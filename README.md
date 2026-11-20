# 🔥 Hot Keywords

A small tool that takes a web page URL and returns the most frequent keywords and phrases in the page's **main content**, with support for Arabic, English, and mixed-language pages.

It was built for SEO-style keyword analysis (for example on real-estate project pages), where you want to know which words a page actually repeats, without the noise from menus, footers, and ads.

## Features

- Fetches a page with `requests`, and automatically falls back to a real browser (Selenium) when the site blocks the request or renders its content with JavaScript.
- Extracts only the main content using `trafilatura`, with a custom fallback extractor when the library fails or returns too little text.
- Cleans Arabic and English text together: normalization, language-specific stop words, and web-boilerplate filtering.
- Counts single words or two-word phrases (bigrams). Bigrams never span a sentence break, punctuation mark, or removed stop word.
- Streamlit interface with a results table, bar chart, CSV download, and a view of the extracted text.
- Quality warnings when the extraction looks unreliable (fallback extractor used, very short text, mixed languages).

## Project structure

```
hotKeyWord-project/
├── keyword_tool/
│   ├── app.py            # Streamlit UI (no logic, calls analyze())
│   ├── analyzer.py       # Orchestrator: analyze(url) runs the whole pipeline
│   ├── fetcher.py        # Page fetching: requests, then Selenium fallback
│   ├── extractor.py      # Main-content extraction: trafilatura, then fallback
│   ├── nlp.py            # Text cleaning, Arabic normalization, stop words
│   ├── keywords.py       # Word / bigram counting
│   └── requirements.txt
├── TextExtractor_(1).ipynb      # Research: comparison of text-extraction libraries
└── Copy_of_Merge_(1)_(1).ipynb  # Early prototype (n-gram merging logic)
```

## How it works

```
URL -> fetcher -> extractor -> nlp -> keywords
```

1. **Fetch** (`fetcher.py`): normalizes the URL, then tries `requests` with browser-like headers and retries. If the site answers 403/406, or the page is nearly empty or looks like a captcha / access-denied page, it retries with headless Chrome through Selenium and keeps whichever version has more visible text.
2. **Extract** (`extractor.py`): runs `trafilatura`. If the result is under 80 words, it runs a fallback that collects long paragraphs, finds the deepest container holding at least 70% of their text, and keeps only its headings and paragraphs.
3. **Clean** (`nlp.py`): lowercases, normalizes Arabic (removes diacritics and tatweel, unifies alef and yaa forms), tokenizes Arabic and English words, and removes stop words per language (NLTK lists plus built-in and web-specific extras). A `None` marker is kept wherever a word was removed or a break occurred, so bigrams do not cross them.
4. **Count** (`keywords.py`): counts words or bigrams and returns the top results.
5. **Display** (`app.py`): shows metrics, warnings, table, chart, CSV download, and the extracted text. The result is kept in `st.session_state`, so changing the sliders does not re-fetch the page.

`analyze(url)` never raises to the UI. It always returns a dict with `ok`, `error`, `warnings`, and the analysis results.

## Installation

Requirements: Python 3.9+ and Google Chrome (only needed for the Selenium fallback).

```bash
git clone https://github.com/gsme-Ghada/hotKeyWord-project.git
cd hotKeyWord-project/keyword_tool
pip install -r requirements.txt
```

Notes:
- NLTK stop-word lists are downloaded automatically on first run (internet required once).
- Selenium 4.6+ downloads the matching Chrome driver automatically.

## Usage

### Web interface

```bash
streamlit run app.py
```

Paste a URL, choose the number of keywords and the counting mode (single words or bigrams), and click the analyze button.

### Command line

```bash
python analyzer.py https://en.wikipedia.org/wiki/Search_engine_optimization
```

Prints the final URL, fetch and extraction methods, language, word counts, warnings, the longest paragraph, and the top 15 keywords.

### From Python

```python
from analyzer import analyze

result = analyze("https://example.com/article", n=2, top=20)
if result["ok"]:
    print(result["keywords"])      # [(keyword, frequency), ...]
    print(result["warnings"])
else:
    print(result["error"])
```

## Deploying on Streamlit Community Cloud

1. Push the repository to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app, pick the repository and branch, and set **Main file path** to `keyword_tool/app.py`.
3. In **Advanced settings**, select the same Python version you develop with.

Notes:

- **Dependencies:** Community Cloud looks for `requirements.txt` in the entrypoint's directory first, then in the repository root, so `keyword_tool/requirements.txt` is found without moving it. Use only one dependency file.
- **Imports:** the modules sit next to `app.py`, so `from analyzer import analyze` works as it does locally.
- **NLTK data:** the stop-word lists are downloaded on the first run of each fresh container, which adds a few seconds.
- **Selenium fallback:** Chrome is not installed on Community Cloud by default. To try it, add a `packages.txt` file at the **repository root** (not inside `keyword_tool/`) containing:

  ```
  chromium
  chromium-driver
  ```

  Depending on the environment, Selenium may also need to be pointed at the system Chromium and driver paths in `fetch_rendered`. If Chrome is not available, the app still works with `requests` only: pages that need JavaScript or block plain requests will show a warning or an error instead of results.
- **Blocked requests:** Community Cloud runs on datacenter IPs, which many sites block more aggressively than a home connection, so some URLs that work locally may fail when deployed.
- **Resources:** the free tier has limited memory, and headless Chrome is heavy. Avoid running several analyses at once.
- **Repository hygiene:** add a `.gitignore` with `__pycache__/` so compiled files are not committed.

## Configuration

Most tuning values are constants at the top of each file:

| File | Constant | Meaning |
|------|----------|---------|
| `fetcher.py` | `TIMEOUT`, `MAX_BYTES` | Request timeouts and max page size (10MB) |
| `fetcher.py` | `MIN_VISIBLE_CHARS` | Below this, the page is suspected empty and Selenium is tried |
| `fetcher.py` | `BLOCK_HINTS` | Phrases that identify captcha / access-denied pages |
| `extractor.py` | `MIN_PARA_LEN`, `LINK_RATIO_MAX`, `COVERAGE`, `MIN_WORDS` | Fallback extractor thresholds (experimental values) |
| `extractor.py` | `NOISE_TAGS`, `NOISE_WORDS` | Elements and class/id words treated as non-content |
| `nlp.py` | `EXTRA_STOP_EN`, `EXTRA_STOP_AR` | Extra web-boilerplate stop words |
| `analyzer.py` | `MIN_WORDS_WARNING` | Below this many clean words, a low-content warning is shown |

## Known limitations

- **Pages that need a login, or that block even real browsers** (captcha, IP bans) cannot be analyzed.
- **Landing pages** with little prose often return too little text.
- **No stemming or lemmatization**: "مشروع" and "المشروع" are counted as separate words.
- **Egyptian-dialect stop words** are not included; the stop-word lists target Modern Standard Arabic and English.
- English words shorter than 3 letters and Arabic words shorter than 2 letters are ignored.
- The fallback extractor only looks at `<p>` elements, so content placed in plain `div` or `li` elements may be missed.
- Selenium requires Google Chrome. It works out of the box on a local machine with Chrome installed, but not on Colab, Kaggle, or Streamlit Community Cloud without extra setup (see the deployment section).

## Notebooks

- `TextExtractor_(1).ipynb`: compares ten text-extraction libraries (html-text, inscriptis, newspaper3k, justext, boilerpy3, goose3, readability-lxml, news-please, readabilipy, trafilatura) on the same pages. The app uses trafilatura.
- `Copy_of_Merge_(1)_(1).ipynb`: early prototype that adds image alt text and captions to the page text and builds long n-grams (2 to 12 words) with merging of overlapping phrases. This logic is not part of the app.

## Tech stack

Python, Streamlit, requests, BeautifulSoup, trafilatura, NLTK, pandas, Altair, Selenium.
