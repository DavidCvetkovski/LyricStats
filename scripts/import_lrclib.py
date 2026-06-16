"""Build career-wide artist stats from a local LRCLIB database dump.

Unlike the Genius CSV import (import_dataset.py), the source here is the
LRCLIB SQLite dump (https://lrclib.net/db-dumps), downloaded and decompressed
under data/lrclib/. LRCLIB lyrics are plain text (no [Chorus]/[Verse] tags)
but come with track duration and, often, time-synced lines — which unlock a
new family of stats (words per minute, intro length, density curve, …).

Four phases:

  1. SONGS   → read tracks+lyrics from the dump, dedupe by (artist, title),
     compute per-song stats + token blobs into a temp DB (data/lrclib/).
  2. FOLD    → group by artist, build one rich aggregate per artist with at
     least --min-songs songs; stash each artist's token counter for phase 3.
  3. CORPUS  → global pass over artist vocabularies: document frequencies
     (signature words, words nobody else uses) and metric distributions
     (percentiles).
  4. WRITE   → final ArtistAggregate rows (source="lrclib").

Usage:
    uv run python scripts/import_lrclib.py --inspect            # schema peek
    uv run python scripts/import_lrclib.py --limit 500000       # trial run
    uv run python scripts/import_lrclib.py --min-songs 8        # full run

The trial run writes aggregates to data/lrclib/_trial_agg.db (NOT the app DB)
and prints size estimates; a full run without --trial-db writes to the app DB.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats import db  # noqa: E402
from lyricstats.stats import STOPWORDS  # noqa: E402
from lyricstats.text import TOKEN_RE  # noqa: E402
from import_dataset import (  # noqa: E402
    _DEMO_KW,
    decode_tokens,
    encode_tokens,
    is_non_song,
)
from title_filter import load_classifier  # noqa: E402

LRCLIB_DIR = os.path.join("data", "lrclib")
DUMP_PATH = os.path.join(LRCLIB_DIR, "lrclib.sqlite3")
TMP_PATH = os.path.join(LRCLIB_DIR, "_song_stat.db")
TOK_PATH = os.path.join(LRCLIB_DIR, "_artist_tok.db")
TRIAL_AGG_PATH = os.path.join(LRCLIB_DIR, "_trial_agg.db")
LID_MODEL = os.path.join("data", "lid.176.ftz")

ARTIST_BLOCKLIST_SUBSTR = (
    "various artists", "soundtrack", "original cast", "karaoke", "tribute",
    "unknown artist", "genius", "translation",
)

# [mm:ss.xx] or [m:ss] timestamps at the start of a synced-lyrics line.
LRC_TS_RE = re.compile(r"\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]")

MAX_SONG_WORDS = 2000
MIN_DURATION_FOR_WPM = 30  # seconds
TOP_N = 20


# ── per-song stats ───────────────────────────────────────────────────────────


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
        m = LRC_TS_RE.match(raw.strip())
        if not m:
            continue
        frac = (m.group(3) or "0").ljust(3, "0")[:3]
        ts = int(m.group(1)) * 60 + int(m.group(2)) + int(frac) / 1000
        words = len(TOKEN_RE.findall(raw[m.end():]))
        events.append((ts, words))
    events = [e for e in events if e[1] > 0]
    if len(events) < 4:
        return None
    events.sort()
    total = duration if duration and duration >= events[-1][0] else events[-1][0] + 5
    first = round(events[0][0], 1)
    gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
    longest_gap = round(max(gaps), 1) if gaps else 0.0
    # densest 15-second window
    fastest15, j = 0, 0
    for i in range(len(events)):
        while events[i][0] - events[j][0] > 15:
            j += 1
        fastest15 = max(fastest15, sum(w for _, w in events[j:i + 1]))
    # words per decile of the song
    curve = [0] * 10
    for ts, w in events:
        curve[min(9, int(ts / total * 10))] += w
    return {"first": first, "gap": longest_gap, "fast15": fastest15,
            "curve": ",".join(map(str, curve))}


def song_stats(title: str, plain: str, synced: str | None,
               duration: float | None) -> dict | None:
    """All per-song numbers from plain lyrics (+synced when available)."""
    lines = [ln.strip() for ln in plain.split("\n")]
    lines = [ln for ln in lines if ln]
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
        "wc": wc, "uniq": len(cnt), "ttr": round(len(cnt) / wc, 4),
        "rep": round(1 - uniq_lines / nl, 4),
        "hook": round(hook_lines / nl, 4),
        "top_line": top_line if top_line_n >= 3 else "",
        "top_line_n": top_line_n,
        "drops": drops,
        "q": round(q / nl, 4), "excl": round(excl / nl, 4),
        "one_word": round(one_word / nl, 4),
        "rhyme": rhyme,
        "longest_word": longest,
        "awl": round(sum(map(len, toks)) / wc, 2),
        "wpm": wpm,
        "first": sy["first"] if sy else None,
        "gap": sy["gap"] if sy else None,
        "fast15": sy["fast15"] if sy else None,
        "curve": sy["curve"] if sy else None,
        "cnt": cnt,
    }


# ── language id ──────────────────────────────────────────────────────────────


def load_lid():
    try:
        import fasttext
        fasttext.FastText.eprint = lambda *a, **k: None
        return fasttext.load_model(LID_MODEL)
    except Exception as e:  # model missing → lang stats become null
        print(f"  (language model unavailable: {e})")
        return None


def detect_lang(lid, plain: str) -> str | None:
    if lid is None:
        return None
    sample = " ".join(plain.split("\n")[:30])[:1500].replace("\n", " ")
    if len(sample) < 40:
        return None
    labels, probs = lid.predict(sample)
    if not labels or probs[0] < 0.45:
        return None
    return labels[0].replace("__label__", "")


# ── phase 1: dump → temp per-song table ──────────────────────────────────────


def inspect_dump(dump: str) -> None:
    conn = sqlite3.connect(f"file:{dump}?mode=ro", uri=True)
    for (sql,) in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ):
        print(sql, end="\n\n")
    for t in ("tracks", "lyrics"):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t}: {n:,} rows")
        except sqlite3.Error as e:
            print(f"{t}: {e}")
    conn.close()


def is_junk_artist(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return True
    return any(sub in n for sub in ARTIST_BLOCKLIST_SUBSTR)


def stream_songs(dump: str, tmp: str, *, limit: int | None) -> int:
    """Read the dump, dedupe (artist,title), write per-song stats to tmp."""
    if os.path.exists(tmp):
        os.remove(tmp)
    out = sqlite3.connect(tmp)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("PRAGMA synchronous=OFF")
    # akey/tkey come from the dump's own *_lower columns, which are
    # diacritic-stripped — "Toše Proeski" and "Tose Proeski" must fold into
    # one artist, and their shared titles must dedupe against each other.
    out.execute(
        "CREATE TABLE song_stat (akey TEXT, tkey TEXT, artist TEXT, "
        "title TEXT, album TEXT, "
        "duration REAL, has_synced INTEGER, wc INTEGER, uniq INTEGER, "
        "ttr REAL, rep REAL, hook REAL, top_line TEXT, top_line_n INTEGER, "
        "drops INTEGER, q REAL, excl REAL, one_word REAL, rhyme REAL, "
        "longest_word TEXT, awl REAL, wpm REAL, first_s REAL, gap_s REAL, "
        "fast15 INTEGER, curve TEXT, lang TEXT, toks TEXT)"
    )
    lid = load_lid()
    src = sqlite3.connect(f"file:{dump}?mode=ro", uri=True)
    src.execute("PRAGMA mmap_size=8589934592")

    # Best lyrics row per track: prefer synced, then longest plain.
    q = """
        SELECT t.artist_name_lower, t.name_lower,
               t.artist_name, t.name, t.album_name, t.duration,
               l.plain_lyrics, l.synced_lyrics
        FROM tracks t
        JOIN lyrics l ON l.id = t.last_lyrics_id
        WHERE l.instrumental = 0
          AND l.plain_lyrics IS NOT NULL AND l.plain_lyrics != ''
    """
    if limit:
        q += f" LIMIT {int(limit)}"

    # NOTE: duplicate (artist, title) rows pass through here on purpose —
    # fold_artist() dedupes per title and keeps the best version (synced >
    # longest), which beats keeping whichever the dump happened to list first.
    seen = saved = 0
    batch: list[tuple] = []
    t0 = time.time()
    for akey, tkey, artist, title, album, duration, plain, synced in src.execute(q):
        seen += 1
        if seen % 250_000 == 0:
            rate = seen / (time.time() - t0)
            print(f"  …{seen:,} rows ({saved:,} kept) @ {rate:,.0f}/s", flush=True)
        if not artist or not title or is_junk_artist(artist):
            continue
        st = song_stats(title, plain, synced, duration)
        if not st:
            continue
        batch.append((
            (akey or artist.lower()).strip(), (tkey or title.lower()).strip(),
            artist.strip(), title.strip(), (album or "").strip(), duration,
            1 if synced else 0,
            st["wc"], st["uniq"], st["ttr"], st["rep"], st["hook"],
            st["top_line"], st["top_line_n"], st["drops"], st["q"], st["excl"],
            st["one_word"], st["rhyme"], st["longest_word"], st["awl"],
            st["wpm"], st["first"], st["gap"], st["fast15"], st["curve"],
            detect_lang(lid, plain), encode_tokens(st["cnt"]),
        ))
        saved += 1
        if len(batch) >= 2000:
            out.executemany(
                f"INSERT INTO song_stat VALUES ({','.join('?' * 28)})", batch)
            out.commit()
            batch.clear()
    if batch:
        out.executemany(f"INSERT INTO song_stat VALUES ({','.join('?' * 28)})", batch)
        out.commit()
    src.close()
    print(f"  phase 1 done: {seen:,} rows, {saved:,} songs kept "
          f"in {time.time() - t0:.0f}s", flush=True)
    print("  indexing by artist…", flush=True)
    out.execute("CREATE INDEX idx_artist ON song_stat(akey)")
    out.commit()
    out.close()
    return saved


# ── phase 2: fold per artist ─────────────────────────────────────────────────


def _avg(rows, key, *, present=False):
    vals = [r[key] for r in rows if (r[key] is not None if present else True)]
    return round(sum(vals) / len(vals), 4) if vals else None


def _best(rows, key, *, biggest=True, min_wc=80):
    pool = [r for r in rows if r[key] is not None and r["wc"] >= min_wc]
    if not pool:
        return None
    r = (max if biggest else min)(pool, key=lambda r: r[key])
    return r



# Bracketed qualifiers, dash suffixes, and trailing descriptors that mark a
# release variant of the same song ("Slut! (Taylor's Version) [From The
# Vault]", "Love Story - Live at the BBC", '"Change" music video', ...).
BRACKET_SEG_RE = re.compile(r"[\(\[\{][^)\]\}]*[\)\]\}]")
# Words that mark a release variant rather than a different song.
_DESCRIPTOR = (
    r"music video|official video|lyric[s]? video|official audio|visualizer|"
    r"sped up|slowed down|slowed|reverb|acoustic|live|remix|mix|instrumental|"
    r"karaoke|demo|remaster(?:ed)?|radio edit|single version|album version|"
    r"extended|bonus track|mono|stereo|deluxe|edit|version|taylor'?s version|"
    r"from the vault|cover|mashup|bootleg|rerecord(?:ed)?|re-record(?:ed)?|mv"
)
# A " - tail" is only a variant marker when the tail actually contains a
# descriptor word ("Love Story - Digital Dog Remix"). A bare "A - B" with no
# descriptor ("Taylor Swift - Bad Blood") is left intact for the prefix step.
DASH_DESCRIPTOR_RE = re.compile(
    r"\s[-\u2013\u2014]\s[^-]*\b(?:" + _DESCRIPTOR + r")\b.*$", re.IGNORECASE)
VARIANT_SUFFIX_RE = re.compile(r"\s*\b(?:" + _DESCRIPTOR + r")\s*$", re.IGNORECASE)
# "Artist - Song", "Artist: Song", "Artist | Song" redundant-credit prefix.
ARTIST_PREFIX_RE = re.compile(r"^\s*(.+?)\s*[-:\u2013\u2014|]\s+(.+)$")


def _alnum_squash(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def _strip_artist_prefix(title: str, artist: str | None) -> str:
    """Drop a leading "<artist> - " credit so "Taylor Swift - Bad Blood"
    dedupes as "Bad Blood", not as the artist's name."""
    if not artist:
        return title
    m = ARTIST_PREFIX_RE.match(title)
    if m and _alnum_squash(m.group(1)) == _alnum_squash(artist):
        return m.group(2)
    return title


def canonical_title(title: str, artist: str | None = None) -> str:
    """Collapse release variants of the same song onto one dedupe key.

    "Slut!", '"Slut!" (Taylor's Version) [From The Vault]' and
    "Slut! - Acoustic" all map to "slut"; "Red" and "Red 2" do not; and
    "Taylor Swift - Bad Blood" maps to "bad blood", not "taylor swift".
    """
    s = (title or "").replace("\x00", "")
    s = _strip_artist_prefix(s, artist)
    s = BRACKET_SEG_RE.sub(" ", s)
    s = DASH_DESCRIPTOR_RE.sub(" ", s)
    s = _alnum_squash(s)
    for _ in range(4):
        s2 = VARIANT_SUFFIX_RE.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    # Titles that were nothing but qualifiers ("Live", "(Untitled)") fall
    # back to their plain squashed form so they keep a non-empty key.
    return s or _alnum_squash(title or "") or (title or "").strip().lower()


def content_fingerprint(cnt: Counter) -> tuple | None:
    """A song's identity from its lyrics: the top content words, sorted. Robust
    to title typos, track-number prefixes and foreign re-spellings; two rows
    with the same fingerprint are the same song under different titles."""
    words = [w for w, _c in cnt.most_common(40)
             if w not in STOPWORDS and len(w) > 2]
    return tuple(sorted(words[:12])) or None


def _dedupe_songs(rows: list[dict], toks: list[Counter]) -> list[int]:
    """Return one representative row index per distinct song, merging by
    canonical title OR shared lyric fingerprint (union-find). The kept row is
    the richest variant: synced lyrics first, then the longest."""
    parent = list(range(len(rows)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    first_by_title: dict[str, int] = {}
    first_by_fp: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        tk = canonical_title(r["title"], r["artist"])
        if tk in first_by_title:
            union(i, first_by_title[tk])
        else:
            first_by_title[tk] = i
        fp = content_fingerprint(toks[i])
        if fp is not None:
            if fp in first_by_fp:
                union(i, first_by_fp[fp])
            else:
                first_by_fp[fp] = i

    best: dict[int, int] = {}
    for i, r in enumerate(rows):
        root = find(i)
        cur = best.get(root)
        if cur is None or (r["has_synced"], r["wc"]) > \
                (rows[cur]["has_synced"], rows[cur]["wc"]):
            best[root] = i
            
    for root, best_i in best.items():
        candidates = [rows[i]["title"] for i in range(len(rows)) if find(i) == root]
        candidates = [t for t in candidates if t.strip()]
        if not candidates:
            shortest_title = rows[best_i]["title"] or ""
        else:
            def title_score(title):
                score = -len(title)
                if re.search(r'[a-z][A-Z]', title):
                    score -= 100
                return score
            shortest_title = max(candidates, key=title_score)
        rows[best_i]["title"] = shortest_title
        
    return sorted(best.values())


def drop_truncation_stubs(aggs: list[tuple]) -> tuple[list[tuple], int]:
    """Drop aggregates whose display name is an encoding-truncated prefix of
    a much bigger artist ("beyonc" 52 next to "Beyoncé" 2067). Only fires
    when the longer name continues with a NON-ascii char, so real artists
    that happen to prefix bigger ones (Emin / Eminem) are untouched."""
    order = sorted(range(len(aggs)), key=lambda i: aggs[i][1].lower())
    drop: set[int] = set()
    for pos, i in enumerate(order):
        d = aggs[i][1]
        dl = d.lower()
        if len(dl) < 4:
            continue
        n = aggs[i][2]["song_count"]
        for j in order[pos + 1: pos + 40]:
            od, on = aggs[j][1], aggs[j][2]["song_count"]
            if not od.lower().startswith(dl):
                break  # sorted: the prefix block is contiguous
            if len(od) > len(d) and ord(od[len(d)]) > 127 and on >= 10 * n:
                drop.add(i)
                break
    return [a for i, a in enumerate(aggs) if i not in drop], len(drop)


def fold_artist(rows: list[dict], *, min_songs: int, clf,
                songs_cap: int = 500) -> tuple | None:
    # U+FFFD in the artist name = broken encoding upstream; the healthy
    # spelling of the same artist has its own (much larger) group.
    import re
    def clean_title(title):
        if not title: return ""
        orig_title = title
        
        parts = title.split(" - ")
        if len(parts) > 1:
            junk_keywords = ["remaster", "edit", "acoustic", "live", "version", "mix", "demo"]
            if any(k in parts[-1].lower() for k in junk_keywords):
                title = " - ".join(parts[:-1])

        def replacer(match):
            content = match.group(0)
            if re.search(r'\b(feat\.?|ft\.?|featuring)\b', content, re.IGNORECASE):
                return content
            return ""
            
        title = re.sub(r'\([^)]*\)|\[[^\]]*\]', replacer, title)
        
        cleaned = title.strip()
        return cleaned if cleaned else orig_title

    rows = [dict(r) for r in rows
            if "\xef\xbf\xbd" not in r["artist"]
            and not is_non_song(r["title"], r["wc"], r["ttr"], Counter(decode_tokens(r["toks"])), clf=clf)]
            
    # NUL bytes from broken submissions break Postgres later; strip on entry
    for r in rows:
        r["title"] = clean_title(r["title"])
        for f in ("artist", "title", "album"):
            if r[f] and "\x00" in r[f]:
                r[f] = r[f].replace("\x00", "")
    # Decode each row's vocabulary once; reused for the content fingerprint
    # and the merged artist vocab below.
    toks = [Counter(decode_tokens(r["toks"])) for r in rows]

    # Dedupe to one row per distinct song. LRCLIB lists every release variant,
    # cover, karaoke and mislabelled re-upload separately, so a single key can't
    # catch them. We union two signals: same canonical title OR same lyric
    # fingerprint (top content words). Title catches variants whose lyrics drift
    # slightly (live, acoustic); content catches variants whose title is a typo,
    # track number or foreign spelling. The union lands near real discographies.
    keep = _dedupe_songs(rows, toks)
    rows = [rows[i] for i in keep]
    toks = [toks[i] for i in keep]
    n = len(rows)
    if n < min_songs:
        return None

    display = Counter(r["artist"] for r in rows).most_common(1)[0][0]
    total_words = sum(r["wc"] for r in rows)
    g: Counter[str] = Counter()
    for c in toks:
        g.update(c)

    eligible = [r for r in rows if r["wc"] >= 80 and not any(
        kw in r["title"].lower() for kw in _DEMO_KW)] or rows
    longest = max(eligible, key=lambda r: r["wc"])
    shortest = min(eligible, key=lambda r: r["wc"])
    richest = max(eligible, key=lambda r: r["ttr"])

    career_line = max(
        (r for r in rows if r["top_line"]), default=None,
        key=lambda r: r["top_line_n"])
    top_drop = max(rows, key=lambda r: r["drops"])
    fastest = _best(rows, "wpm", biggest=True)
    slowest = _best(rows, "wpm", biggest=False)
    long_intro = _best(rows, "first_s", biggest=True, min_wc=40)
    long_gap = _best(rows, "gap_s", biggest=True, min_wc=40)
    burst = _best(rows, "fast15", biggest=True, min_wc=40)

    langs = Counter(r["lang"] for r in rows if r["lang"])
    lang_mix = {l: round(c / sum(langs.values()), 3)
                for l, c in langs.most_common(3)} if langs else {}

    curves = [list(map(int, r["curve"].split(","))) for r in rows if r["curve"]]
    avg_curve = None
    if len(curves) >= 5:
        sums = [sum(c[i] for c in curves) for i in range(10)]
        tot = sum(sums) or 1
        avg_curve = [round(s / tot, 3) for s in sums]

    albums: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["album"]:
            albums[r["album"]].append(r)
    album_rows = sorted(albums.items(), key=lambda kv: -len(kv[1]))[:12]
    album_stats = []
    for name, ars in album_rows:
        if len(ars) < 3:
            continue
        a_vocab = set()
        for r in ars:
            a_vocab.update(Counter(decode_tokens(r["toks"])).keys())
        album_stats.append({
            "album": name, "songs": len(ars),
            "words": sum(r["wc"] for r in ars),
            "vocab": len(a_vocab),
            "avg_ttr": _avg(ars, "ttr"),
            "avg_wpm": _avg(ars, "wpm", present=True),
        })

    stats = {
        # core (same shape the artist page already reads)
        "song_count": n,
        "total_words": total_words,
        "total_unique_words": len(g),
        "avg_words_per_song": round(total_words / n, 2),
        "avg_ttr": _avg(rows, "ttr"),
        "avg_chorus_ratio": 0.0,  # no section tags in lrclib
        "avg_repetition_ratio": _avg(rows, "rep"),
        "top_words": g.most_common(TOP_N),
        "top_words_no_stop": [(w, c) for w, c in g.most_common(TOP_N * 4)
                              if w not in STOPWORDS][:TOP_N],
        "longest_song": {"title": longest["title"], "words": longest["wc"]},
        "shortest_song": {"title": shortest["title"], "words": shortest["wc"]},
        "richest_song": {"title": richest["title"], "ttr": richest["ttr"]},
        # new: repetition / hook
        "avg_hook_share": _avg(rows, "hook"),
        "career_line": {"line": career_line["top_line"],
                        "count": career_line["top_line_n"],
                        "title": career_line["title"]} if career_line else None,
        # new: flow & timing
        "avg_wpm": _avg(rows, "wpm", present=True),
        "fastest_song": {"title": fastest["title"], "wpm": fastest["wpm"]} if fastest else None,
        "slowest_song": {"title": slowest["title"], "wpm": slowest["wpm"]} if slowest else None,
        "synced_share": round(sum(r["has_synced"] for r in rows) / n, 3),
        "avg_first_word_s": _avg(rows, "first_s", present=True),
        "longest_intro": {"title": long_intro["title"], "s": long_intro["first_s"]} if long_intro else None,
        "longest_silence": {"title": long_gap["title"], "s": long_gap["gap_s"]} if long_gap else None,
        "fastest_burst": {"title": burst["title"], "words15s": burst["fast15"]} if burst else None,
        "density_curve": avg_curve,
        # new: texture
        "avg_rhyme": _avg(rows, "rhyme"),
        "question_share": _avg(rows, "q"),
        "exclaim_share": _avg(rows, "excl"),
        "one_word_line_share": _avg(rows, "one_word"),
        "avg_word_length": _avg(rows, "awl"),
        "longest_word": max((r["longest_word"] for r in rows), key=len),
        "title_drops_total": sum(r["drops"] for r in rows),
        "biggest_title_drop": {"title": top_drop["title"],
                               "count": top_drop["drops"]} if top_drop["drops"] else None,
        "lang_mix": lang_mix,
        "albums": album_stats,
        # filled by the corpus pass
        "signature_words": None,
        "exclusive_words": None,
        "percentiles": None,
    }
    # Positions 0-7 match the old dataset shape (the artist table indexes
    # into these); the new per-song stats are appended after, so the current
    # UI keeps working and a future song dropdown can read 8+.
    songs_list = sorted(
        ([r["title"], None, r["wc"], r["uniq"], round(r["ttr"], 2), 0.0,
          round(r["rep"], 2), 0]
         for r in rows), key=lambda x: x[2], reverse=True)[:songs_cap]
    return display, stats, songs_list, g


def backfill_years(display: str, stats: dict, songs_list: list,
                   app_conn) -> None:
    """LRCLIB has no release years; recover them for titles that also exist
    in the legacy Genius-dataset aggregate for the same artist."""
    if app_conn is None:
        return
    row = app_conn.execute(
        "SELECT songs_json FROM artistaggregate WHERE name_key = ? "
        "AND source = 'dataset'", (db.normalize_key(display),)).fetchone()
    if not row:
        return
    years = {}
    for old in json.loads(row[0]):
        if len(old) >= 2 and old[1]:
            years[canonical_title(str(old[0]))] = old[1]
    hits = 0
    for r in songs_list:
        y = years.get(canonical_title(str(r[0])))
        if y:
            r[1] = y
            hits += 1
    stats["years_known"] = hits


def fold(tmp: str, *, min_songs: int, songs_cap: int) -> list[tuple]:
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    clf = load_classifier()
    try:
        app_conn = sqlite3.connect(os.path.join("data", "lyricstats.db"))
    except sqlite3.Error:
        app_conn = None
    conn.create_function("nkey", 1, lambda a: db.normalize_key(a or ""))
    cur = conn.execute(
        "SELECT *, (CASE WHEN nkey(akey) = '' THEN 'raw:' || akey "
        "ELSE nkey(akey) END) AS gkey FROM song_stat ORDER BY gkey")
    out = []
    group: list[dict] = []
    current = None
    if os.path.exists(TOK_PATH):
        os.remove(TOK_PATH)
    tok_writer = sqlite3.connect(TOK_PATH)
    tok_writer.execute("PRAGMA journal_mode=OFF")
    tok_writer.execute("PRAGMA synchronous=OFF")
    tok_writer.execute("CREATE TABLE artist_tok (name TEXT PRIMARY KEY, toks TEXT)")
    t0 = time.time()

    def flush():
        nonlocal group
        if not group:
            return
        r = fold_artist(group, min_songs=min_songs, clf=clf,
                        songs_cap=songs_cap)
        if r:
            display, stats, songs_list, g = r
            backfill_years(display, stats, songs_list, app_conn)
            out.append((current, display, stats, songs_list))
            tok_writer.execute(
                "INSERT OR REPLACE INTO artist_tok VALUES (?, ?)",
                (current, encode_tokens(g)))
        group = []

    for row in cur:
        k = row["gkey"]
        if current is not None and k != current:
            flush()
            if len(out) % 10_000 == 0 and out:
                print(f"  …{len(out):,} aggregates @ "
                      f"{len(out) / (time.time() - t0):,.0f}/s", flush=True)
        current = k
        group.append(dict(row))
    flush()
    tok_writer.commit()
    tok_writer.close()
    conn.close()
    print(f"  phase 2 done: {len(out):,} artists ≥{min_songs} songs "
          f"in {time.time() - t0:.0f}s", flush=True)
    return out


# ── phase 3: corpus pass ─────────────────────────────────────────────────────

PCTL_KEYS = ("total_unique_words", "avg_ttr", "avg_wpm", "avg_hook_share",
             "avg_rhyme", "avg_words_per_song")


def corpus_pass(aggs: list[tuple]) -> None:
    """Attach signature_words, exclusive_words, percentiles in place."""
    t0 = time.time()
    conn = sqlite3.connect(TOK_PATH)
    # 3a — document frequency over artists (hashed; value capped at 2) +
    # corpus frequency for candidate words (each artist's 250 most-used)
    df: dict[int, int] = {}
    corpus_freq: Counter[str] = Counter()
    corpus_total = 0
    n_artists = 0
    for (toks,) in conn.execute("SELECT toks FROM artist_tok"):
        cnt = decode_tokens(toks)
        corpus_total += sum(cnt.values())
        n_artists += 1
        for w in cnt:
            h = hash(w)
            v = df.get(h, 0)
            if v < 2:
                df[h] = v + 1
        for w, c in cnt.most_common(250):
            if len(w) >= 3 and c >= 3 and w not in STOPWORDS:
                corpus_freq[w] += c
        if n_artists % 25_000 == 0:
            print(f"  …corpus 3a {n_artists:,} artists, df={len(df):,}", flush=True)
    print(f"  corpus: {n_artists:,} artists, {corpus_total:,} words, "
          f"{len(df):,} distinct (3a in {time.time() - t0:.0f}s)", flush=True)

    # metric distributions → percentile lookup
    dists = {}
    for key in PCTL_KEYS:
        vals = sorted(s[key] for _, _, s, _ in aggs if s.get(key) is not None)
        dists[key] = vals
    import bisect

    def pctl(key, v):
        vals = dists[key]
        if not vals or v is None:
            return None
        return int(round(100 * bisect.bisect_left(vals, v) / len(vals)))

    # 3b — per artist, score the same top-250 candidate set against the corpus
    for akey, _display, stats, _songs in aggs:
        row = conn.execute(
            "SELECT toks FROM artist_tok WHERE name = ?", (akey,)).fetchone()
        cnt = decode_tokens(row[0]) if row else Counter()
        my_total = stats["total_words"] or 1
        sig, excl = [], []
        for w, c in cnt.most_common(250):
            if len(w) < 3 or c < 3 or w in STOPWORDS:
                continue
            if df.get(hash(w), 0) == 1:
                excl.append([w, c])
            if c < 5:
                continue
            mine = c / my_total * 1000
            theirs = (corpus_freq.get(w, 0) / corpus_total * 1000) or 0.0005
            ratio = mine / theirs
            if ratio >= 3:
                sig.append([w, c, round(ratio, 1)])
        stats["signature_words"] = sorted(sig, key=lambda x: -x[2])[:10]
        stats["exclusive_words"] = sorted(excl, key=lambda x: -x[1])[:10]
        stats["percentiles"] = {k: pctl(k, stats.get(k)) for k in PCTL_KEYS}
    conn.close()
    print(f"  phase 3 done in {time.time() - t0:.0f}s", flush=True)


# ── phase 4: write ───────────────────────────────────────────────────────────


def write_trial(aggs: list[tuple], path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE agg (name TEXT, song_count INTEGER, "
                 "stats_json TEXT, songs_json TEXT)")
    conn.executemany(
        "INSERT INTO agg VALUES (?,?,?,?)",
        ((d, s["song_count"], json.dumps(s, ensure_ascii=False),
          json.dumps(sl, ensure_ascii=False)) for _k, d, s, sl in aggs))
    conn.commit()
    # size report
    total_stats = conn.execute("SELECT SUM(LENGTH(stats_json)) FROM agg").fetchone()[0] or 0
    total_songs = conn.execute("SELECT SUM(LENGTH(songs_json)) FROM agg").fetchone()[0] or 0
    n = len(aggs)
    print(f"\n  TRIAL SIZE: {n:,} artists | stats_json {total_stats/1e6:.1f}MB "
          f"(avg {total_stats/max(n,1):.0f}B) | songs_json {total_songs/1e6:.1f}MB "
          f"(avg {total_songs/max(n,1):.0f}B)")
    for cutoff in (3, 5, 8, 10, 15, 20):
        r = conn.execute(
            "SELECT COUNT(*), SUM(LENGTH(stats_json))+SUM(LENGTH(songs_json)) "
            "FROM agg WHERE song_count >= ?", (cutoff,)).fetchone()
        if r and r[0]:
            print(f"    cutoff ≥{cutoff:>2}: {r[0]:>8,} artists, {r[1]/1e6:>8.1f} MB raw")
    conn.close()


def write_final(aggs: list[tuple]) -> None:
    from sqlmodel import delete, select
    with db.session() as s:
        s.exec(delete(db.ArtistAggregate))  # pure-LRCLIB table
        s.commit()
        used_names: set[str] = set()
        for i, (_akey, display, stats, songs_list) in enumerate(aggs):
            name = display.strip().lower()
            if name in used_names:
                print(f"  skipping duplicate display name: {display!r}")
                continue
            used_names.add(name)
            old = s.exec(select(db.ArtistAggregate)
                         .where(db.ArtistAggregate.name == name)).first()
            if old is not None:
                s.delete(old)
                s.flush()
            s.add(db.ArtistAggregate(
                name=display.strip().lower(),
                name_key=db.normalize_key(display),
                display_name=display,
                song_count=stats["song_count"],
                has_sections=False,
                stats_json=json.dumps(stats, ensure_ascii=False),
                songs_json=json.dumps(songs_list, ensure_ascii=False),
                source="lrclib",
            ))
            if i % 5_000 == 0:
                s.commit()
        s.commit()
    print(f"  wrote {len(aggs):,} aggregates (source=lrclib)")


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=DUMP_PATH)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-songs", type=int, default=5)
    ap.add_argument("--songs-cap", type=int, default=500)
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--skip-stream", action="store_true",
                    help="reuse the existing temp song_stat DB")
    ap.add_argument("--final", action="store_true",
                    help="write into the app DB instead of the trial DB")
    args = ap.parse_args()

    if args.inspect:
        inspect_dump(args.dump)
        return

    if not args.skip_stream:
        print("phase 1: streaming songs from dump…", flush=True)
        stream_songs(args.dump, TMP_PATH, limit=args.limit)
    print("phase 2: folding artists…", flush=True)
    aggs = fold(TMP_PATH, min_songs=args.min_songs, songs_cap=args.songs_cap)
    aggs, n_stubs = drop_truncation_stubs(aggs)
    if n_stubs:
        print(f"  dropped {n_stubs} truncation-stub artists", flush=True)
    print("phase 3: corpus pass…", flush=True)
    corpus_pass(aggs)
    if args.final:
        print("phase 4: writing to app DB…", flush=True)
        write_final(aggs)
    else:
        print("phase 4: writing trial DB…", flush=True)
        write_trial(aggs, TRIAL_AGG_PATH)


if __name__ == "__main__":
    main()
