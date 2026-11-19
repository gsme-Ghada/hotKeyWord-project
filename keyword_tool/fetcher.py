"""
fetcher.py
جلب صفحة الويب من اللينك.

الترتيب:
1) requests (سريع وخفيف)
2) لو الموقع رفض (403/406) أو الصفحة طلعت فاضية/حجب -> Selenium (متصفح حقيقي)

الاستخدام:
    html, info = get_page("example.com/article")
    # html: bytes  |  info: {"url", "method", "notes"}
"""
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------- الإعدادات
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.9",
    # من غير br: requests مش بتفك brotli من غير مكتبة إضافية
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.google.com/",
}
TIMEOUT = (6, 15)                 # (connect, read) بالثواني
MAX_BYTES = 10 * 1024 * 1024      # أكبر صفحة نقبلها: 10MB
MIN_VISIBLE_CHARS = 500           # أقل من كده نشك إن الصفحة فاضية (JS)

BLOCK_HINTS = [
    "captcha", "access denied", "just a moment", "verify you are human",
    "enable javascript", "unusual traffic", "are you a robot",
]


class FetchError(Exception):
    """فشل نهائي، الرسالة مكتوبة للمستخدم."""


class BlockedError(Exception):
    """الموقع رفض الطلب (403/406). ممكن متصفح حقيقي يعدّيها."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


# ---------------------------------------------------------------- 1) اللينك
def normalize_url(url):
    """بتضيف https:// لو ناقصة، وبترفع FetchError لو اللينك مش سليم."""
    url = (url or "").strip()
    if not url:
        raise FetchError("اكتبي اللينك الأول.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError("اللينك لازم يبدأ بـ http أو https.")
    host = parsed.hostname or ""
    if not host or ("." not in host and host != "localhost"):
        raise FetchError("اللينك شكله غلط، اتأكدي من اسم الموقع (مثال: example.com).")
    return url


# ---------------------------------------------------------------- 2) requests
def _make_session():
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        # مش بنستنى Retry-After: موقع ممكن يبعت 3600 ثانية ويعلّق الأداة
        respect_retry_after_header=False,
        # بعد ما المحاولات تخلص نرجع آخر response ونتعامل معاه إحنا
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


def fetch_html(url):
    """بترجّع الـ HTML كـ bytes (عشان العربي)، أو بترفع FetchError/BlockedError."""
    try:
        r = _make_session().get(url, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        raise FetchError("الموقع بطيء ومردّش في الوقت المحدد. جرّبي تاني بعد شوية.")
    except requests.exceptions.SSLError:
        raise FetchError("في مشكلة في شهادة الأمان (SSL) بتاعة الموقع.")
    except requests.exceptions.TooManyRedirects:
        raise FetchError("الموقع بيحوّلك من لينك للتاني في دايرة (redirect loop).")
    except requests.exceptions.ConnectionError:
        raise FetchError("مقدرتش أوصل للموقع. اتأكدي من اللينك ومن النت.")
    except requests.exceptions.RequestException as e:
        raise FetchError(f"حصل خطأ في الاتصال: {type(e).__name__}")

    code = r.status_code
    if code in (403, 406):
        raise BlockedError(code)
    if code == 401:
        raise FetchError("الصفحة دي محتاجة تسجيل دخول (401).")
    if code in (404, 410):
        raise FetchError("الصفحة دي مش موجودة (404). اتأكدي من اللينك.")
    if code == 429:
        raise FetchError("الموقع بيحدّ عدد الطلبات (429). استني شوية وجرّبي تاني.")
    if code >= 400:
        raise FetchError(f"الموقع رجّع خطأ {code}.")

    ctype = r.headers.get("Content-Type", "").lower()
    if ctype and "html" not in ctype:
        raise FetchError(
            "اللينك ده مش صفحة ويب (ممكن PDF أو صورة أو ملف). "
            "الأداة بتشتغل على صفحات HTML بس."
        )
    if len(r.content) > MAX_BYTES:
        raise FetchError("الصفحة كبيرة جداً (أكتر من 10MB).")
    return r.content


# ---------------------------------------------------------------- 3) Selenium
def fetch_rendered(url, wait_seconds=3):
    """
    بتفتح الصفحة في Chrome حقيقي (headless) وبترجّع الـ HTML بعد ما الـ JavaScript يشتغل.
    محتاجة: pip install selenium + Google Chrome متسطّب على الجهاز.
    (Selenium 4.6+ بينزّل الـ driver لوحده.)
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        raise FetchError("Selenium مش متسطّب (pip install selenium).")

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
        time.sleep(wait_seconds)  # وقت بسيط للمحتوى اللي بيتحمّل بعد الـ load
        html = driver.page_source
    except Exception as e:
        raise FetchError(
            f"المتصفح (Selenium) مقدرش يفتح الصفحة ({type(e).__name__}). "
            "اتأكدي إن Google Chrome متسطّب."
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return html.encode("utf-8")


# ---------------------------------------------------------------- 4) الفحص
def visible_text(html):
    """النص الظاهر في الصفحة (من غير script/style)."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


def looks_blocked(text):
    """صفحة قصيرة فيها captcha أو access denied (حجب بكود 200)."""
    t = text.lower()
    return len(t) < 1500 and any(h in t for h in BLOCK_HINTS)


def needs_fallback(html):
    """الصفحة فاضية تقريباً (JS) أو صفحة حجب؟"""
    text = visible_text(html)
    return len(text) < MIN_VISIBLE_CHARS or looks_blocked(text)


# ---------------------------------------------------------------- 5) المايسترو
def get_page(url):
    """
    بترجّع (html_bytes, info).
    info = {"url": اللينك بعد التظبيط, "method": "requests" | "selenium", "notes": [...]}
    وبترفع FetchError برسالة واضحة لو معرفتش تجيب الصفحة.
    """
    url = normalize_url(url)
    notes = []
    method = "requests"

    try:
        html = fetch_html(url)
    except BlockedError as blocked:
        # الموقع رفض requests: نجرب متصفح حقيقي
        try:
            html = fetch_rendered(url)
            method = "selenium"
        except FetchError as e:
            raise FetchError(
                f"الموقع رفض الوصول (HTTP {blocked.code}) ومقدرتش أفتحه بمتصفح كمان. {e}"
            )

    if method == "requests" and needs_fallback(html):
        # الصفحة فاضية أو حجب: نجرب نشوف هل المتصفح بيجيب محتوى أكتر
        try:
            rendered = fetch_rendered(url)
            if len(visible_text(rendered)) > len(visible_text(html)):
                html, method = rendered, "selenium"
        except FetchError as e:
            notes.append(
                "الصفحة شكلها بتحمّل المحتوى بالـ JavaScript أو فيها حجب، "
                f"ومقدرتش أجرب متصفح حقيقي: {e}"
            )

    if looks_blocked(visible_text(html)):
        raise FetchError(
            "الموقع حاجب الأداة (صفحة captcha أو Access Denied). "
            "جرّبي لينك تاني."
        )
    return html, {"url": url, "method": method, "notes": notes}
