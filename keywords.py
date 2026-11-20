"""
keywords.py
Counts word (or phrase) frequencies and ranks them from most to least common.
"""
from collections import Counter


def make_ngrams(words, n=1):
    """n=1 single words, n=2 two-word phrases (bigrams), and so on.
    None markers are skipped, and no n-gram may contain one."""
    if n <= 1:
        return [w for w in words if w is not None]
    out = []
    for i in range(len(words) - n + 1):
        gram = words[i:i + n]
        if None not in gram:
            out.append(" ".join(gram))
    return out


def count_keywords(words, n=1, top=20):
    """
    words: list of clean words (the output of preprocess)
    n:     1 = single words | 2 = bigrams
    top:   number of results
    Returns [(keyword, frequency), ...] sorted in descending order.

    Note: bigrams are built from the words after stop words are removed,
    so two words that were not adjacent in the original sentence can end up
    as one phrase. => i handled it by add none where i deleted the stop_words.
    """
    return Counter(make_ngrams(words, n)).most_common(top)