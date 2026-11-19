"""
keywords.py
عدّ تكرار الكلمات (أو العبارات) وترتيبها من الأكتر للأقل.
"""
from collections import Counter


def make_ngrams(words, n=1):
    """n=1 كلمات مفردة، n=2 عبارات من كلمتين (bigrams)، وهكذا."""
    if n <= 1:
        return list(words)
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def count_keywords(words, n=1, top=20):
    """
    words: قايمة كلمات نضيفة (ناتج preprocess)
    n:     1 = كلمات مفردة | 2 = bigrams
    top:   عدد النتايج
    بترجّع [(keyword, frequency), ...] مرتبة تنازلياً.

    ملحوظة: الـ bigrams بتتكوّن من الكلمات بعد شيل الـ stop words،
    فممكن كلمتين مش جنب بعض في الجملة الأصلية يطلعوا عبارة واحدة.
    """
    return Counter(make_ngrams(words, n)).most_common(top)
