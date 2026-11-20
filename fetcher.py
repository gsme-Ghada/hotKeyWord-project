import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Settings
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.google.com/",
}
TIMEOUT = (6, 15)                 # (connect, read) in seconds
MAX_BYTES = 10 * 1024 * 1024      
MIN_VISIBLE_CHARS = 500

BLOCK_HINTS = [
    "captcha", "access denied", "just a moment", "verify you are human",
    "enable javascript", "unusual traffic", "are you a robot",
]


class FetchError(Exception):
    """Final failure. The message is written for the end user."""


class BlockedError(Exception):
    """The site refused the request (403/406). A real browser may get through."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


# URL
def normalize_url(url):
    """Add https:// if missing, and raise FetchError if the URL is invalid."""
    url = (url or "").strip()
    if not url:
        raise FetchError("Please enter a URL first.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("The URL must start with http or https.")
    host = parsed.hostname or ""
    if not host or ("." not in host and host != "localhost"):
        raise FetchError("The URL looks invalid. Check the site name (e.g. example.com).")
    return url


# requests
def _make_session():
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=False,
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


def fetch_html(url):
    """Return the HTML as bytes (to keep Arabic intact), or raise FetchError/BlockedError."""
    try:
        r = _make_session().get(url, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        raise FetchError("The site is slow and did not respond in time. Try again in a bit.")
    except requests.exceptions.SSLError:
        raise FetchError("The site has a problem with its security certificate (SSL).")
    except requests.exceptions.TooManyRedirects:
        raise FetchError("The site keeps redirecting in a loop (redirect loop).")
    except requests.exceptions.ConnectionError:
        raise FetchError("Could not reach the site. Check the URL and your internet connection.")
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Connection error: {type(e).__name__}")

    code = r.status_code
    if code in (403, 406):
        raise BlockedError(code)
    if code == 401:
        raise FetchError("This page requires login (401).")
    if code in (404, 410):
        raise FetchError("This page does not exist (404). Check the URL.")
    if code == 429:
        raise FetchError("The site is rate-limiting requests (429). Wait a bit and try again.")
    if code >= 400:
        raise FetchError(f"The site returned error {code}.")

    ctype = r.headers.get("Content-Type", "").lower()
    if ctype and "html" not in ctype:
        raise FetchError(
            "This link is not a web page (it may be a PDF, image, or file). "
            "The tool only works on HTML pages."
        )
    if len(r.content) > MAX_BYTES:
        raise FetchError("The page is too large (over 10MB).")
    return r.content


# 3) Selenium
def fetch_rendered(url, wait_seconds=3):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        raise FetchError("Selenium is not installed (pip install selenium).")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument(f"--user-agent={USER_AGENT}")

    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(30)
        driver.get(url)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(wait_seconds)  # short wait for content that loads after the page load event
        html = driver.page_source
    except Exception as e:
        raise FetchError(
            f"The browser (Selenium) could not open the page ({type(e).__name__}). "
            "Make sure Google Chrome is installed."
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return html.encode("utf-8")


# 4) Checks
def visible_text(html):
    """The visible text of the page (without script/style)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


def looks_blocked(text):
    """Short page containing captcha or access denied (a block served with status 200)."""
    t = text.lower()
    return len(t) < 1500 and any(h in t for h in BLOCK_HINTS)


def needs_fallback(html):
    """Is the page almost empty (JS-rendered) or a block page?"""
    text = visible_text(html)
    return len(text) < MIN_VISIBLE_CHARS or looks_blocked(text)


# 5) Orchestrator
def get_page(url):
    """
    Return (html_bytes, info).
    info = {"url": normalized URL, "method": "requests" | "selenium", "notes": [...]}
    Raises FetchError with a clear message if the page could not be fetched.
    """
    url = normalize_url(url)
    notes = []
    method = "requests"

    try:
        html = fetch_html(url)
    except BlockedError as blocked:
        # The site refused requests: try a real browser
        try:
            html = fetch_rendered(url)
            method = "selenium"
        except FetchError as e:
            raise FetchError(
                f"The site refused access (HTTP {blocked.code}) and a browser could not open it either. {e}"
            )

    if method == "requests" and needs_fallback(html):
        # Page is empty or blocked: check whether a browser returns more content
        try:
            rendered = fetch_rendered(url)
            if len(visible_text(rendered)) > len(visible_text(html)):
                html, method = rendered, "selenium"
        except FetchError as e:
            notes.append(
                "The page seems to load its content with JavaScript or is blocking requests, "
                f"and a real browser could not be tried: {e}"
            )

    if looks_blocked(visible_text(html)):
        raise FetchError(
            "The site is blocking the tool (captcha or Access Denied page). "
            "Try a different URL."
        )
    return html, {"url": url, "method": method, "notes": notes}