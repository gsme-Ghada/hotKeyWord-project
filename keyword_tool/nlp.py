"""
nlp.py
تنضيف النص وتحويله لقايمة كلمات نضيفة.

الفكرة: بنقرا النص بالترتيب ونطلّع كلمات عربي (حروف عربي) وكلمات إنجليزي (a-z)،
ولكل كلمة بنطبّق قايمة الـ stop words بتاعة لغتها. كده الصفحة المختلطة
(عربي + إنجليزي) بتتعامل صح من غير ما نحتاج نقرر لغة واحدة للصفحة كلها.
detect_lang بتستخدم للعرض والتنبيهات بس.
"""
import re
from functools import lru_cache


_TOKEN = re.compile(r"[\u0621-\u064A]{2,}|[a-z]{3,}")

# ------------------------------------------------- stop words إضافية
# كلمات web بتتكرر في أي موقع ومالهاش قيمة كـ keywords
EXTRA_STOP_EN = {
    "click", "read", "share", "subscribe", "newsletter", "cookie", "cookies",
    "privacy", "policy", "terms", "login", "signup", "sign", "menu", "home",
    "contact", "copyright", "reserved", "rights", "also", "like", "get",
    "one", "may", "can", "will", "would", "could", "use", "used", "using",
    "via", "per", "etc",
}
EXTRA_STOP_AR = {
    "اقرا", "المزيد", "اشترك", "اشتراك", "تسجيل", "الدخول", "الرئيسية",
    "اتصل", "شارك", "مشاركة", "حقوق", "النشر", "محفوظة", "سياسة",
    "الخصوصية", "الشروط", "والاحكام", "ايضا", "كما", "حيث", "بعد", "قبل",
}

# قايمة صغيرة مدمجة، تستخدم لو nltk مش متسطّبة أو ملقتش البيانات
_FALLBACK_EN = set(
    "the and for that with this are from was were have has had not but you "
    "your all can her his its our out their there they them these those "
    "what which when where who will would been being into than then more "
    "most some such only over very just about after before between during "
    "each other any both few own same too how why".split()
)
_FALLBACK_AR = {
    "في", "من", "على", "الى", "عن", "ان", "ان", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "الذين", "هو", "هي", "هم", "كان", "كانت", "يكون", "ما",
    "لا", "لم", "لن", "قد", "او", "ثم", "كل", "بين", "عند", "مع", "هنا",
    "هناك", "كما", "اي", "اذا", "حتى", "لكن", "بعض", "غير", "عن", "منذ",
}


# ---------------------------------------------------------------- اللغة
def detect_lang(text):
    """'ar' | 'en' | 'mixed' | 'unknown' حسب نسبة الحروف العربي للإنجليزي."""
    ar = len(re.findall(r"[\u0600-\u06FF]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    total = ar + en
    if total == 0:
        return "unknown"
    ratio = ar / total
    if ratio > 0.7:
        return "ar"
    if ratio < 0.3:
        return "en"
    return "mixed"


def normalize_ar(text):
    """توحيد الشكل: بنشيل التشكيل والتطويل، ونوحّد الألف والياء."""
    text = re.sub(r"[\u064B-\u0652\u0670\u0640]", "", text)  # تشكيل + تطويل
    text = re.sub(r"[إأآٱ]", "ا", text)
    return text.replace("ى", "ي")


# ---------------------------------------------------------------- stop words
@lru_cache(maxsize=None)
def _nltk_words(lang_name):
    """قايمة nltk (وبتنزّلها أول مرة لو مش موجودة). لو فشلت بنرجّع set فاضية."""
    try:
        from nltk.corpus import stopwords
        try:
            return frozenset(stopwords.words(lang_name))
        except LookupError:
            import nltk
            nltk.download("stopwords", quiet=True)
            return frozenset(stopwords.words(lang_name))
    except Exception:
        return frozenset()


@lru_cache(maxsize=None)
def get_stopwords(lang):
    """
    lang: 'en' أو 'ar'. بترجّع set.
    مهم: في العربي بنطبّق normalize_ar على القايمة كمان،
    وإلا "إلى" في القايمة مش هتطابق "الى" في النص بعد التنضيف.
    """
    if lang == "ar":
        raw = set(_nltk_words("arabic")) | _FALLBACK_AR | EXTRA_STOP_AR
        return frozenset(normalize_ar(w) for w in raw)
    return frozenset(set(_nltk_words("english")) | _FALLBACK_EN | EXTRA_STOP_EN)


# ---------------------------------------------------------------- التنضيف
def tokenize(text):
    """lowercase + normalize عربي + تقطيع لكلمات (من غير أرقام ورموز)."""
    text = normalize_ar(text.lower())
    return _TOKEN.findall(text)


def preprocess(text):
    """النص ← قايمة كلمات نضيفة (بنفس ترتيب ظهورها في النص)."""
    ar_stop = get_stopwords("ar")
    en_stop = get_stopwords("en")
    words = []
    for w in tokenize(text):
        is_arabic = "\u0621" <= w[0] <= "\u064A"
        if w not in (ar_stop if is_arabic else en_stop):
            words.append(w)
    return words
