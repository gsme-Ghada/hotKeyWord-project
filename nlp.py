import re
from functools import lru_cache


_TOKEN = re.compile(r"[\u0621-\u064A]{2,}|[a-z]{3,}")

# Extra stop words
# Web words that repeat on every site and have no value as keywords
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

# Small built-in lists, used if nltk is not installed or its data is missing
_FALLBACK_EN = set(
    "the and for that with this are from was were have has had not but you "
    "your all can her his its our out their there they them these those "
    "what which when where who will would been being into than then more "
    "most some such only over very just about after before between during "
    "each other any both few own same too how why".split()
)
_FALLBACK_AR = {
    "في", "من", "على", "الى", "ان", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "الذين", "هو", "هي", "هم", "كان", "كانت", "يكون", "ما",
    "لا", "لم", "لن", "قد", "او", "ثم", "كل", "بين", "عند", "مع", "هنا",
    "هناك", "كما", "اي", "اذا", "حتى", "لكن", "بعض", "غير", "عن", "منذ",
}


# Language
def detect_lang(text):
    """'ar' | 'en' | 'mixed' | 'unknown', based on the Arabic-to-English letter ratio."""
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
    """Unify letter forms: strip diacritics and tatweel, unify alef and yaa variants."""
    text = re.sub(r"[\u064B-\u0652\u0670\u0640]", "", text)  
    text = re.sub(r"[إأآٱ]", "ا", text)
    return text.replace("ى", "ي")


# Stop words
@lru_cache(maxsize=None)
def _nltk_words(lang_name):
    """nltk list (downloaded on first use if missing). Returns an empty set on failure."""
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
    lang: 'en' or 'ar'. Returns a frozenset.
    Important: for Arabic we apply normalize_ar to the list as well,
    otherwise a word written with a hamza-alef form in the list would not
    match its plain-alef form in the text after cleaning.
    """
    if lang == "ar":
        raw = set(_nltk_words("arabic")) | _FALLBACK_AR | EXTRA_STOP_AR
        return frozenset(normalize_ar(w) for w in raw)
    return frozenset(set(_nltk_words("english")) | _FALLBACK_EN | EXTRA_STOP_EN)


# Cleaning
def tokenize(text):
    """Lowercase + Arabic normalization + split into words (no digits or symbols)."""
    text = normalize_ar(text.lower())
    return _TOKEN.findall(text)


def preprocess(text):
    """Text -> list of clean words (in the same order they appear in the text)."""
    ar_stop = get_stopwords("ar")
    en_stop = get_stopwords("en")
    words = []
    for w in tokenize(text):
        is_arabic = "\u0621" <= w[0] <= "\u064A"
        if w not in (ar_stop if is_arabic else en_stop):
            words.append(w)
    return words


# Words, or any run of symbols/digits, or a newline (all non-word things become breaks)
_TOKEN_BRK = re.compile(r"[\u0621-\u064A]+|[a-z]+|[^\s\u0621-\u064Aa-z]+|\n")


def preprocess_with_breaks(text):
    """
    Like preprocess, but keeps a None marker wherever a word was removed
    (stop word, too short) or a break occurred (punctuation, digits, symbols,
    newline), so n-grams never span them.
    """
    ar_stop = get_stopwords("ar")
    en_stop = get_stopwords("en")
    out = []
    for w in _TOKEN_BRK.findall(normalize_ar(text.lower())):
        is_arabic = "\u0621" <= w[0] <= "\u064A"
        is_english = "a" <= w[0] <= "z"
        if is_arabic:
            out.append(None if len(w) < 2 or w in ar_stop else w)
        elif is_english:
            out.append(None if len(w) < 3 or w in en_stop else w)
        else:
            out.append(None)   # digits, punctuation, symbols
    return out