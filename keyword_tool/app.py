"""
app.py
واجهة Streamlit. مفيهاش منطق: بتاخد اللينك، تنادي analyze، وتعرض النتيجة.

التشغيل:
    streamlit run app.py
"""
import html

import altair as alt
import pandas as pd
import streamlit as st

from analyzer import analyze
from keywords import count_keywords

st.set_page_config(page_title="Hot Keywords", page_icon="🔥", layout="wide")

LANG_LABELS = {"ar": "عربي", "en": "إنجليزي", "mixed": "عربي + إنجليزي", "unknown": "غير معروف"}
FETCH_LABELS = {"requests": "requests", "selenium": "Selenium (متصفح)"}


def text_block(text, max_height=None):
    """بيعرض النص باتجاه تلقائي (RTL للعربي / LTR للإنجليزي) مع الحفاظ على الأسطر."""
    style = "white-space: pre-wrap; line-height: 1.7;"
    if max_height:
        style += f" max-height: {max_height}px; overflow-y: auto;"
    st.markdown(
        f'<div dir="auto" style="{style}">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------ الإدخال
st.title("🔥 Hot Keywords")
st.write("اكتبي لينك صفحة، وهطلّعلك أكتر الكلمات تكراراً في محتواها الأساسي.")

with st.sidebar:
    st.header("الإعدادات")
    top_n = st.slider("عدد الكلمات المعروضة", min_value=5, max_value=50, value=15, step=5)
    mode = st.radio("نوع العد", ["كلمات مفردة", "عبارات من كلمتين (Bigrams)"])
    n = 1 if mode == "كلمات مفردة" else 2

# form عشان زرار Enter يشتغل زي الزرار
with st.form("url_form"):
    url = st.text_input("لينك الصفحة", placeholder="https://example.com/article")
    submitted = st.form_submit_button("حلّل الصفحة", type="primary")

if submitted:
    if not url.strip():
        st.session_state.pop("result", None)
        st.warning("اكتبي اللينك الأول.")
    else:
        with st.spinner("بجيب الصفحة وبحلّلها... ممكن ياخد كام ثانية"):
            st.session_state["result"] = analyze(url)

# ------------------------------------------------------------------ النتيجة
# النتيجة محفوظة في session_state، فتغيير السلايدر مش بيعيد تحميل الصفحة من النت
result = st.session_state.get("result")

if result:
    if not result["ok"]:
        st.error(result["error"])
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("لغة الصفحة", LANG_LABELS.get(result["lang"], result["lang"]))
        c2.metric("الكلمات بعد التنضيف", result["total_words"])
        c3.metric("كلمات مختلفة", result["unique_words"])
        c4.metric("طريقة الجلب", FETCH_LABELS.get(result["fetch_method"], result["fetch_method"]))

        for msg in result["warnings"]:
            st.warning(msg)

        kw = count_keywords(result["words"], n=n, top=top_n)
        df = pd.DataFrame(kw, columns=["Keyword", "Frequency"])

        st.subheader("أكتر الكلمات تكراراً")
        left, right = st.columns([1, 2])
        with left:
            st.dataframe(df, hide_index=True)
            st.download_button(
                "تحميل النتيجة CSV",
                df.to_csv(index=False).encode("utf-8-sig"),  # utf-8-sig عشان Excel يقرا العربي
                file_name="keywords.csv",
                mime="text/csv",
            )
        with right:
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    y=alt.Y("Keyword:N", sort=None, title=None),   # sort=None: نفس ترتيب الجدول
                    x=alt.X("Frequency:Q", title="التكرار"),
                    tooltip=["Keyword", "Frequency"],
                )
            )
            st.altair_chart(chart)

        st.subheader("المحتوى اللي اتحلّل")
        st.caption(
            f"طريقة الاستخراج: {result['extract_method']} | الصفحة: {result['url']}"
        )
        st.markdown("**أطول فقرة في المحتوى المستخرج**")
        text_block(result["longest_paragraph"])
        with st.expander("عرض النص المستخرج كامل"):
            text_block(result["text"], max_height=400)
