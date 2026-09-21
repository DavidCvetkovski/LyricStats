"""The numbers one song is read by.

One engine for two callers. The LRCLIB importer (scripts/import_lrclib.py)
folds these numbers into every artist's catalogue; the API computes the same
numbers for a song fetched live. Sharing the code is what keeps a song page
and its artist's catalogue agreeing to the digit.

Plain lyrics give the word and line figures. Synced (LRC) lyrics, when the
provider has them, add the clock: when the first word lands, the longest
silence, the densest fifteen seconds, and words per tenth of the song.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .text import SECTION_RE, TOKEN_RE

# [mm:ss.xx] or [m:ss] timestamps at the start of a synced-lyrics line.
LRC_TS_RE = re.compile(r"\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]")

MAX_SONG_WORDS = 2000
MIN_DURATION_FOR_WPM = 30  # seconds


def _norm_line(ln: str) -> str:
    return " ".join(ln.lower().split())


def _line_ending(ln: str) -> str:
    """Last 3 letters of a line, lowercased and diacritics-stripped, for the
    crude end-rhyme match (š→s, ć→c, … so 'noći'/'oči' style pairs count)."""
    s = unicodedata.normalize("NFKD", ln.lower())
    letters = [c for c in s if c.isalpha() and not unicodedata.combining(c)]
    return "".join(letters[-3:])


def parse_synced(synced: str, duration: float | None) -> dict | None:
    """Timing stats from LRC text: (seconds, word-count) per line."""
    events: list[tuple[float, int]] = []
    for raw in synced.split("\n"):
        line = raw.strip()
        m = LRC_TS_RE.match(line)
        if not m:
            continue
        frac = (m.group(3) or "0").ljust(3, "0")[:3]
        ts = int(m.group(1)) * 60 + int(m.group(2)) + int(frac) / 1000
        words = len(TOKEN_RE.findall(line[m.end() :]))
        events.append((ts, words))
    events = [e for e in events if e[1] > 0]
    if len(events) < 4:
        return None
    events.sort()
    total = duration if duration and duration >= events[-1][0] else events[-1][0] + 5
    first = round(events[0][0], 1)
    gaps = [(b[0] - a[0], a[0]) for a, b in zip(events, events[1:])]
    longest_gap, gap_at = max(gaps) if gaps else (0.0, 0.0)
    # densest 15-second window
    fastest15, j = 0, 0
    for i in range(len(events)):
        while events[i][0] - events[j][0] > 15:
            j += 1
        fastest15 = max(fastest15, sum(w for _, w in events[j : i + 1]))
    # words per decile of the song
    curve = [0] * 10
    for ts, w in events:
        curve[min(9, int(ts / total * 10))] += w
    return {
        "first": first,
        "gap": round(longest_gap, 1),
        "gap_at": round(gap_at, 1),
        "fast15": fastest15,
        "curve": ",".join(map(str, curve)),
        "last": round(events[-1][0], 1),
    }


def song_stats(
    title: str, plain: str, synced: str | None, duration: float | None
) -> dict | None:
    """All per-song numbers from plain lyrics (+synced when available).

    Returns None for an empty text or one past MAX_SONG_WORDS (a lyrics page
    that is really a libretto or a mistagged album).
    """
    lines = [ln.strip() for ln in plain.split("\n")]
    # Section headers ("[Chorus]") are furniture, not lines that get sung.
    lines = [ln for ln in lines if ln and not SECTION_RE.match(ln)]
    if not lines:
        return None
    toks = TOKEN_RE.findall(" ".join(lines).lower())
    wc = len(toks)
    if wc == 0 or wc > MAX_SONG_WORDS:
        return None
    cnt = Counter(toks)
    nl = len(lines)

    norm = [_norm_line(ln) for ln in lines]
    line_freq = Counter(norm)
    top_line, top_line_n = line_freq.most_common(1)[0]
    hook_lines = sum(c for c in line_freq.values() if c >= 3)
    uniq_lines = len(line_freq)

    # title drops: the normalised title phrase appearing in the lyrics
    t_norm = _norm_line(re.sub(r"[\(\[].*?[\)\]]", "", title))
    drops = 0
    if 3 <= len(t_norm) <= 60 and len(t_norm.split()) <= 6:
        drops = _norm_line(plain).count(t_norm)

    q = sum(1 for ln in lines if ln.rstrip().endswith("?"))
    excl = sum(1 for ln in lines if ln.rstrip().endswith("!"))
    one_word = sum(1 for ln in norm if len(ln.split()) == 1)

    endings = [_line_ending(ln) for ln in lines]
    pairs = [(a, b) for a, b in zip(endings, endings[1:]) if len(a) == 3 and len(b) == 3]
    rhyme = round(sum(1 for a, b in pairs if a == b) / len(pairs), 4) if pairs else 0.0

    wpm = None
    if duration and duration >= MIN_DURATION_FOR_WPM:
        wpm = round(wc / (duration / 60), 1)

    sy = parse_synced(synced, duration) if synced else None

    longest = max(cnt, key=len)
    return {
        "wc": wc,
        "uniq": len(cnt),
        "ttr": round(len(cnt) / wc, 4),
        "rep": round(1 - uniq_lines / nl, 4),
        "hook": round(hook_lines / nl, 4),
        "top_line": top_line if top_line_n >= 3 else "",
        "top_line_n": top_line_n,
        "drops": drops,
        "q": round(q / nl, 4),
        "excl": round(excl / nl, 4),
        "one_word": round(one_word / nl, 4),
        "rhyme": rhyme,
        "longest_word": longest,
        "awl": round(sum(map(len, toks)) / wc, 2),
        "wpm": wpm,
        "first": sy["first"] if sy else None,
        "gap": sy["gap"] if sy else None,
        "gap_at": sy["gap_at"] if sy else None,
        "fast15": sy["fast15"] if sy else None,
        "curve": sy["curve"] if sy else None,
        "last": sy["last"] if sy else None,
        "cnt": cnt,
        # The song page draws these; the importer ignores them.
        "line_count": nl,
        "line_words": [len(TOKEN_RE.findall(ln)) for ln in lines],
        "top_line_at": [i for i, ln in enumerate(norm) if ln == top_line] if top_line_n >= 3 else [],
        "once": sum(1 for c in cnt.values() if c == 1),
    }


# Keys of song_stats() that are safe to store and send: everything but the
# raw token counter, which is large and already summarised by the top words.
PUBLIC_KEYS = (
    "wc", "uniq", "ttr", "rep", "hook", "top_line", "top_line_n", "drops",
    "q", "excl", "one_word", "rhyme", "longest_word", "awl", "wpm", "first",
    "gap", "gap_at", "fast15", "curve", "last", "line_count", "line_words",
    "top_line_at", "once",
)


def reading(
    title: str, plain: str, synced: str | None = None, duration: float | None = None
) -> dict | None:
    """song_stats() trimmed to what the API stores in a song's stats JSON."""
    st = song_stats(title, plain, synced, duration)
    if not st:
        return None
    out = {k: st[k] for k in PUBLIC_KEYS}
    if out["curve"]:
        out["curve"] = [int(x) for x in out["curve"].split(",")]
    out["duration"] = duration
    return out
