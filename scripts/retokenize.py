#!/usr/bin/env python3
"""Re-tokenize the songs the old tokenizer broke, in place, with a way back.

The old word regex dropped vowel signs (combining marks), so every word in
Devanagari, Tamil, Thai, Sinhala and the other Brahmic scripts was cut at
each one ("गले" → "ग" + "ल"), and heavily vowelled Arabic and Hebrew fell
apart into letters. song_stat keeps only the tokens, not the text, so the
text has to come back from LRCLIB, and each row is rewritten only when the
old code, run on that text, gives exactly the tokens stored today (the same
text, not a later edit). Nothing is written until --apply; the old values
of every changed column are kept in the work file first.

  python scripts/retokenize.py --find
      One read-only pass over song_stat: the rows to redo, and their current
      values, into data/lrclib/_retok.db (the work file; ~0.3 GB).
  python scripts/retokenize.py --fetch api [--rate 2] [--limit N]
  python scripts/retokenize.py --fetch /path/to/lrclib-db-dump.sqlite3
      Text from the LRCLIB API (artist, title, album, duration) or from a dump;
      new values into the work file. Resumable: rows already fetched are skipped.
  python scripts/retokenize.py --apply
      Write the checked rows into song_stat, 2,000 per transaction. Resumable.
  python scripts/retokenize.py --rollback
      Put the old values of every applied row back.
  python scripts/retokenize.py --status

After --apply: rebuild the owner index, the artist token counters, the word
frequencies and the folds (see the README's catalogue section).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("DATABASE_URL", None)

from lyricstats import reading  # noqa: E402
from lyricstats.text import SECTION_RE  # noqa: E402

SONG_DB = os.path.join(ROOT, "data", "lrclib", "_song_stat.db")
WORK_DB = os.path.join(ROOT, "data", "lrclib", "_retok.db")
API = "https://lrclib.net/api/get"
AGENT = "LyricStats re-tokenizer (https://lyricstats.dev)"

# The regex song_stat.toks was made with: letters only, so a vowel sign ends a word.
OLD_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
# Brahmic and South-East Asian scripts: vowels are marks, every word was cut.
SPLIT_SCRIPT_RE = re.compile(r"[ऀ-෿฀-໿ༀ-࿿က-႟ក-៿]")
# Arabic and Hebrew: only a text with its vowel points fell apart into letters.
POINTED_SCRIPT_RE = re.compile(r"[֐-׿؀-ۿ]")
# Columns the text decides (the rest — names, album, duration, lang — stay).
COLS = ("wc", "uniq", "ttr", "rep", "hook", "top_line", "top_line_n", "drops", "q", "excl",
        "one_word", "rhyme", "longest_word", "awl", "wpm", "first_s", "gap_s", "fast15", "curve", "toks")


def _encode(cnt: Counter) -> str:
    return " ".join(f"{t} {c}" for t, c in cnt.items())


def old_tokens(plain: str) -> tuple[str, int]:
    """The tokens and word count the old importer stored for this text."""
    lines = [ln.strip() for ln in plain.split("\n")]
    lines = [ln for ln in lines if ln and not SECTION_RE.match(ln)]
    toks = OLD_TOKEN_RE.findall(" ".join(lines).lower())
    return _encode(Counter(toks)), len(toks)


def broken(toks: str) -> bool:
    """Tokens in a script the old regex cut up: any Brahmic word, or an Arabic
    or Hebrew text that fell apart into single letters."""
    words = toks.split()[::2]
    if any(SPLIT_SCRIPT_RE.search(w) for w in words):
        return True
    pointed = [w for w in words if POINTED_SCRIPT_RE.search(w)]
    return len(pointed) >= 10 and sum(len(w) == 1 for w in pointed) >= 0.3 * len(pointed)


def work() -> sqlite3.Connection:
    w = sqlite3.connect(WORK_DB)
    w.execute(f"CREATE TABLE IF NOT EXISTS todo (rid INTEGER PRIMARY KEY, akey TEXT, artist TEXT, "
              f"title TEXT, album TEXT, duration REAL, {', '.join('old_' + c for c in COLS)})")
    w.execute(f"CREATE TABLE IF NOT EXISTS new (rid INTEGER PRIMARY KEY, status TEXT, lrclib_id INTEGER, "
              f"{', '.join(COLS)}, applied INTEGER DEFAULT 0)")
    return w


def find() -> None:
    song = sqlite3.connect(f"file:{SONG_DB}?mode=ro", uri=True)
    song.execute("PRAGMA mmap_size=68000000000")
    w = work()
    t0, seen, hit, batch = time.time(), 0, 0, []
    cols = ", ".join(COLS)
    for row in song.execute(f"SELECT rowid, akey, artist, title, album, duration, {cols} FROM song_stat"):
        seen += 1
        if broken(row[-1] or ""):
            batch.append(row)
            hit += 1
        if len(batch) >= 5000:
            w.executemany(f"INSERT OR IGNORE INTO todo VALUES ({','.join('?' * (6 + len(COLS)))})", batch)
            w.commit()
            batch.clear()
        if seen % 1_000_000 == 0:
            print(f"  …{seen:,} rows read, {hit:,} to redo, {time.time() - t0:.0f}s", flush=True)
    w.executemany(f"INSERT OR IGNORE INTO todo VALUES ({','.join('?' * (6 + len(COLS)))})", batch)
    w.commit()
    print(f"{hit:,} of {seen:,} rows to redo → {WORK_DB}", flush=True)


def _from_api(artist: str, title: str, album: str, duration: float | None) -> dict | None:
    q = {"artist_name": artist, "track_name": title, "album_name": album or ""}
    if duration:
        q["duration"] = str(round(duration))
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}", headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _from_dump(dump: sqlite3.Connection, akey: str, title: str, album: str, duration: float | None):
    r = dump.execute(
        "SELECT t.id, l.plain_lyrics, l.synced_lyrics FROM tracks t JOIN lyrics l ON l.id = t.last_lyrics_id "
        "WHERE t.artist_name_lower = ? AND t.name_lower = ? AND coalesce(t.album_name, '') = ? "
        "ORDER BY abs(coalesce(t.duration, 0) - ?) LIMIT 1",
        (akey, title.lower(), album or "", duration or 0)).fetchone()
    return {"id": r[0], "plainLyrics": r[1], "syncedLyrics": r[2]} if r else None


def fetch(source: str, rate: float, limit: int | None) -> None:
    w = work()
    dump = None if source == "api" else sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    todo = w.execute(
        "SELECT t.rid, t.akey, t.artist, t.title, t.album, t.duration, t.old_toks, t.old_wc FROM todo t "
        "LEFT JOIN new n ON n.rid = t.rid WHERE n.rid IS NULL ORDER BY t.rid").fetchall()
    if limit:
        todo = todo[:limit]
    print(f"{len(todo):,} rows to fetch from {source}", flush=True)
    counts: Counter[str] = Counter()
    t0 = time.time()
    for k, (rid, akey, artist, title, album, duration, toks, wc) in enumerate(todo, 1):
        try:
            got = _from_api(artist, title, album, duration) if dump is None else _from_dump(
                dump, akey, title, album, duration)
        except Exception as e:  # a network error: stop, the next run carries on here
            print(f"  stopped at row {rid}: {e}", flush=True)
            break
        status, values, lid = "missing", None, None
        if got and got.get("plainLyrics"):
            lid = got.get("id")
            plain, synced = got["plainLyrics"], got.get("syncedLyrics")
            if old_tokens(plain) != (toks, wc):
                status = "changed upstream"  # not the text these tokens came from
            else:
                st = reading.song_stats(title, plain, synced, duration)
                if st:
                    status = "ok"
                    st = {**st, "first_s": st["first"], "gap_s": st["gap"], "toks": _encode(st["cnt"])}
                    values = [st[c] for c in COLS]
        w.execute(f"INSERT INTO new (rid, status, lrclib_id, {', '.join(COLS)}) VALUES "
                  f"({','.join('?' * (3 + len(COLS)))})", [rid, status, lid] + (values or [None] * len(COLS)))
        counts[status] += 1
        if k % 200 == 0:
            w.commit()
            print(f"  …{k:,}/{len(todo):,} {dict(counts)} {time.time() - t0:.0f}s", flush=True)
        if dump is None and rate:
            time.sleep(1 / rate)
    w.commit()
    print(f"fetched: {dict(counts)}", flush=True)


def apply(batch: int = 2000) -> None:
    w = work()
    song = sqlite3.connect(SONG_DB)
    rows = w.execute(f"SELECT rid, {', '.join(COLS)} FROM new WHERE status = 'ok' AND applied = 0").fetchall()
    sets = ", ".join(f"{c} = ?" for c in COLS)
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        with song:
            song.executemany(f"UPDATE song_stat SET {sets} WHERE rowid = ?", [list(r[1:]) + [r[0]] for r in part])
        with w:
            w.executemany("UPDATE new SET applied = 1 WHERE rid = ?", [(r[0],) for r in part])
        print(f"  {min(i + batch, len(rows)):,}/{len(rows):,} applied", flush=True)


def rollback(batch: int = 2000) -> None:
    w = work()
    song = sqlite3.connect(SONG_DB)
    rows = w.execute(f"SELECT t.rid, {', '.join('t.old_' + c for c in COLS)} FROM todo t "
                     f"JOIN new n ON n.rid = t.rid WHERE n.applied = 1").fetchall()
    sets = ", ".join(f"{c} = ?" for c in COLS)
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        with song:
            song.executemany(f"UPDATE song_stat SET {sets} WHERE rowid = ?", [list(r[1:]) + [r[0]] for r in part])
        with w:
            w.executemany("UPDATE new SET applied = 0 WHERE rid = ?", [(r[0],) for r in part])
        print(f"  {min(i + batch, len(rows)):,}/{len(rows):,} rolled back", flush=True)


def status() -> None:
    w = work()
    print("to redo:", w.execute("SELECT count(*) FROM todo").fetchone()[0])
    for s, n, a in w.execute("SELECT status, count(*), sum(applied) FROM new GROUP BY status"):
        print(f"  {s}: {n:,} ({a or 0:,} applied)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--find", action="store_true")
    ap.add_argument("--fetch", metavar="SOURCE", help="'api' or the path of an LRCLIB dump")
    ap.add_argument("--rate", type=float, default=2.0, help="API requests per second")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--work", help="another work file (a trial run)")
    args = ap.parse_args()
    if args.work:
        global WORK_DB
        WORK_DB = args.work
    if args.find:
        find()
    if args.fetch:
        fetch(args.fetch, args.rate, args.limit)
    if args.apply:
        apply()
    if args.rollback:
        rollback()
    if args.status:
        status()


if __name__ == "__main__":
    main()
