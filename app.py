import os
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import streamlit as st

st.set_page_config(page_title="World Gone Mad AI Editor", page_icon="🌍", layout="wide")

CATEGORIES = {
    "UFOs & unexplained": '"UFO" OR "UAP" OR unexplained sighting OR mysterious lights',
    "Strange events & creatures": '"strange creature" OR mysterious animal OR unexplained event',
    "Disasters & extreme events": 'major disaster OR extreme weather OR unusual natural phenomenon',
    "Wars & global events": 'major world events OR conflict OR international crisis',
    "Science & discoveries": 'scientific discovery OR space discovery OR unusual research',
    "Mysteries & archaeology": 'archaeological mystery OR unexplained historical discovery',
}

st.title("🌍 World Gone Mad AI Editor")
st.caption("Research, verify and prepare English-language Telegram posts. Nothing is published automatically.")

with st.sidebar:
    st.header("Research settings")
    category = st.selectbox("Topic", list(CATEGORIES.keys()))
    region = st.selectbox("News region", ["Worldwide", "United States", "United Kingdom", "Canada", "Australia"])
    hours = st.selectbox("Time range", ["Past 24 hours", "Past week", "Any time"], index=0)
    max_items = st.slider("Number of results", 5, 30, 15)
    st.divider()
    st.caption("The agent does not connect to Telegram, Reddit or your social accounts.")

region_codes = {
    "Worldwide": ("US", "EN"),
    "United States": ("US", "EN"),
    "United Kingdom": ("GB", "EN"),
    "Canada": ("CA", "EN"),
    "Australia": ("AU", "EN"),
}
gl, hl = region_codes[region]
when = {"Past 24 hours": "when:1d", "Past week": "when:7d", "Any time": ""}[hours]
query = " ".join(x for x in [CATEGORIES[category], when] if x)
feed_url = (
    "https://news.google.com/rss/search?q="
    + quote_plus(query)
    + f"&hl={hl.lower()}&gl={gl}&ceid={gl}:{hl.lower()}"
)

@st.cache_data(ttl=900, show_spinner=False)
def load_feed(url, limit):
    parsed = feedparser.parse(url)
    items = []
    for entry in parsed.entries[:limit]:
        items.append({
            "title": entry.get("title", "Untitled"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", "Publication date unavailable"),
            "source": entry.get("source", {}).get("title", "Source not identified"),
        })
    return items, getattr(parsed, "bozo", False)

st.subheader(f"Research results: {category}")
st.caption("Search results are leads, not verified facts. Open the original report and check dates, evidence and independent coverage before publishing.")

if st.button("🔎 Find stories", type="primary"):
    st.cache_data.clear()

with st.spinner("Searching news feeds..."):
    stories, feed_warning = load_feed(feed_url, max_items)

if not stories:
    st.warning("No results were returned. Try another topic or a wider time range.")
else:
    st.success(f"Found {len(stories)} possible stories.")
    labels = [f"{i+1}. {s['title']}" for i, s in enumerate(stories)]
    selected_index = st.selectbox("Choose a story to prepare", range(len(stories)), format_func=lambda i: labels[i])
    story = stories[selected_index]

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"### {story['title']}")
        st.write(story["summary"] or "No summary supplied by the feed.")
        st.caption(f"Published: {story['published']} · Feed source: {story['source']}")
        if story["link"]:
            st.link_button("Open original report", story["link"])
    with right:
        st.markdown("#### Editorial checks")
        st.write("☐ Confirm the original publication")
        st.write("☐ Check the event date and location")
        st.write("☐ Compare with another reliable source")
        st.write("☐ Separate confirmed facts from claims")

    st.divider()
    st.subheader("Prepare a Telegram post")
    st.write("Add context from the original report. The draft generator will not invent missing details.")
    extra_context = st.text_area(
        "Verified details / notes (recommended)",
        placeholder="What happened? Where and when? What is confirmed? What remains unknown?",
        height=130,
    )
    tone = st.selectbox("Writing style", ["Engaging news brief", "Mysterious but factual", "Straight news report"])
    length = st.selectbox("Post length", ["Short (70–100 words)", "Medium (100–150 words)", "Detailed (150–200 words)"], index=1)

    def make_prompt():
        return f"""You are the editor of the English-language Telegram channel World Gone Mad.
Write an original Telegram post based ONLY on the source information and verified notes below.
Do not invent quotes, eyewitnesses, numbers, dates, locations, causes or conclusions.
If a claim is unverified, clearly attribute it. Do not present speculation as fact.
Use an intriguing but responsible headline, short readable paragraphs, and 2-4 relevant hashtags.
Do not include links to any website in the post. Do not mention Reddit.
Style: {tone}. Length: {length}.
Story headline: {story['title']}
Feed summary (may be incomplete): {story['summary']}
Verified notes supplied by editor: {extra_context}
Return only the post text. After the post, do not add source links or editorial commentary."""

    if st.button("✨ Generate draft", type="primary", disabled=not bool(extra_context.strip())):
        api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        if not api_key:
            st.info("AI generation needs an OpenAI API key. You can still use the source research and copy the template below. Add OPENAI_API_KEY in Streamlit app Secrets when you are ready.")
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                with st.spinner("Writing the draft..."):
                    response = client.responses.create(
                        model="gpt-4.1-mini",
                        input=make_prompt(),
                    )
                st.session_state["draft"] = response.output_text.strip()
            except Exception as exc:
                st.error(f"Draft generation failed: {exc}")

    if st.session_state.get("draft"):
        st.markdown("#### Draft for manual review")
        st.text_area("Telegram post", value=st.session_state["draft"], height=300, key="draft_output")
        st.caption("Review every factual claim before manually posting. The source link stays separate and is not included in the post.")

st.divider()
st.subheader("Manual topic ideas")
idea = st.text_input("Enter a topic you want to investigate")
if st.button("Create research checklist", disabled=not idea.strip()):
    st.session_state["research_checklist"] = [
        f"Find the earliest reliable report about: {idea}",
        "Identify the original source, date and location.",
        "Find at least one independent source.",
        "Check whether images or video are authentic and correctly dated.",
        "List confirmed facts separately from speculation.",
        "Decide whether the story is suitable for World Gone Mad.",
    ]
if st.session_state.get("research_checklist"):
    for item in st.session_state["research_checklist"]:
        st.write("☐ " + item)

st.caption(f"Dashboard build · {datetime.now(timezone.utc).strftime('%Y-%m-%d')} · Research only, no automatic publishing.")
