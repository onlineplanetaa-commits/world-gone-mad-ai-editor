#!/usr/bin/env python3
"""Build a daily, human-reviewed World Gone Mad research shortlist from Google News RSS."""

from __future__ import annotations

import calendar
from difflib import SequenceMatcher
import html
from html.parser import HTMLParser
import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import feedparser

KYIV = ZoneInfo("Europe/Kyiv")
OUTPUT_DIR = Path("daily-shortlist")
MAX_STORIES = 15
MAX_PER_TOPIC = 4
WINDOW = timedelta(hours=24)

TOPICS = {
    "UFOs & unexplained": '("UFO" OR "UAP" OR "unexplained aerial" OR "alien encounter")',
    "Strange events & creatures": '("mysterious creature" OR "strange creature" OR "unusual phenomenon" OR "mysterious sighting")',
    "Disasters & extreme events": '("natural disaster" OR earthquake OR volcano OR extreme weather OR "strange natural phenomenon")',
    "Wars & global events": '("war" OR conflict OR missile OR military OR geopolitical)',
    "Science & discoveries": '("scientific discovery" OR breakthrough OR space OR astronomy OR archaeology)',
    "Mysteries & archaeology": '("archaeological mystery" OR ancient discovery OR unexplained mystery OR lost civilization)',
}

BLOCKED_TERMS = (
    "gta 6", "grand theft auto", "video game", "gaming", "gameplay",
    "playstation", "xbox", "nintendo", "steam game", "fortnite",
    "minecraft", "call of duty", "game release", "gaming storyline",
    "conflict of interest", "opinion |", "film review", "movie review",
    "book review", "panel discussion", "box office", "tv review",
    "full moon calendar", "moon phases", "forum to focus", "supports military families",
    "ufo spark", "ufo device", "ufo technology", "green path review",
    "stock", "shares", "ticker", "earnings", "investor",
)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def published_datetime(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def get_domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def fetch_topic(topic: str, query: str, cutoff: datetime):
    rss_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query + " when:1d")
        + "&hl=en&gl=US&ceid=US:en"
    )
    request = Request(
        rss_url,
        headers={"User-Agent": "WorldGoneMadResearch/1.0 (daily public RSS research)"},
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read(2_000_000)
    feed = feedparser.parse(payload)
    stories = []

    for entry in feed.entries:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        summary = clean_text(entry.get("summary", ""))
        published = published_datetime(entry)
        source = entry.get("source", {})
        source_url = source.get("href", "") if hasattr(source, "get") else ""
        domain = get_domain(source_url or link)
        haystack = (title + " " + summary).lower()

        if not title or not link or not published or published < cutoff:
            continue
        if domain == "ua-stena.info" or domain.endswith(".ua-stena.info"):
            continue
        if any(term in haystack for term in BLOCKED_TERMS):
            continue

        # Require a meaningful title signal for the selected topic. This cuts
        # unrelated stories returned by broad Google News OR queries.
        title_lower = title.lower()
        topic_signals = {
            "UFOs & unexplained": ("uap", "alien", "extraterrestrial", "unexplained aerial", "ufo sighting", "ufo encounter", "ufo over", "ufo footage", "ufo report", "ufo mystery", "mistaken for ufo"),
            "Strange events & creatures": ("creature", "monster", "beast", "cryptid", "mysterious", "strange", "unusual", "sighting"),
            "Disasters & extreme events": ("earthquake", "volcano", "eruption", "flood", "hurricane", "tornado", "wildfire", "tsunami", "landslide", "disaster", "extreme weather"),
            "Wars & global events": ("war", "missile", "drone", "airstrike", "airspace", "attack", "invasion", "ceasefire", "troops", "army", "navy", "bombing", "military", "defense", "weapons", "frontline", "casualties", "soldiers", "air defense", "shelling", "occupation", "hostilities"),
            "Science & discoveries": ("discovery", "breakthrough", "researchers", "scientists", "study finds", "new study", "nasa", "space mission", "astronomers", "telescope", "scientific discovery", "experiment", "new species", "fossil"),
            "Mysteries & archaeology": ("archaeology", "archaeological", "ancient discovery", "ancient artifact", "mystery", "mysterious discovery", "lost civilization", "shipwreck", "ruins", "excavation", "hidden chamber", "buried city"),
        }
        if not any(signal in title_lower for signal in topic_signals.get(topic, ())):
            continue
        if any(term in title_lower for term in (
            "calendar", "horoscope", "weekly forecast", "daily forecast",
            "forum to focus", "panel discussion", "supports military families",
            "ufo spark", "device enters", "green path review",
        )):
            continue

        publisher = clean_text(source.get("title", "")) if hasattr(source, "get") else ""
        if not publisher:
            publisher = domain or "Unknown publisher"
        # Google News descriptions sometimes repeat the headline verbatim.
        title_key = re.sub(r"\s+", " ", title).strip().casefold()
        summary_key = re.sub(r"\s+", " ", summary).strip().casefold()
        if summary_key == title_key:
            summary = ""
        elif summary_key.startswith(title_key):
            summary = summary[len(title):].lstrip(" -:|")
        if publisher and summary.lower().endswith(publisher.lower()):
            summary = summary[: -len(publisher)].strip()
        if summary.lower() == title.lower():
            summary = ""

        stories.append({
            "topic": topic,
            "title": title,
            "link": link,
            "summary": summary[:650],
            "publisher": publisher,
            "domain": domain,
            "published": published,
        })

    return stories


class ArticleTextParser(HTMLParser):
    """Small, dependency-free extractor for readable article paragraphs."""
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}
    CONTENT_TAGS = {"article", "main"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.content_depth = 0
        self.paragraph_depth = 0
        self.paragraphs = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.CONTENT_TAGS:
            self.content_depth += 1
        if tag == "p":
            self.paragraph_depth += 1
            self.current = []

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "p" and self.paragraph_depth:
            value = clean_text(" ".join(self.current))
            if len(value) >= 45:
                self.paragraphs.append((self.content_depth > 0, value))
            self.paragraph_depth -= 1
            self.current = []
        if tag in self.CONTENT_TAGS and self.content_depth:
            self.content_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth and self.paragraph_depth:
            self.current.append(data)

    def article_text(self):
        preferred = [p for in_article, p in self.paragraphs if in_article]
        chosen = preferred if preferred else [p for _, p in self.paragraphs]
        return "\\n\\n".join(chosen)[:9000]


def fetch_article_text(url):
    """Fetch a public article page without bypassing paywalls or script barriers."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return {"status": "skipped: unsupported URL", "text": ""}
        host = parsed.hostname.lower()
        if host in ("localhost",) or host.endswith((".local", ".internal")):
            return {"status": "skipped: non-public host", "text": ""}
        try:
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            if not addresses or any(ipaddress.ip_address(item[4][0].split("%")[0]).is_private or ipaddress.ip_address(item[4][0].split("%")[0]).is_loopback or ipaddress.ip_address(item[4][0].split("%")[0]).is_link_local for item in addresses):
                return {"status": "skipped: non-public address", "text": ""}
        except Exception:
            return {"status": "unavailable: host lookup failed", "text": ""}
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; WorldGoneMadResearch/1.0)", "Accept": "text/html"})
        with urlopen(request, timeout=8) as response:
            final_url = urlparse(response.geturl())
            final_host = (final_url.hostname or "").lower()
            if final_url.scheme not in ("http", "https") or not final_host:
                return {"status": "skipped: unsafe redirect", "text": ""}
            try:
                final_addresses = socket.getaddrinfo(final_host, final_url.port or (443 if final_url.scheme == "https" else 80))
                final_ips = [ipaddress.ip_address(item[4][0].split("%")[0]) for item in final_addresses]
                if not final_ips or any(not ip.is_global for ip in final_ips):
                    return {"status": "skipped: redirect to non-public address", "text": ""}
            except Exception:
                return {"status": "unavailable: redirect host lookup failed", "text": ""}
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return {"status": "unavailable: not an HTML page", "text": ""}
            payload = response.read(1_000_000)
        parser = ArticleTextParser()
        parser.feed(payload.decode("utf-8", errors="replace"))
        text = parser.article_text()
        if len(text) < 250:
            return {"status": "limited: page blocked, scripted or no readable article text", "text": text}
        return {"status": "extracted", "text": text}
    except Exception as exc:
        return {"status": f"unavailable: {type(exc).__name__}", "text": ""}


def find_other_coverage(story):
    """Find additional publisher leads; syndication is not proof of independence."""
    query = '"' + story["title"][:180] + '" when:7d'
    rss_url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en&gl=US&ceid=US:en"
    )
    request = Request(
        rss_url,
        headers={"User-Agent": "WorldGoneMadResearch/1.0 (public RSS cross-check)"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            feed = feedparser.parse(response.read(800_000))
    except Exception:
        return []

    leads = []
    seen_domains = {story.get("domain", "")}
    for entry in feed.entries:
        source = entry.get("source", {})
        source_url = source.get("href", "") if hasattr(source, "get") else ""
        domain = get_domain(source_url)
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        if not domain or domain == "news.google.com" or domain in seen_domains or not title or not link:
            continue
        seen_domains.add(domain)
        publisher = clean_text(source.get("title", "")) if hasattr(source, "get") else ""
        leads.append({
            "publisher": publisher or domain,
            "domain": domain,
            "title": title,
            "link": link,
        })
        if len(leads) >= 4:
            break
    return leads


def score_research_priority(story):
    """Transparent editorial triage heuristic; never a truth or reliability score."""
    score = 2
    reasons = ["recent candidate"]
    title = story.get("title", "")
    summary = story.get("summary", "")
    if len(title) >= 55:
        score += 1
        reasons.append("specific headline")
    if len(summary) >= 180:
        score += 2
        reasons.append("substantive feed summary")
    if re.search(r"\b(earthquake|eruption|crash|encounter|sighting|discovery|attack|missile|explosion|creature|artifact|fossil|shipwreck)\b", title, re.I):
        score += 2
        reasons.append("concrete event signal")
    if story.get("domain") and story["domain"] != "news.google.com":
        score += 1
        reasons.append("publisher domain identified")
    coverage_count = len(story.get("coverage", []))
    if coverage_count:
        score += min(coverage_count, 2)
        reasons.append(f"{coverage_count} additional coverage lead(s)")
    return min(score, 10), reasons


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - WINDOW
    all_stories = []
    errors = []

    for topic, query in TOPICS.items():
        try:
            all_stories.extend(fetch_topic(topic, query, cutoff))
        except Exception as exc:
            errors.append(f"{topic}: {type(exc).__name__}: {exc}")

    seen = set()
    unique = []
    topic_counts = {topic: 0 for topic in TOPICS}
    # Keep the shortlist from being overwhelmed by one broad category.
    for story in sorted(all_stories, key=lambda item: item["published"], reverse=True):
        key = re.sub(r"[^a-z0-9]+", " ", story["title"].lower()).strip()
        # Suppress near-identical headlines returned by overlapping topic feeds.
        if key in seen or any(SequenceMatcher(None, key, previous).ratio() >= 0.84 for previous in seen):
            continue
        if topic_counts.get(story["topic"], 0) >= MAX_PER_TOPIC:
            continue
        seen.add(key)
        topic_counts[story["topic"]] = topic_counts.get(story["topic"], 0) + 1
        unique.append(story)

    # Search for other publisher coverage for each shortlisted candidate.
    # These are leads to inspect, not proof of independent corroboration.
    for story in unique[:MAX_STORIES]:
        story["coverage"] = find_other_coverage(story)
        story["article"] = fetch_article_text(story["link"])
        # Read at most one additional publisher page; the others remain leads.
        for lead in story["coverage"][:1]:
            lead["article"] = fetch_article_text(lead["link"])
        story["priority_score"], story["priority_reasons"] = score_research_priority(story)

    local_now = now.astimezone(KYIV)
    date_label = local_now.strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{date_label}.md"

    lines = [
        f"# World Gone Mad — Daily Research Shortlist ({date_label})",
        "",
        f"Generated: {local_now.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "Research candidates from public Google News RSS feeds, published in the last 24 hours.",
        "",
        "**Editorial status:** candidates only. Headlines and summaries are not verification. Open the original report, inspect the evidence, and seek independent coverage before drafting.",
        "**Research priority is a transparent heuristic for triage, not an AI verdict, truth score or source-reliability rating. Additional coverage leads may be syndicated copies.**",
        "",
        f"**Candidates found:** {min(len(unique), MAX_STORIES)} of {len(unique)} unique results",
        "",
    ]

    for index, story in enumerate(unique[:MAX_STORIES], 1):
        published_local = story["published"].astimezone(KYIV).strftime("%Y-%m-%d %H:%M %Z")
        lines.extend([
            f"## {index}. {story['title']}",
            "",
            f"- **Topic:** {story['topic']}",
            f"- **Published:** {published_local}",
            f"- **Publisher:** {story['publisher']} ({story['domain'] or 'domain unavailable'})",
            f"- **Research priority:** {story.get('priority_score', 2)}/10 — {', '.join(story.get('priority_reasons', ['recent candidate']))}",
            f"- **Original report:** {story['link']}",
            f"- **Article extraction:** {story.get('article', {}).get('status', 'not attempted')}",
            "",
            story["summary"] or "_No summary supplied by the feed._",
            "",
            "**Extracted original article text (for manual review):**",
            "",
            (story.get("article", {}).get("text", "")[:2200] or "_No readable article text extracted. Open the original page manually; paywalls and script-rendered pages are not bypassed._"),
            "",
            f"**Other coverage leads ({len(story.get('coverage', []))}; check whether they are independent):**",
            *(
                [f"- {item['publisher']} ({item['domain']}): [{item['title']}]({item['link']}) — article: {item.get('article', {}).get('status', 'not fetched')}" for item in story.get("coverage", [])]
                or ["- No additional publisher leads found by the title search."]
            ),
            "",
        ])

    if not unique:
        lines.extend(["No qualifying stories were found in the feeds during this run.", ""])

    if errors:
        lines.extend(["## Feed warnings", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.extend(["", "This shortlist may be incomplete because one or more feeds failed.", ""])

    lines.extend([
        "---",
        "",
        "This file is an automatically collected research queue, not a fact-checked news report. No Telegram post is published automatically.",
        "",
    ])
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output} with {min(len(unique), MAX_STORIES)} candidates; {len(errors)} feed errors.")


if __name__ == "__main__":
    main()
