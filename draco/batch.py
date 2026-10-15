"""Batch download pattern expansion.

Supports bracket ranges anywhere in a URL (several may be combined):
    http://site/img[001-120].jpg     numbers, zero padding kept from the start value
    http://site/part[a-f].rar        letters
and the "*" wildcard with explicit parameters via expand_wildcard().
"""

import itertools
import re

_BRACKET = re.compile(r"\[([0-9]+|[a-zA-Z])-([0-9]+|[a-zA-Z])(?::(\d+))?\]")
MAX_URLS = 10000


def _range_values(a, b, step=1):
    if a.isdigit() and b.isdigit():
        width = len(a) if a.startswith("0") and len(a) > 1 else 0
        lo, hi = int(a), int(b)
        rng = range(lo, hi + 1, step) if lo <= hi else range(lo, hi - 1, -step)
        return [str(v).zfill(width) for v in rng]
    if a.isalpha() and b.isalpha() and len(a) == len(b) == 1:
        lo, hi = ord(a), ord(b)
        rng = range(lo, hi + 1, step) if lo <= hi else range(lo, hi - 1, -step)
        return [chr(v) for v in rng]
    raise ValueError(f"bad range [{a}-{b}]")


def expand_pattern(pattern):
    parts = _BRACKET.split(pattern)
    # split gives: text, a, b, step, text, a, b, step, text ...
    texts = parts[0::4]
    ranges = []
    for i in range(1, len(parts), 4):
        ranges.append(_range_values(parts[i], parts[i + 1], int(parts[i + 2] or 1)))
    if not ranges:
        return [pattern]
    out = []
    for combo in itertools.product(*ranges):
        s = texts[0]
        for val, txt in zip(combo, texts[1:]):
            s += val + txt
        out.append(s)
        if len(out) >= MAX_URLS:
            break
    return out


def expand_wildcard(pattern, start, end, width=0, letters=False):
    """Replace a single '*' with start..end (numbers or letters)."""
    if "*" not in pattern:
        return [pattern]
    if letters:
        vals = _range_values(str(start), str(end))
    else:
        lo, hi = int(start), int(end)
        vals = [str(v).zfill(int(width or 0)) for v in range(lo, hi + 1)]
    return [pattern.replace("*", v, 1) for v in vals[:MAX_URLS]]
