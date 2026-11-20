import re
from collections import defaultdict

import trafilatura
from bs4 import BeautifulSoup

# Settings

MIN_PARA_LEN = 80      # minimum paragraph length to count when picking the container
LINK_RATIO_MAX = 0.5   # ignore paragraphs where more than half the text is links
COVERAGE = 0.7         # the container must hold 70% of the long-paragraph text
MIN_WORDS = 80         # if the output has fewer words, treat it as incomplete and try the fallback


NOISE_TAGS = ["script", "style", "noscript", "nav", "footer",
              "header", "aside", "form", "iframe"]


# Do NOT add words like widget or menu here: many sites use them for real content
NOISE_WORDS = {
    "comment", "comments", "sidebar", "related", "promo", "share", "sharing",
    "social", "advert", "ads", "banner", "cookie", "newsletter", "breadcrumb",
}


# trafilatura
def extract_with_library(html):
    """Returns the main text, or None if trafilatura could not extract it."""
    try:
        text = trafilatura.extract(
            html,
            include_comments=False,   
            include_tables=False,     
            favor_recall=True,        
        )
    except Exception:
        return None
    return text or None


# Fallback
def _is_noisy(tag, levels=1):
    """
    Does the tag, or its direct parent, have a whole noise word in its id/class?
    The name is split on - and _ and whitespace, and each part is compared
    against the set, so comment-list matches but commentary does not.
    Only the paragraph and its parent are checked, so a distant wrapper
    like with-sidebar does not throw away the article.
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

    total = len(tag.get_text(strip=True))
    if total == 0:
        return 1.0
    links = sum(len(a.get_text(strip=True)) for a in tag.find_all("a"))
    return links / total


def _depth(tag):
    return len(list(tag.parents))


def extract_fallback(html):
    """
    Returns (text, info) or (None, None).

    Steps:
    1. Remove non-content tags.
    2. Collect only long paragraphs 
    3. For each container, sum the length of the paragraphs beneath it.
    4. Candidates = containers holding >= 70% of the total paragraph text.
    5. Pick the deepest one (i.e. the smallest), so we don't pick an outer
       div that wraps the whole page.
    6. Pull only paragraphs and headings from it.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(NOISE_TAGS):
        t.decompose()

    # 2) Clean long paragraphs
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

    # 3) Sum of paragraph text under each container
    score, nodes = defaultdict(int), {}
    for p, n in paras:
        for anc in p.parents:
            if anc.name in (None, "[document]"):
                break
            score[id(anc)] += n
            nodes[id(anc)] = anc

    # 4 + 5) Pick the deepest container covering COVERAGE of the text
    candidates = [nodes[k] for k, s in score.items() if s >= COVERAGE * total]
    if not candidates:
        return None, None
    container = max(candidates, key=lambda c: (_depth(c), score[id(c)]))

    # 6) Pull only paragraphs and headings from the winning container
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


# Main function
def extract_main_text(html):
    """
    Returns (text, info). info includes "method" so you can tell which path ran:
    trafilatura / fallback / trafilatura (short) / none
    """
    lib_text = extract_with_library(html)
    lib_words = len(lib_text.split()) if lib_text else 0

    # Normal case: trafilatura succeeded and returned enough text
    if lib_words >= MIN_WORDS:
        return lib_text, {"method": "trafilatura"}

    # It failed or the text is short: try the fallback
    fb_text, fb_info = extract_fallback(html)
    fb_words = len(fb_text.split()) if fb_text else 0

    if fb_words > lib_words:
        return fb_text, {"method": "fallback", **fb_info}
    if lib_text:
        return lib_text, {"method": "trafilatura (short)"}
    return "", {"method": "none"}