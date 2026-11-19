"""
extractor.py
استخراج المحتوى الأساسي من صفحة HTML.

الترتيب:
1) trafilatura  -> الطريقة الأساسية
2) extract_fallback -> لو trafilatura رجّعت None أو نص قصير
   الفكرة: ندوّر على "أقل container" بيجمّع أغلب الفقرات الطويلة في الصفحة.

الاستخدام:
    text, info = extract_main_text(html)   # html ممكن يكون bytes أو str
"""
import re
from collections import defaultdict

import trafilatura
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- الإعدادات
# كلها أرقام تجريبية، اضبطيها بعد ما تجربي على مواقع حقيقية.
MIN_PARA_LEN = 80      # أقل طول لفقرة تتحسب في اختيار الـ container
LINK_RATIO_MAX = 0.5   # لو أكتر من نص الفقرة لينكات، نتجاهلها
COVERAGE = 0.7         # الـ container لازم يحتوي 70% من نص الفقرات الطويلة
MIN_WORDS = 80         # لو النص الناتج أقل من كده نعتبره ناقص ونجرب الفالباك

# tags مش محتوى، بنشيلها قبل أي حاجة
NOISE_TAGS = ["script", "style", "noscript", "nav", "footer",
              "header", "aside", "form", "iframe"]

# كلمات (كاملة) في id/class بتدل غالباً على noise. إشارة مساعدة بس.
# متحطّيش هنا كلمات زي widget أو menu: مواقع كتير بتستخدمها للمحتوى الحقيقي
# (Elementor مثلاً بيسمّي الـ wrapper بتاع النصوص elementor-widget-container).
NOISE_WORDS = {
    "comment", "comments", "sidebar", "related", "promo", "share", "sharing",
    "social", "advert", "ads", "banner", "cookie", "newsletter", "breadcrumb",
}


# ------------------------------------------------------- 1) trafilatura
def extract_with_library(html):
    """بترجّع النص الأساسي، أو None لو trafilatura معرفتش تطلعه."""
    try:
        text = trafilatura.extract(
            html,
            include_comments=False,   # من غير التعليقات
            include_tables=False,     # من غير الجداول
            favor_recall=True,        # الأفضل ناخد نص أكتر من إننا نضيّع جزء
        )
    except Exception:
        return None
    return text or None


# ------------------------------------------------------- 2) الفالباك
def _is_noisy(tag, levels=1):
    """
    هل الـ tag أو أبوه المباشر اسمه (id/class) فيه كلمة noise كاملة؟
    بنقسّم الاسم عند - و _ والمسافات ونقارن كل جزء بالقايمة،
    فـ comment-list يطابق لكن commentary لأ.
    وبنبص على الفقرة وأبوها بس، عشان wrapper بعيد زي with-sidebar ميرميش المقال.
    """
    el = tag
    for _ in range(levels + 1):
        if el is None or el.name in (None, "[document]", "html", "body"):
            break
        ident = " ".join([el.get("id") or "", *(el.get("class") or [])])
        if set(re.split(r"[-_\s]+", ident.lower())) & NOISE_WORDS:
            return True
        el = el.parent
    return False


def _link_ratio(tag):
    """نسبة النص اللي جوه <a> من نص الـ tag كله."""
    total = len(tag.get_text(strip=True))
    if total == 0:
        return 1.0
    links = sum(len(a.get_text(strip=True)) for a in tag.find_all("a"))
    return links / total


def _depth(tag):
    return len(list(tag.parents))


def extract_fallback(html):
    """
    بترجّع (text, info) أو (None, None).

    الخطوات:
    1. نشيل الـ tags اللي مش محتوى.
    2. نجمع الفقرات الطويلة بس (مش قايمة لينكات، ومش في كتلة noise).
    3. لكل container (الأب وكل أجداده) نحسب مجموع طول الفقرات اللي تحته.
    4. المرشحين = الـ containers اللي تحتها >= 70% من إجمالي الفقرات.
    5. نختار الأعمق (يعني الأصغر)، فمنختارش div خارجي شايل الصفحة كلها.
    6. نسحب منه الفقرات والعناوين بس.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(NOISE_TAGS):
        t.decompose()

    # 2) الفقرات الطويلة النضيفة
    paras = []
    for p in soup.find_all("p"):
        n = len(p.get_text(" ", strip=True))
        if n < MIN_PARA_LEN:
            continue
        if _link_ratio(p) > LINK_RATIO_MAX:
            continue
        if _is_noisy(p):
            continue
        paras.append((p, n))

    if not paras:
        return None, None

    total = sum(n for _, n in paras)

    # 3) مجموع الفقرات تحت كل container
    score, nodes = defaultdict(int), {}
    for p, n in paras:
        for anc in p.parents:
            if anc.name in (None, "[document]"):
                break
            score[id(anc)] += n
            nodes[id(anc)] = anc

    # 4 + 5) نختار أعمق container بيغطي COVERAGE من النص
    candidates = [nodes[k] for k, s in score.items() if s >= COVERAGE * total]
    if not candidates:
        return None, None
    container = max(candidates, key=lambda c: (_depth(c), score[id(c)]))

    # 6) نسحب الفقرات والعناوين بس من الـ container الفايز
    parts = []
    for el in container.find_all(["h1", "h2", "h3", "p"]):
        txt = el.get_text(" ", strip=True)
        if not txt or _is_noisy(el):
            continue
        if el.name == "p" and (len(txt) < 30 or _link_ratio(el) > LINK_RATIO_MAX):
            continue
        parts.append(txt)

    text = "\n\n".join(parts)
    info = {
        "tag": container.name,
        "id": container.get("id"),
        "class": container.get("class"),
        "long_paragraphs": len(paras),
        "chars": len(text),
    }
    return text, info


# ------------------------------------------------------- الدالة الرئيسية
def extract_main_text(html):
    """
    بترجّع (text, info). الـ info فيها method عشان تعرفي مين اللي اشتغل:
    trafilatura / fallback / trafilatura (short) / none
    """
    lib_text = extract_with_library(html)
    lib_words = len(lib_text.split()) if lib_text else 0

    # الحالة الطبيعية: trafilatura نجحت ورجّعت نص كفاية
    if lib_words >= MIN_WORDS:
        return lib_text, {"method": "trafilatura"}

    # فشلت أو النص قصير: نجرب الفالباك
    fb_text, fb_info = extract_fallback(html)
    fb_words = len(fb_text.split()) if fb_text else 0

    if fb_words > lib_words:
        return fb_text, {"method": "fallback", **fb_info}
    if lib_text:
        return lib_text, {"method": "trafilatura (short)"}
    return "", {"method": "none"}
