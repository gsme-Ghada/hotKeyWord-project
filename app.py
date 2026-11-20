"""
app.py
Streamlit UI. No logic here: it takes the URL, calls analyze, and shows the result.
    
"""
import html

import altair as alt
import pandas as pd
import streamlit as st

from analyzer import analyze
from keywords import count_keywords

st.set_page_config(page_title="Hot Keywords", page_icon="🔥", layout="wide")

LANG_LABELS = {"ar": "Arabic", "en": "English", "mixed": "Arabic + English", "unknown": "Unknown"}
FETCH_LABELS = {"requests": "requests", "selenium": "Selenium (browser)"}


def text_block(text, max_height=None):
    """Shows text with automatic direction (RTL for Arabic / LTR for English), keeping line breaks."""
    style = "white-space: pre-wrap; line-height: 1.7;"
    if max_height:
        style += f" max-height: {max_height}px; overflow-y: auto;"
    st.markdown(
        f'<div dir="auto" style="{style}">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


# Input
st.title("🔥 Hot Keywords")
st.write("Enter a page URL and I'll show the most frequent words in its main content.")

with st.sidebar:
    st.header("Settings")
    top_n = st.slider("Number of keywords shown", min_value=5, max_value=50, value=15, step=5)
    mode = st.radio("Count type", ["Single words", "Two-word phrases (Bigrams)"])
    n = 1 if mode == "Single words" else 2

# Using a form so pressing Enter works like clicking the button
with st.form("url_form"):
    url = st.text_input("Page URL", placeholder="https://example.com/article")
    submitted = st.form_submit_button("Analyze page", type="primary")

if submitted:
    if not url.strip():
        st.session_state.pop("result", None)
        st.warning("Enter a URL first.")
    else:
        with st.spinner("Fetching and analyzing the page... this may take a few seconds"):
            st.session_state["result"] = analyze(url)

# Result
# The result is kept in session_state, so moving the slider doesn't re-fetch the page
result = st.session_state.get("result")

if result:
    if not result["ok"]:
        st.error(result["error"])
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Page language", LANG_LABELS.get(result["lang"], result["lang"]))
        c2.metric("Words after cleaning", result["total_words"])
        c3.metric("Unique words", result["unique_words"])
        c4.metric("Fetch method", FETCH_LABELS.get(result["fetch_method"], result["fetch_method"]))

        for msg in result["warnings"]:
            st.warning(msg)

        kw = count_keywords(result["words"], n=n, top=top_n)
        df = pd.DataFrame(kw, columns=["Keyword", "Frequency"])

        st.subheader("Most frequent keywords")
        left, right = st.columns([1, 2])
        with left:
            st.dataframe(df, hide_index=True)
            st.download_button(
                "Download results as CSV",
                df.to_csv(index=False).encode("utf-8-sig"),  # utf-8-sig so Excel reads Arabic correctly
                file_name="keywords.csv",
                mime="text/csv",
            )
        with right:
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    y=alt.Y("Keyword:N", sort=None, title=None),   # sort=None: same order as the table
                    x=alt.X("Frequency:Q", title="Frequency"),
                    tooltip=["Keyword", "Frequency"],
                )
            )
            st.altair_chart(chart)

        st.subheader("Analyzed content")
        st.caption(
            f"Extraction method: {result['extract_method']} | Page: {result['url']}"
        )
        st.markdown("**Longest paragraph in the extracted content**")
        text_block(result["longest_paragraph"])
        with st.expander("Show the full extracted text"):
            text_block(result["text"], max_height=400)