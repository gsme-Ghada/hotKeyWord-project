"""
analyzer.py
The only function the UI calls: analyze(url).

URL -> get_page -> extract_main_text -> detect_lang -> preprocess_with_breaks -> count_keywords

"""
from extractor import extract_main_text
from fetcher import FetchError, get_page
from keywords import count_keywords
from nlp import detect_lang, preprocess_with_breaks

MIN_WORDS_WARNING = 100   # below this, warn that the page is probably not a content page


def _longest_line(text):
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return max(lines, key=len) if lines else ""


def analyze(url, n=1, top=20):
    """
    Always returns a dict (never raises exceptions to the UI):
      ok, error, url, lang, fetch_method, extract_method, extract_info,
      text, longest_paragraph, words, total_words, unique_words,
      keywords [(kw, freq)], warnings [str]
    If ok = False, the message is in error.
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
                "Could not extract any text from this page. The content is "
                "probably loaded with JavaScript, or the page has no text. "
                "Try an article or content page link."
            )

        words = preprocess_with_breaks(text)
        clean = [w for w in words if w]
        if not clean:
            raise FetchError("The extracted text has no analyzable words (Arabic or English).")

        lang = detect_lang(text)
        result.update(
            text=text,
            longest_paragraph=_longest_line(text),
            lang=lang,
            words=words,
            total_words=len(clean),
            unique_words=len(set(clean)),
            keywords=count_keywords(words, n=n, top=top),
        )

        # Quality warnings
        if ext_info["method"] == "fallback":
            result["warnings"].append(
                "The main library could not locate the content, so the fallback "
                "method was used (the container with the most paragraphs). "
                "Please review the extracted text."
            )
        elif ext_info["method"] == "trafilatura (short)":
            result["warnings"].append("The extracted text is short and may be incomplete.")
        if len(clean) < MIN_WORDS_WARNING:
            result["warnings"].append(
                f"Very little text ({len(clean)} words after cleaning). This is "
                "probably not a content page (homepage or listing), so the "
                "result may be weak."
            )
        if lang == "mixed":
            result["warnings"].append(
                "The page mixes Arabic and English, and words are counted for both languages."
            )
        result["ok"] = True

    except FetchError as e:
        result["error"] = str(e)
    except Exception as e:  # any unexpected error, so the UI never crashes
        result["error"] = f"Unexpected error ({type(e).__name__}): {e}"
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