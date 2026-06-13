#!/usr/bin/env python3
"""Deduplicate release variants of songs in the precomputed database in-place.

Iterates over all artist aggregates in the local SQLite DB, parses their song lists,
groups duplicate versions of the same song (distinguishing different lengths like
5-min vs 10-min versions by checking word count similarity), updates the song count
and stats JSON, and writes back the cleaned records.
"""

import json
import os
import re
import sqlite3
import unicodedata

DB_PATH = "data/lyricstats.db"


def _alnum_squash(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


def remove_all_brackets(s: str) -> str:
    res = []
    depth = 0
    for char in s:
        if char in "([{":
            depth += 1
            res.append(" ")
        elif char in ")]}":
            if depth > 0:
                depth -= 1
            res.append(" ")
        elif depth == 0:
            res.append(char)
    return "".join(res)


PREFIX_NUMS_RE = re.compile(r"^\d+\s+")

QUALIFIERS = [
    "taylor s version", "taylors version", "taylor version",
    "from the vault", "sad girl autumn version", "sad girl autumn",
    "recorded at long pond studios", "long pond studios",
    "short film", "the short film", "extended tv", "extended",
    "10 minute version", "10 minute", "ten minute version", "ten minute",
    "10 minute versio",
    "explicit", "clean", "remix", "acoustic", "live", "demo", "edit", "version"
]
QUALIFIERS_RE = re.compile(r"\b(" + "|".join(re.escape(q) for q in QUALIFIERS) + r")\b", re.IGNORECASE)


def clean_title(title: str, artist_name: str) -> str:
    s = title.lower()
    art = artist_name.lower()
    if s.startswith(art):
        s = s[len(art):]
    if s.endswith(art):
        s = s[:-len(art)]

    # Remove text in parentheses/brackets (handles unclosed ones cleanly)
    s = remove_all_brackets(s)

    # squash punctuation
    s = _alnum_squash(s)

    # Remove prefix numbers (like "05 ")
    s = PREFIX_NUMS_RE.sub("", s)

    # Remove common qualifiers anywhere in the string
    s = QUALIFIERS_RE.sub(" ", s)

    s = " ".join(s.split())
    return s or _alnum_squash(title)



def deduplicate_songs(songs: list, artist_name: str) -> list:
    cleaned = []
    for s in songs:
        cleaned.append((s, clean_title(s[0], artist_name)))

    groups = []

    for s, ct in cleaned:
        wc = s[2]
        matched = False
        for g in groups:
            rep, rep_ct = g[0]
            rep_wc = rep[2]

            if ct == rep_ct:
                if rep_wc == 0 or wc == 0:
                    g.append((s, ct))
                    matched = True
                    break
                diff = abs(rep_wc - wc) / max(rep_wc, 1)
                if diff <= 0.18:
                    g.append((s, ct))
                    matched = True
                    break
        if not matched:
            groups.append([(s, ct)])

    res = []
    for g in groups:
        songs_in_group = [item[0] for item in g]
        # Sort by: 1) has year, 2) shorter title, 3) higher word count
        songs_in_group.sort(key=lambda s: (
            s[1] is None,
            len(s[0]),
            -s[2]
        ))
        res.append(songs_in_group[0])

    res.sort(key=lambda s: s[2], reverse=True)
    return res


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id, display_name, song_count, stats_json, songs_json FROM artistaggregate")
    rows = cur.fetchall()

    print(f"Processing {len(rows):,} artists in local database...")
    updates = []
    total_removed = 0

    for r_id, display_name, old_count, stats_str, songs_str in rows:
        try:
            songs = json.loads(songs_str)
            stats = json.loads(stats_str)
        except Exception as e:
            print(f"  Failed parsing JSON for {display_name}: {e}")
            continue

        deduped = deduplicate_songs(songs, display_name)
        n_deduped = len(deduped)

        if n_deduped < len(songs):
            removed = len(songs) - n_deduped
            total_removed += removed

            # Update stats
            stats["song_count"] = n_deduped
            # Adjust avg_words_per_song if total_words is available
            if "total_words" in stats:
                new_total_words = sum(s[2] for s in deduped)
                stats["total_words"] = new_total_words
                stats["avg_words_per_song"] = round(new_total_words / max(n_deduped, 1), 2)

            updates.append((
                n_deduped,
                json.dumps(stats, ensure_ascii=False),
                json.dumps(deduped, ensure_ascii=False),
                r_id
            ))

    if updates:
        print(f"Applying deduplication updates to {len(updates):,} artists...")
        conn.executemany(
            "UPDATE artistaggregate SET song_count = ?, stats_json = ?, songs_json = ? WHERE id = ?",
            updates
        )
        conn.commit()
        print(f"✅ Successfully deduplicated {total_removed:,} song records locally!")
    else:
        print("No duplicates found to merge.")

    conn.close()


if __name__ == "__main__":
    main()
