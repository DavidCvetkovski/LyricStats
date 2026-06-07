"""Bulk-import career-wide artist stats from the 5M-song Genius lyrics dataset.

Streams the dataset CSV over HTTP (nothing saved to disk except a temporary
per-song stats DB), computes lean per-song stats, then folds them into one
precomputed aggregate per artist — stored in the ``ArtistAggregate`` table so
the app can answer "type an artist, see their whole career in figures" with
zero Genius/lyric fetches.

Two phases (single network pass):

  1. STREAM  → for every song compute word/vocab/section stats + a full token
     counter, batch-insert into a temp SQLite (``song_stat``). ~10GB temp; the
     raw 9GB CSV is never persisted.
  2. FOLD    → read ``song_stat`` ordered by artist, accumulate one artist at a
     time (bounded memory), and write final aggregates for artists with at
     least ``--min-songs`` songs. Drop the temp DB at the end.

Usage:
    uv run python scripts/import_dataset.py                 # full run
    uv run python scripts/import_dataset.py --limit 200000  # quick test
    uv run python scripts/import_dataset.py --min-songs 8
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter

import pandas as pd
import requests

# Allow "uv run python scripts/import_dataset.py" without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats import db  # noqa: E402
from lyricstats.stats import STOPWORDS  # noqa: E402
from lyricstats.text import parse_sections, tokenize  # noqa: E402

DATASET_URL = (
    "https://huggingface.co/datasets/sebastiandizon/genius-song-lyrics"
    "/resolve/main/song_lyrics%202.csv"
)

# Genius "artist" pages that aren't real artists — skip so they don't become
# giant junk aggregates.
ARTIST_BLOCKLIST_SUBSTR = (
    "genius",
    "translation",
    "romanization",
    "spotify",
    "apple music",
    "soundcloud",
    "annotated",
    "tracklist",
    "booklet",
)

_CHORUS_KINDS = {"chorus", "hook", "refrain"}

# Genius pages that aren't songs (interviews, discographies, etc.) leak into the
# dataset and, being long, sort to the top of a catalogue. Drop them by title.
_NON_SONG_SUBSTR = (
    "interview", "discography", "tracklist", "tracklisting", "booklet",
    "conference call", "setlist", "annotated", "tour dates", "album art",
    "cover art", "liner notes", "press release", "(album)", "full album",
    "q&a", "biography", "snippet", "teaser",
)


def is_non_song(title: str) -> bool:
    t = (title or "").lower()
    return any(p in t for p in _NON_SONG_SUBSTR)


def is_junk_artist(name: str) -> bool:
    n = name.strip().lower()
    if not n or n == "nan":
        return True
    return any(sub in n for sub in ARTIST_BLOCKLIST_SUBSTR)


def lean_song_stats(lyrics: str):
    """Per-song stats needed for aggregation. Returns dict or None if empty."""
    secs = parse_sections(lyrics)
    lines = [ln for s in secs for ln in s.lines]
    if not lines:
        return None
    toks = tokenize(" ".join(lines))
    wc = len(toks)
    if wc == 0:
        return None
    cnt = Counter(toks)
    total_lines = len(lines)
    chorus_lines = sum(len(s.lines) for s in secs if s.kind in _CHORUS_KINDS)
    uniq_lines = len({ln.strip().lower() for ln in lines if ln.strip()})
    return {
        "wc": wc,
        "uniq": len(cnt),
        "ttr": round(wc and len(cnt) / wc, 4),
        "chorus": round(chorus_lines / total_lines, 4) if total_lines else 0.0,
        "rep": round(1 - (uniq_lines / total_lines), 4) if total_lines else 0.0,
        "has_sec": 1 if any(s.kind != "other" for s in secs) else 0,
        "cnt": cnt,
    }


def encode_tokens(cnt: Counter) -> str:
    """Compact 'tok count tok count …' blob. Tokens are letters/apostrophes
    only (no spaces), so a space-delimited flat list round-trips cleanly."""
    return " ".join(f"{t} {c}" for t, c in cnt.items())


def decode_tokens(blob: str) -> Counter:
    if not blob:
        return Counter()
    parts = blob.split(" ")
    cnt: Counter[str] = Counter()
    for i in range(0, len(parts) - 1, 2):
        cnt[parts[i]] = int(parts[i + 1])
    return cnt


# ── phase 1: stream → temp per-song table ────────────────────────────────────


def _tmp_has_data(tmp_path: str) -> int:
    if not os.path.exists(tmp_path):
        return 0
    try:
        conn = sqlite3.connect(tmp_path)
        n = conn.execute("SELECT COUNT(*) FROM song_stat").fetchone()[0]
        conn.close()
        return int(n)
    except sqlite3.Error:
        return 0


def stream_to_temp(tmp_path: str, *, limit: int | None, chunksize: int) -> int:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    conn = sqlite3.connect(tmp_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute(
        "CREATE TABLE song_stat (artist TEXT, title TEXT, year INTEGER, "
        "wc INTEGER, uniq INTEGER, ttr REAL, chorus REAL, rep REAL, "
        "has_sec INTEGER, toks TEXT)"
    )

    r = requests.get(
        DATASET_URL, stream=True, headers={"Accept-Encoding": "identity"}, timeout=120
    )
    r.raise_for_status()
    r.raw.decode_content = True

    seen = saved = 0
    batch: list[tuple] = []
    t0 = time.time()
    for chunk in pd.read_csv(
        r.raw,
        chunksize=chunksize,
        usecols=["title", "artist", "year", "lyrics"],
        dtype=str,
        on_bad_lines="skip",
        engine="c",
    ):
        for title, artist, year, lyrics in zip(
            chunk["title"], chunk["artist"], chunk["year"], chunk["lyrics"]
        ):
            seen += 1
            if not isinstance(artist, str) or is_junk_artist(artist):
                continue
            if not isinstance(lyrics, str):
                continue
            st = lean_song_stats(lyrics)
            if not st:
                continue
            yr = None
            if isinstance(year, str) and year[:4].isdigit():
                yr = int(year[:4])
            batch.append(
                (
                    artist.strip(),
                    (title or "?").strip() if isinstance(title, str) else "?",
                    yr,
                    st["wc"], st["uniq"], st["ttr"], st["chorus"], st["rep"],
                    st["has_sec"], encode_tokens(st["cnt"]),
                )
            )
            saved += 1
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO song_stat VALUES (?,?,?,?,?,?,?,?,?,?)", batch
                )
                conn.commit()
                batch.clear()
            if seen % 250_000 == 0:
                rate = seen / (time.time() - t0)
                print(
                    f"  …streamed {seen:,} rows ({saved:,} kept) "
                    f"@ {rate:,.0f}/s",
                    flush=True,
                )
            if limit and seen >= limit:
                break
        if limit and seen >= limit:
            break
    if batch:
        conn.executemany("INSERT INTO song_stat VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
        conn.commit()
    r.close()
    print(f"  phase 1 done: {seen:,} rows seen, {saved:,} songs kept "
          f"in {time.time()-t0:.0f}s", flush=True)
    print("  indexing by artist…", flush=True)
    conn.execute("CREATE INDEX idx_artist ON song_stat(artist)")
    conn.commit()
    conn.close()
    return saved


# ── phase 2: fold per artist → ArtistAggregate ───────────────────────────────

_DEMO_KW = ("(demo)", "[demo]", "(snippet)", "[snippet]", "(teaser)",
            "[teaser]", "(promo)", "[promo]", "(skit)", "[skit]")


def _highlights(songs: list[tuple[str, int, float]]) -> dict:
    """songs = list of (title, wc, ttr). Pick longest/shortest/richest,
    excluding tiny/demo tracks so a 20-word snippet can't 'win'."""
    eligible = [s for s in songs if s[1] >= 80 and not any(
        kw in s[0].lower() for kw in _DEMO_KW)]
    if not eligible:
        eligible = songs
    longest = max(eligible, key=lambda s: s[1])
    shortest = min(eligible, key=lambda s: s[1])
    richest = max(eligible, key=lambda s: s[2])
    return {
        "longest_song": {"title": longest[0], "words": longest[1]},
        "shortest_song": {"title": shortest[0], "words": shortest[1]},
        "richest_song": {"title": richest[0], "ttr": richest[2]},
    }


def _build_aggregate(rows: list, *, min_songs: int, top_n: int):
    """Build an ArtistAggregate ORM object for one artist group, or None if too
    few songs. Rows are grouped by normalised (trim+lower) name, so casing
    variants ('Johnnyswim' / 'JOHNNYSWIM') merge into one artist; the display
    name is the most common raw spelling. No DB write here — caller batches."""
    # Drop interview/discography/tracklist pages before anything counts.
    rows = [r for r in rows if not is_non_song(r["title"])]
    n = len(rows)
    if n < min_songs:
        return None
    # Most common raw casing wins as the display name.
    display_name = Counter(r["artist"] for r in rows).most_common(1)[0][0]
    total_words = sum(r["wc"] for r in rows)
    global_counts: Counter[str] = Counter()
    for r in rows:
        global_counts.update(decode_tokens(r["toks"]))
    top_words = global_counts.most_common(top_n)
    top_words_no_stop = [
        (w, c) for w, c in global_counts.most_common(top_n * 4) if w not in STOPWORDS
    ][:top_n]
    stats = {
        "song_count": n,
        "total_words": total_words,
        "total_unique_words": len(global_counts),
        "avg_words_per_song": round(total_words / n, 2),
        "avg_ttr": round(sum(r["ttr"] for r in rows) / n, 4),
        "avg_chorus_ratio": round(sum(r["chorus"] for r in rows) / n, 4),
        "avg_repetition_ratio": round(sum(r["rep"] for r in rows) / n, 4),
        "top_words": top_words,
        "top_words_no_stop": top_words_no_stop,
        **_highlights([(r["title"], r["wc"], r["ttr"]) for r in rows]),
    }
    # Compact per-song list for the catalogue (no lyrics). Order doesn't matter
    # — the UI sorts client-side; store largest-first so it reads sensibly raw.
    songs_list = sorted(
        ([r["title"], r["year"], r["wc"], r["uniq"], r["ttr"],
          r["chorus"], r["rep"], int(r["has_sec"])] for r in rows),
        key=lambda x: x[2], reverse=True,
    )
    return db.ArtistAggregate(
        name=display_name.strip().lower(),
        name_key=db.normalize_key(display_name),
        display_name=display_name,
        song_count=n,
        has_sections=any(r["has_sec"] for r in rows),
        stats_json=json.dumps(stats, ensure_ascii=False),
        songs_json=json.dumps(songs_list, ensure_ascii=False),
        source="dataset",
    )


def fold_to_aggregates(tmp_path: str, *, min_songs: int, top_n: int,
                       batch: int = 2000) -> int:
    print("  resetting ArtistAggregate table…", flush=True)
    db.reset_aggregates()

    conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    # Order by the trimmed/lowercased name so casing variants of the same
    # artist are adjacent and fold into a single group (avoids UNIQUE clashes
    # on the lowercased `name` and merges 'Johnnyswim'/'JOHNNYSWIM').
    cur = conn.execute(
        "SELECT artist, title, year, wc, uniq, ttr, chorus, rep, has_sec, toks "
        "FROM song_stat ORDER BY TRIM(LOWER(artist))"
    )
    written = 0
    seen_artists = 0
    cur_key: str | None = None
    rows: list = []
    buf: list = []
    t0 = time.time()

    def flush_buf():
        if not buf:
            return
        with db.session() as s:
            s.add_all(buf)
            s.commit()
        buf.clear()

    def finish_artist(songs: list):
        nonlocal written, seen_artists
        seen_artists += 1
        agg = _build_aggregate(songs, min_songs=min_songs, top_n=top_n)
        if agg is not None:
            buf.append(agg)
            written += 1
            if len(buf) >= batch:
                flush_buf()
        if seen_artists % 20000 == 0:
            print(f"  …folded {seen_artists:,} artists, {written:,} kept",
                  flush=True)

    for row in cur:
        key = (row["artist"] or "").strip().lower()
        if key != cur_key:
            if cur_key is not None:
                finish_artist(rows)
            cur_key = key
            rows = []
        rows.append(row)
    if cur_key is not None:
        finish_artist(rows)
    flush_buf()
    conn.close()
    print(f"  phase 2 done: {seen_artists:,} artists seen, {written:,} "
          f"aggregates written (≥{min_songs} songs) in {time.time()-t0:.0f}s",
          flush=True)
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N source rows (for testing)")
    ap.add_argument("--min-songs", type=int, default=5,
                    help="only keep artists with at least this many songs")
    ap.add_argument("--top-n", type=int, default=30, help="top words to store")
    ap.add_argument("--chunksize", type=int, default=20000)
    ap.add_argument("--tmp", default="./data/_import_tmp.db")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="don't delete the temp per-song DB at the end")
    ap.add_argument("--reuse-tmp", action="store_true",
                    help="skip streaming and re-fold an existing temp DB "
                         "(for tuning --min-songs without re-downloading)")
    args = ap.parse_args()

    if args.reuse_tmp and _tmp_has_data(args.tmp):
        n = _tmp_has_data(args.tmp)
        print(f"▶ Phase 1 skipped: reusing {args.tmp} ({n:,} songs)", flush=True)
        saved = n
    else:
        print(f"▶ Phase 1: streaming dataset → {args.tmp}", flush=True)
        saved = stream_to_temp(args.tmp, limit=args.limit, chunksize=args.chunksize)
    if saved == 0:
        print("No songs streamed; aborting.")
        return

    print(f"▶ Phase 2: folding into ArtistAggregate (min_songs={args.min_songs})",
          flush=True)
    written = fold_to_aggregates(args.tmp, min_songs=args.min_songs, top_n=args.top_n)

    if not args.keep_tmp:
        try:
            os.remove(args.tmp)
            print(f"  removed temp DB {args.tmp}")
        except OSError:
            pass

    print(f"\n✅ Done. {written:,} artist aggregates in the database.")


if __name__ == "__main__":
    main()
