import os
from urllib.parse import quote_plus, urlparse

import feedparser
from flask import Flask, render_template_string, request

app = Flask(__name__)

CATEGORIES = {
    "UFOs & unexplained": '"UFO" OR "UAP" OR unexplained sighting OR mysterious lights',
    "Strange events & creatures": '"strange creature" OR mysterious animal OR unexplained event',
    "Disasters & extreme events": 'major disaster OR extreme weather OR unusual natural phenomenon',
    "Wars & global events": 'major world events OR conflict OR international crisis',
    "Science & discoveries": 'scientific discovery OR space discovery OR unusual research',
    "Mysteries & archaeology": 'archaeological mystery OR unexplained historical discovery',
}
REGIONS = {
    "Worldwide": ("US", "EN"),
    "United States": ("US", "EN"),
    "United Kingdom": ("GB", "EN"),
    "Canada": ("CA", "EN"),
    "Australia": ("AU", "EN"),
}
RANGES = {"Past 24 hours": "when:1d", "Past week": "when:7d", "Any time": ""}

# Keep the Telegram channel independent from the user's website and remove
# obvious gaming/entertainment noise from real-world research results.
EXCLUDED_DOMAINS = ("ua-stena.info",)
NOISE_TERMS = (
    "gta 6", "grand theft auto", "video game", "gaming", "gameplay",
    "playstation", "xbox", "nintendo", "steam game", "fortnite",
    "minecraft", "call of duty", "game release", "gaming storyline",
)

def is_relevant_story(entry):
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    link = entry.get("link", "")
    source = entry.get("source", {}).get("title", "")
    text = " ".join((title, summary, source, link)).lower()
    host = urlparse(link).netloc.lower()
    if any(domain in host or domain in source.lower() for domain in EXCLUDED_DOMAINS):
        return False
    if any(term in text for term in NOISE_TERMS):
        return False
    return True

def headline_for_search(title, publisher=""):
    """Remove Google News' trailing publisher suffix before searching coverage."""
    cleaned = title.strip()
    publisher = publisher.strip()
    if publisher:
        suffix = " - " + publisher
        if cleaned.lower().endswith(suffix.lower()):
            cleaned = cleaned[:-len(suffix)].strip()
    return cleaned.strip(' "“”')

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Gone Mad AI Editor</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101114;color:#f3f3f3;font:16px Arial,sans-serif;line-height:1.5}
header{background:#18191d;border-bottom:3px solid #d52b32;padding:22px max(20px,calc((100% - 1050px)/2))}
main{max-width:1050px;margin:26px auto;padding:0 18px}.brand{font-size:27px;font-weight:bold}.brand span{color:#ef454b}
.sub{color:#b7b7bd;margin-top:5px}.panel,.story{background:#1b1d22;border:1px solid #34363d;border-radius:9px;padding:20px;margin:18px 0}
h2{font-size:21px;margin:0 0 14px}h3{font-size:19px;margin:0 0 9px}
label{display:block;font-weight:bold;margin:12px 0 5px}select,input,textarea{width:100%;padding:11px;border:1px solid #555963;border-radius:6px;background:#111318;color:#fff;font:inherit}
textarea{min-height:120px;resize:vertical}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
button,.button{display:inline-block;background:#d52b32;color:#fff;border:0;border-radius:6px;padding:11px 17px;font-weight:bold;font-size:15px;text-decoration:none;cursor:pointer;margin-top:14px}
button:hover,.button:hover{background:#b91f26}.muted{color:#b5b6bd;font-size:14px}.source{color:#ff777d}.checks{background:#15161a;padding:12px;border-radius:6px}.checks p{margin:5px 0}
.story{border-left:4px solid #d52b32}.story p{color:#d3d3d7}.meta{color:#aaa;font-size:13px}.notice{padding:12px;border-radius:6px;background:#292b31;margin:12px 0}.ok{border-left:4px solid #55a86b}.warn{border-left:4px solid #e1ad45}.draft{white-space:pre-wrap;background:#111318;padding:16px;border-radius:6px}
footer{max-width:1050px;margin:25px auto;padding:15px 18px;color:#999;font-size:13px}
a{color:#ff777d}hr{border:0;border-top:1px solid #393b42;margin:24px 0}
</style>
</head>
<body>
<header><div class="brand">WORLD <span>GONE</span> MAD</div><div class="sub">AI EDITOR · Research, verify and prepare English-language Telegram posts</div></header>
<main>
<div class="notice warn">Research only. Nothing is published automatically. Search results are leads, not verified facts. Always check the original report.</div>
<section class="panel">
<h2>Find stories</h2>
<form method="post" action="/">
<div class="grid">
<div><label for="category">Topic</label><select id="category" name="category">{% for c in categories %}<option value="{{c}}" {% if c==category %}selected{% endif %}>{{c}}</option>{% endfor %}</select></div>
<div><label for="region">News region</label><select id="region" name="region">{% for r in regions %}<option value="{{r}}" {% if r==region %}selected{% endif %}>{{r}}</option>{% endfor %}</select></div>
<div><label for="period">Time range</label><select id="period" name="period">{% for p in ranges %}<option value="{{p}}" {% if p==period %}selected{% endif %}>{{p}}</option>{% endfor %}</select></div>
<div><label for="limit">Number of results</label><select id="limit" name="limit">{% for n in [5,10,15,20,30] %}<option value="{{n}}" {% if n==limit %}selected{% endif %}>{{n}}</option>{% endfor %}</select></div>
</div><button type="submit">Search news</button>
</form></section>
{% if searched %}
<section><h2>Research results: {{category}}</h2>
{% if stories %}
<p class="muted">Found {{stories|length}} candidate stories. Obvious gaming noise and ua-stena.info results are filtered out. {% if filtered_count %}{{filtered_count}} irrelevant results were skipped.{% endif %} Open each source and verify dates, evidence and independent coverage.</p>
{% for s in stories %}
<article class="story"><h3>{{loop.index}}. {{s.title}}</h3>
<p>{{s.summary|striptags|truncate(500)}}</p>
<div class="meta">Published: {{s.published}} · Feed source: {{s.source}}</div>
{% if s.link %}<p><a class="button" href="{{s.link}}" target="_blank" rel="noopener noreferrer">Open original report</a></p>{% endif %}
<div class="checks"><strong>Editorial checks</strong><p>☐ Confirm the original publication</p><p>☐ Check the event date and location</p><p>☐ Compare with another reliable source</p><p>☐ Separate confirmed facts from claims</p></div>
<form method="post" action="/research">
<input type="hidden" name="title" value="{{s.title}}">
<input type="hidden" name="source" value="{{s.source}}">
<input type="hidden" name="link" value="{{s.link}}">
<button type="submit">Find other coverage</button>
</form>
<details><summary>Prepare a Telegram draft from this story</summary>
<form method="post" action="/draft">
<input type="hidden" name="title" value="{{s.title}}">
<input type="hidden" name="summary" value="{{s.summary|striptags|truncate(3000, True, '')}}">
<input type="hidden" name="link" value="{{s.link}}">
<input type="hidden" name="published" value="{{s.published}}">
<input type="hidden" name="source" value="{{s.source}}">
<label>Verified details / notes</label><textarea name="notes" required placeholder="What happened? Where and when? What is confirmed? What remains unknown?"></textarea>
<div class="grid"><div><label>Writing style</label><select name="tone"><option>Engaging news brief</option><option>Mysterious but factual</option><option>Straight news report</option></select></div>
<div><label>Post length</label><select name="length"><option>Short (70–100 words)</option><option selected>Medium (100–150 words)</option><option>Detailed (150–200 words)</option></select></div></div>
<button type="submit">Generate draft</button></form></details></article>
{% endfor %}
{% else %}<div class="notice">No results were returned. Try another topic or a wider time range.</div>{% endif %}
</section>
{% endif %}
{% if research_results is not none %}
<section class="panel"><h2>Additional coverage to inspect</h2>
<h3>{{research_title}}</h3>
<p class="muted">These are search leads, not verified independent confirmation. Check whether each report has its own evidence and is not merely repeating the original story.</p>
{% if research_results %}
<p class="muted">Potentially distinct publishers found: {{research_publisher_count}}. This is a publisher count, not a reliability score.</p>
{% for item in research_results %}
<article class="story"><h3>{{loop.index}}. {{item.title}}</h3>
<div class="meta">Publisher: {{item.source}} · {{item.published}}{% if item.publisher_domain %} · {{item.publisher_domain}}{% endif %}</div>
{% if item.summary %}<p>{{item.summary|striptags|truncate(400)}}</p>{% endif %}
{% if item.link %}<a class="button" href="{{item.link}}" target="_blank" rel="noopener noreferrer">Open coverage</a>{% endif %}
</article>
{% endfor %}
{% else %}
<div class="notice">No additional matching coverage was found in Google News. This does not prove the story is false; try searching distinctive names or phrases manually.</div>
{% endif %}
</section>
{% endif %}
{% if draft %}
<section class="panel"><h2>Draft for manual review</h2><div class="draft">{{draft}}</div><p class="muted">Review every factual claim before manually posting. The source link stays separate.</p>{% if source_link %}<a href="{{source_link}}" target="_blank" rel="noopener noreferrer">Open source report</a>{% endif %}</section>
{% endif %}
{% if error %}<div class="notice warn">{{error}}</div>{% endif %}
<section class="panel"><h2>Manual topic ideas</h2>
<form method="post" action="/checklist"><label>Topic to investigate</label><input name="idea" required placeholder="Enter a story, event or mystery"><button type="submit">Create research checklist</button></form>
{% if checklist %}<hr><h3>Research checklist: {{idea}}</h3>{% for item in checklist %}<p>☐ {{item}}</p>{% endfor %}{% endif %}
</section>
<div class="muted">No Telegram login · No Reddit access · No automatic publishing · No links to ua-stena.info</div>
</main><footer>World Gone Mad AI Editor · Human review required before publication.</footer>
</body></html>
"""

def render_page(**kwargs):
    defaults = {
        "categories": list(CATEGORIES), "regions": list(REGIONS), "ranges": list(RANGES),
        "category": "UFOs & unexplained", "region": "Worldwide",
        "period": "Past 24 hours", "limit": 15, "searched": False,
        "stories": [], "filtered_count": 0, "draft": None, "error": None, "source_link": None,
        "research_results": None, "research_title": "", "research_publisher_count": 0,
        "checklist": None, "idea": "",
    }
    defaults.update(kwargs)
    return render_template_string(PAGE, **defaults)

@app.get("/")
def home():
    return render_page()

@app.post("/")
def search():
    category = request.form.get("category", "UFOs & unexplained")
    region = request.form.get("region", "Worldwide")
    period = request.form.get("period", "Past 24 hours")
    try:
        limit = max(5, min(30, int(request.form.get("limit", "15"))))
    except ValueError:
        limit = 15
    category = category if category in CATEGORIES else "UFOs & unexplained"
    region = region if region in REGIONS else "Worldwide"
    period = period if period in RANGES else "Past 24 hours"
    gl, hl = REGIONS[region]
    query = " ".join(part for part in (CATEGORIES[category], RANGES[period], "-site:ua-stena.info", "-\"GTA 6\"", "-gaming", "-gameplay") if part)
    url = "https://news.google.com/rss/search?q=" + quote_plus(query) + f"&hl={hl.lower()}&gl={gl}&ceid={gl}:{hl.lower()}"
    try:
        parsed = feedparser.parse(url)
        stories = []
        seen_titles = set()
        filtered_count = 0
        for entry in parsed.entries:
            if not is_relevant_story(entry):
                filtered_count += 1
                continue
            title = entry.get("title", "Untitled").strip()
            title_key = title.lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            stories.append({
                "title": title,
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", "Date unavailable"),
                "source": entry.get("source", {}).get("title", "Source not identified"),
            })
            if len(stories) >= limit:
                break
        return render_page(category=category, region=region, period=period, limit=limit, searched=True, stories=stories, filtered_count=filtered_count)
    except Exception as exc:
        return render_page(category=category, region=region, period=period, limit=limit, searched=True, error="News search failed: " + str(exc)), 502

@app.post("/research")
def research():
    title = request.form.get("title", "").strip()
    original_source = request.form.get("source", "").strip().lower()
    original_link = request.form.get("link", "").strip()
    if not title:
        return render_page(error="No story title was supplied for the additional search.")
    # Google News appends publisher names to many headlines ("Headline - Publisher").
    # Strip that suffix so exact and keyword searches target the actual story.
    # Results remain discovery leads, not proof of independent reporting.
    clean_title = headline_for_search(title, request.form.get("source", ""))
    clean_title = clean_title.replace('"', ' ')
    stop_words = {"about", "after", "against", "could", "from", "have", "into", "more",
                  "mysterious", "report", "says", "that", "their", "there", "these",
                  "this", "what", "when", "where", "which", "while", "with", "would"}
    words = [word for word in clean_title.split() if len(word) > 3 and word.lower() not in stop_words]
    broad_query = " ".join(words[:8]) if words else clean_title
    queries = [
        '"' + clean_title + '" -site:ua-stena.info',
        broad_query + " -site:ua-stena.info",
    ]
    try:
        results = []
        seen_titles = set()
        seen_publishers = set()
        for query in queries:
            url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en&gl=US&ceid=US:en"
            parsed = feedparser.parse(url)
            for entry in parsed.entries:
                if not is_relevant_story(entry):
                    continue
                publisher = entry.get("source", {}).get("title", "Publisher not identified").strip()
                publisher_key = publisher.lower()
                headline = entry.get("title", "").strip()
                key = headline.lower()
                source_url = entry.get("source", {}).get("href", "") or entry.get("source", {}).get("url", "")
                publisher_domain = urlparse(source_url).netloc.lower().removeprefix("www.")
                # Do not count the original publisher or original link as another source.
                if original_source and publisher_key == original_source:
                    continue
                if original_link and entry.get("link", "").split("?")[0] == original_link.split("?")[0]:
                    continue
                if not headline or key in seen_titles or publisher_key in seen_publishers:
                    continue
                seen_titles.add(key)
                seen_publishers.add(publisher_key)
                results.append({
                    "title": headline,
                    "source": publisher,
                    "publisher_domain": publisher_domain,
                    "published": entry.get("published", "Date unavailable"),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                })
                if len(results) >= 10:
                    break
            if len(results) >= 10:
                break
        return render_page(
            research_results=results,
            research_publisher_count=len(seen_publishers),
            research_title=title,
            source_link=original_link,
        )
    except Exception as exc:
        return render_page(error="Additional coverage search failed: " + str(exc), source_link=original_link), 502

@app.post("/draft")
def make_draft():
    title = request.form.get("title", "")
    summary = request.form.get("summary", "")
    link = request.form.get("link", "")
    notes = request.form.get("notes", "").strip()
    tone = request.form.get("tone", "Engaging news brief")
    length = request.form.get("length", "Medium (100–150 words)")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not notes:
        return render_page(error="Add verified notes before generating a draft.", source_link=link)
    if not api_key:
        return render_page(error="AI drafting is not enabled yet. News research works without an API key. An OpenAI API key is optional and API usage may incur charges.", source_link=link)
    try:
        from openai import OpenAI
        prompt = f"""You are the editor of the English-language Telegram channel World Gone Mad.
Write an original Telegram post based ONLY on the source information and verified notes below.
Do not invent quotes, eyewitnesses, numbers, dates, locations, causes or conclusions.
If a claim is unverified, clearly attribute it. Do not present speculation as fact.
Use an intriguing but responsible headline, short readable paragraphs, and 2-4 relevant hashtags.
Do not include links to any website in the post. Do not mention Reddit.
Style: {tone}. Length: {length}.
Story headline: {title}
Feed summary (may be incomplete): {summary}
Verified notes supplied by editor: {notes}
Return only the post text. After the post, do not add source links or editorial commentary."""
        response = OpenAI(api_key=api_key).responses.create(model="gpt-4.1-mini", input=prompt)
        return render_page(draft=response.output_text.strip(), source_link=link)
    except Exception as exc:
        return render_page(error="Draft generation failed: " + str(exc), source_link=link), 500

@app.post("/checklist")
def checklist():
    idea = request.form.get("idea", "").strip()
    if not idea:
        return render_page(error="Enter a topic first.")
    items = [
        f"Find the earliest reliable report about: {idea}",
        "Identify the original source, date and location.",
        "Find at least one independent source.",
        "Check whether images or video are authentic and correctly dated.",
        "List confirmed facts separately from speculation.",
        "Decide whether the story is suitable for World Gone Mad.",
    ]
    return render_page(idea=idea, checklist=items)

@app.get("/health")
def health():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
