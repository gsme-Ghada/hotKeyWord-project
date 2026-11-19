"""
analyzer.py
الدالة الوحيدة اللي الواجهة بتناديها: analyze(url).

اللينك ← get_page ← extract_main_text ← detect_lang ← preprocess ← count_keywords

بتجرّب من الـ terminal كمان:
    python analyzer.py https://example.com/article
"""
from extractor import extract_main_text
from fetcher import FetchError, get_page
from keywords import count_keywords
from nlp import detect_lang, preprocess

MIN_WORDS_WARNING = 100   # أقل من كده نحذّر إن الصفحة مش صفحة محتوى


def _longest_line(text):
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return max(lines, key=len) if lines else ""


def analyze(url, n=1, top=20):
    """
    بترجّع dict دايماً (مبترفعش exceptions للواجهة):
      ok, error, url, lang, fetch_method, extract_method, extract_info,
      text, longest_paragraph, words, total_words, unique_words,
      keywords [(kw, freq)], warnings [str]
    لو ok = False الرسالة في error.
    """
    result = {"ok": False, "error": None, "url": url, "warnings": []}
    try:
        html, fetch_info = get_page(url)
        result["url"] = fetch_info["url"]
        result["fetch_method"] = fetch_info["method"]
        result["warnings"].extend(fetch_info["notes"])

        text, ext_info = extract_main_text(html)
        result["extract_method"] = ext_info["method"]
        result["extract_info"] = ext_info
        if not text.strip():
            raise FetchError(
                "مقدرتش أطلّع نص من الصفحة دي. غالباً المحتوى بيتحمّل بالـ JavaScript "
                "أو الصفحة مفيهاش نص. جرّبي لينك مقال أو صفحة محتوى."
            )

        words = preprocess(text)
        if not words:
            raise FetchError("النص اللي طلع مفيهوش كلمات قابلة للتحليل (عربي أو إنجليزي).")

        lang = detect_lang(text)
        result.update(
            text=text,
            longest_paragraph=_longest_line(text),
            lang=lang,
            words=words,
            total_words=len(words),
            unique_words=len(set(words)),
            keywords=count_keywords(words, n=n, top=top),
        )

        # تحذيرات الجودة
        if ext_info["method"] == "fallback":
            result["warnings"].append(
                "المكتبة الأساسية معرفتش تحدد المحتوى، فاستخدمت الطريقة الاحتياطية "
                "(أكتر container فيه فقرات). راجعي النص المستخرج."
            )
        elif ext_info["method"] == "trafilatura (short)":
            result["warnings"].append("النص المستخرج قصير، ممكن يكون ناقص.")
        if len(words) < MIN_WORDS_WARNING:
            result["warnings"].append(
                f"النص قليل ({len(words)} كلمة بعد التنضيف). غالباً الصفحة دي "
                "مش صفحة محتوى (رئيسية أو قايمة)، فالنتيجة ممكن تبقى ضعيفة."
            )
        if lang == "mixed":
            result["warnings"].append(
                "الصفحة فيها عربي وإنجليزي مع بعض، والكلمات معدودة للغتين."
            )
        result["ok"] = True

    except FetchError as e:
        result["error"] = str(e)
    except Exception as e:  # أي خطأ مش متوقع، عشان الواجهة متقعش
        result["error"] = f"حصل خطأ غير متوقع ({type(e).__name__}): {e}"
    return result


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else input("Enter URL: ")
    res = analyze(target, top=15)
    if not res["ok"]:
        print("ERROR:", res["error"])
        raise SystemExit(1)

    print(f"URL: {res['url']}")
    print(f"fetch: {res['fetch_method']} | extract: {res['extract_method']} | lang: {res['lang']}")
    print(f"words: {res['total_words']} (unique {res['unique_words']})")
    for w in res["warnings"]:
        print("WARNING:", w)
    print("\nLongest paragraph:\n", res["longest_paragraph"][:400], "\n")
    for kw, freq in res["keywords"]:
        print(f"{kw:20s} {freq}")
