#!/usr/bin/env python3
"""Give stored songs the clock they were saved without.

A song page shows the minute each line is sung (`reading.line_at`), the pace
and the silences, all from LRCLIB's timed transcription. The timed text is
never stored, only the numbers read from it, so songs saved before those
numbers existed have none, and nothing on the page would ever add them.

For every stored song whose reading has no line times, this asks LRCLIB for
the timed text once and reads the song again with it. The stored words are
kept as they are. A timed text that does not line up with them (another
recording, another song) is not used: the song keeps its reading without a
clock rather than one borrowed from something else.

  uv run python scripts/backfill_song_clock.py            # the local database
  uv run python scripts/backfill_song_clock.py --prod     # production (.env.prod)
  add --dry-run to report without saving, --redo to read timed songs again
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def prod_url() -> str:
    """DATABASE_URL from .env.prod, the way the other production scripts read it."""
    env = ROOT / ".env.prod"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.strip().split("=", 1)[1].split("#", 1)[0].strip().strip("'\"")
    sys.exit("DATABASE_URL not found in .env.prod")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prod", action="store_true", help="work on the production database")
    ap.add_argument("--dry-run", action="store_true", help="report, save nothing")
    ap.add_argument("--redo", action="store_true", help="also read songs that already have line times")
    ap.add_argument("--pause", type=float, default=0.5, help="seconds between LRCLIB requests")
    args = ap.parse_args()

    if args.prod:
        os.environ["DATABASE_URL"] = prod_url()

    # Imported after the database is chosen: the engine is made on import.
    from sqlmodel import select

    from lyricstats import db, fetch, stats
    from lyricstats.reading import reading

    print(f"database: {'production' if db.DATABASE_URL else 'local'}"
          f"{' (dry run)' if args.dry_run else ''}", flush=True)
    with db.session() as s:
        rows = s.exec(select(db.Song, db.Artist.name).join(db.Artist)).all()

    tally = {"timed already": 0, "no text": 0, "no timed text": 0, "did not line up": 0, "clocked": 0}
    for song, artist in rows:
        if not song.lyrics.strip():
            tally["no text"] += 1
            continue
        st = db.load_stats(song) or {}
        r = st.get("reading") or {}
        if r.get("line_at") and not args.redo:
            tally["timed already"] += 1
            continue

        timed = fetch._lrclib_lyrics(artist, song.title)
        time.sleep(args.pause)
        if not timed.synced:
            tally["no timed text"] += 1
            print(f"  –  {artist} – {song.title}: no timed text", flush=True)
            continue
        fresh = reading(song.title, song.lyrics, timed.synced, timed.duration)
        if not fresh or not fresh.get("line_at"):
            tally["did not line up"] += 1
            print(f"  ×  {artist} – {song.title}: the timed text does not match the words", flush=True)
            continue

        tally["clocked"] += 1
        timed_lines = sum(t is not None for t in fresh["line_at"])
        print(f"  ✓  {artist} – {song.title}: {timed_lines}/{len(fresh['line_at'])} lines timed, "
              f"{fresh.get('wpm') or '–'} words a minute", flush=True)
        if args.dry_run:
            continue
        if "section_sequence" not in st:
            st = stats.compute(song.lyrics).to_dict()
        db.save_stats(song, {**st, "reading": fresh})

    print(", ".join(f"{k}: {v}" for k, v in tally.items()))


if __name__ == "__main__":
    main()
