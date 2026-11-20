# 🔥 Hot Keywords

Paste a web page URL and get the most frequent keywords and phrases in its **main content**. Supports Arabic, English, and mixed-language pages.

**Live demo:** [https://YOUR-APP-NAME.streamlit.app](https://YOUR-APP-NAME.streamlit.app)

## Features

- Fetches pages with `requests`, with an automatic Selenium (real browser) fallback for blocked or JavaScript-rendered sites.
- Extracts only the main content with `trafilatura`, plus a custom fallback extractor.
- Cleans Arabic and English text together: normalization, language-specific stop words, and web-boilerplate filtering.
- Counts single words or bigrams. Bigrams never cross punctuation, sentence breaks, or removed stop words.
- Streamlit UI with table, bar chart, CSV download, and the extracted text.

## Project structure

```
.
├── app.py            # Streamlit UI
├── analyzer.py       # analyze(url): runs the whole pipeline
├── fetcher.py        # Page fetching: requests, then Selenium fallback
├── extractor.py      # Main-content extraction: trafilatura, then fallback
├── nlp.py            # Text cleaning, Arabic normalization, stop words
├── keywords.py       # Word / bigram counting
└── requirements.txt
```

## How it works

```
URL -> fetcher -> extractor -> nlp -> keywords -> app
```

1. **Fetch:** `requests` with browser-like headers. On a 403/406, an empty page, or a captcha page, it retries in headless Chrome (Selenium).
2. **Extract:** `trafilatura`; if the result is under 80 words, a fallback picks the deepest container holding most of the long paragraphs.
3. **Clean:** lowercase, Arabic normalization, per-language stop words. Removed words leave a break marker so bigrams don't span them.
4. **Count:** top N words or bigrams.
5. **Display:** metrics, warnings, table, chart, CSV download.

`analyze(url)` never raises to the UI; it always returns a dict with `ok`, `error`, `warnings`, and the results.

## Run locally

Requires Python 3.9+. Google Chrome is only needed for the Selenium fallback.

```bash
git clone https://github.com/gsme-Ghada/hotKeyWord-project.git
cd hotKeyWord-project
pip install -r requirements.txt
streamlit run app.py
```

Command line:

```bash
python analyzer.py https://en.wikipedia.org/wiki/Search_engine_optimization
```

## Known limitations

- Pages behind a login, or that block even real browsers (captcha, IP bans), can't be analyzed.
- Landing pages with little text often return too little content.
- No stemming or lemmatization: "مشروع" and "المشروع" are counted separately.
- Stop words target Modern Standard Arabic and English, not Egyptian dialect.
- The Selenium fallback needs Chrome, so it may not work on the hosted demo. Some sites that work locally may be blocked there.

## Tech stack

Python, Streamlit, requests, BeautifulSoup, trafilatura, NLTK, pandas, Altair, Selenium.