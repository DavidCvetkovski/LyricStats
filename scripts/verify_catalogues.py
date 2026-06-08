"""Spot-check rebuilt ArtistAggregate catalogues for residual non-song junk.

Reads the local aggregates (data/lyricstats.db) and, for a set of artists prone
to junk (interviews, liner notes, tracklists, tour merch), prints the longest
catalogue entries + the 'longest song' highlight, and counts any titles still
matching obvious junk patterns. Run after a fold to eyeball quality.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats import db  # noqa: E402

# A loose "does this still look like junk?" net — broader than the import filter,
# only used here to flag leftovers for a human to eyeball.
_SUSPECT = re.compile(
    r"\b(interview|liner notes?|tracklist|discography|chart history|foreword|"
    r"prologue|epilogue|tour (costumes?|dates?|book|guide|setlist|special)|"
    r"costumes?|setlist|playlist|acceptance speech|commencement|"
    r"t[üu]rk[çc]e|[çc]eviri|s[öo]zleri|traducci[óo]n|tradu[çc][ãa]o|romaniz|"
    r"\bvmas?\b|grammys?|super ?bowl|halftime|documentary|transcript|"
    r"making of|behind the scenes)\b",
    re.IGNORECASE,
)

ARTISTS = [
    "Taylor Swift", "Drake", "Eminem", "Kanye West", "JAY-Z", "Kendrick Lamar",
    "Ariana Grande", "Rihanna", "The Weeknd", "Coldplay", "Ed Sheeran",
    "Lady Gaga", "Beyoncé", "BTS", "Lana Del Rey",
]


def check(name: str) -> None:
    agg = db.get_artist_aggregate(name)
    if not agg:
        print(f"\n### {name}: (no aggregate)")
        return
    songs = json.loads(agg.songs_json) if agg.songs_json else []
    stats = json.loads(agg.stats_json) if agg.stats_json else {}
    # songs_json rows: [title, year, wc, uniq, ttr, chorus, rep, has_sec]
    suspects = [s for s in songs if _SUSPECT.search(s[0] or "")]
    longest = stats.get("longest_song", {})
    print(f"\n### {agg.display_name}: {agg.song_count} songs · "
          f"{len(suspects)} suspect titles")
    print(f"   longest-song highlight: {longest.get('title','?')!r} "
          f"({longest.get('words','?')}w)")
    print("   top 6 by words:")
    for t, yr, wc, *_ in sorted(songs, key=lambda x: x[2], reverse=True)[:6]:
        mark = "⚠" if _SUSPECT.search(t or "") else " "
        print(f"     {mark} {wc:>4}w  {t[:54]}")
    if suspects:
        print(f"   ⚠ residual suspects ({len(suspects)}):")
        for s in suspects[:8]:
            print(f"       {s[2]:>4}w  {s[0][:54]}")


def main() -> None:
    names = sys.argv[1:] or ARTISTS
    for n in names:
        check(n)


if __name__ == "__main__":
    main()
