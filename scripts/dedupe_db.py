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
import concurrent.futures
import multiprocessing

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
    "taylor s version",
    "taylors version",
    "taylor version",
    "from the vault",
    "sad girl autumn version",
    "sad girl autumn",
    "recorded at long pond studios",
    "long pond studios",
    "short film",
    "the short film",
    "extended tv",
    "extended",
    "10 minute version",
    "10 minute",
    "ten minute version",
    "ten minute",
    "10 minute versio",
    "explicit",
    "clean",
    "remix",
    "acoustic",
    "live",
    "demo",
    "edit",
    "version",
]
QUALIFIERS_RE = re.compile(
    r"\b(" + "|".join(re.escape(q) for q in QUALIFIERS) + r")\b", re.IGNORECASE
)


def clean_title(title: str, artist_name: str) -> str:
    s = title.lower()
    art = artist_name.lower()
    if s.startswith(art):
        s = s[len(art) :]
    if s.endswith(art):
        s = s[: -len(art)]

    # Split on common metadata delimiters and check if the first part is an artist list
    known_lower = {
        "buba corelli",
        "jala brat",
        "coby",
        "devito",
        "rasta",
        "voyage",
        "senidah",
        "nucci",
        "hava",
        "taylor swift",
    }
    changed = True
    while changed:
        changed = False
        for delim in (":", "|", " - "):
            if delim in s:
                parts = s.split(delim, 1)
                part0 = parts[0].strip()
                contains_artist = (
                    art in part0
                    or any(ka in part0 for ka in known_lower)
                    or "feat." in part0
                    or "ft." in part0
                )
                if contains_artist:
                    s = parts[1]
                    changed = True
                    break
                else:
                    s = parts[0]
                    changed = True
                    break

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


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def is_similar_title(t1: str, t2: str, use_levenshtein: bool = True) -> bool:
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True
    if t1.startswith(t2) or t2.startswith(t1):
        return True
    if t1.endswith(t2) or t2.endswith(t1):
        return True
    if not use_levenshtein:
        return False
    len1, len2 = len(t1), len(t2)
    threshold = max(1, int(0.2 * max(len1, len2)))
    if abs(len1 - len2) > threshold:
        return False
    dist = levenshtein_distance(t1, t2)
    return dist <= threshold


def deduplicate_songs(songs: list, artist_name: str) -> list:
    # If the catalogue is huge (>500 tracks), disable Levenshtein to avoid O(N^2) bottlenecks
    use_levenshtein = len(songs) <= 500

    groups = []
    for s in songs:
        ct = clean_title(s[0], artist_name)
        wc = s[2]
        matched = False
        for g in groups:
            rep, rep_ct = g[0]
            rep_wc = rep[2]

            wc_ok = False
            if rep_wc == 0 or wc == 0:
                wc_ok = True
            else:
                diff = abs(rep_wc - wc) / max(rep_wc, 1)
                if diff <= 0.18:
                    wc_ok = True

            if wc_ok and is_similar_title(ct, rep_ct, use_levenshtein=use_levenshtein):
                g.append((s, ct))
                matched = True
                break
        if not matched:
            groups.append([(s, ct)])

    res = []
    for g in groups:
        songs_in_group = [item[0] for item in g]
        songs_in_group.sort(key=lambda s: (s[1] is None, len(s[0]), -s[2]))
        res.append(songs_in_group[0])

    res.sort(key=lambda s: s[2], reverse=True)
    return res


def process_artist_chunk(rows: list) -> tuple[list, int]:
    updates = []
    removed_count = 0
    for r_id, display_name, old_count, stats_str, songs_str in rows:
        try:
            songs = json.loads(songs_str)
            stats = json.loads(stats_str)
        except Exception:
            continue

        deduped = deduplicate_songs(songs, display_name)
        n_deduped = len(deduped)

        if n_deduped < len(songs):
            removed = len(songs) - n_deduped
            removed_count += removed

            # Update stats
            stats["song_count"] = n_deduped
            if "total_words" in stats:
                new_total_words = sum(s[2] for s in deduped)
                stats["total_words"] = new_total_words
                stats["avg_words_per_song"] = round(new_total_words / max(n_deduped, 1), 2)

            updates.append(
                (
                    n_deduped,
                    json.dumps(stats, ensure_ascii=False),
                    json.dumps(deduped, ensure_ascii=False),
                    r_id,
                )
            )
    return updates, removed_count


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT id, display_name, song_count, stats_json, songs_json FROM artistaggregate"
    )
    rows = cur.fetchall()
    conn.close()

    print(f"Processing {len(rows):,} artists in local database using multicore parallelization...")

    num_workers = max(1, multiprocessing.cpu_count())
    chunk_size = (len(rows) + num_workers - 1) // num_workers
    chunks = [rows[i : i + chunk_size] for i in range(0, len(rows), chunk_size)]

    updates = []
    total_removed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_artist_chunk, chunk) for chunk in chunks]
        for f in concurrent.futures.as_completed(futures):
            chunk_updates, removed = f.result()
            updates.extend(chunk_updates)
            total_removed += removed

    if updates:
        print(f"Applying deduplication updates to {len(updates):,} artists...")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executemany(
            "UPDATE artistaggregate SET song_count = ?, stats_json = ?, songs_json = ? WHERE id = ?",
            updates,
        )
        conn.commit()
        conn.close()
        print(f"✅ Successfully deduplicated {total_removed:,} song records locally!")
    else:
        print("No duplicates found to merge.")

    deduplicate_song_cache(DB_PATH)


def deduplicate_song_cache(db_path: str) -> None:
    print("Deduplicating the live-cached song table...")
    conn = sqlite3.connect(db_path)
    artists = conn.execute("SELECT id, name FROM artist").fetchall()

    total_deleted = 0
    for artist_id, artist_name in artists:
        songs = conn.execute(
            "SELECT id, title, lyrics, stats_json FROM song WHERE artist_id = ?", (artist_id,)
        ).fetchall()
        if not songs:
            continue

        song_list = []
        for song_id, title, lyrics, stats_json in songs:
            wc = 0
            if stats_json:
                try:
                    wc = json.loads(stats_json).get("word_count", 0)
                except Exception:
                    pass
            if wc == 0 and lyrics:
                wc = len(lyrics.split())
            song_list.append([title, None, wc, song_id])

        use_levenshtein = len(song_list) <= 500
        groups = []
        for s in song_list:
            ct = clean_title(s[0], artist_name)
            wc = s[2]
            matched = False
            for g in groups:
                rep, rep_ct = g[0]
                rep_wc = rep[2]

                wc_ok = False
                if rep_wc == 0 or wc == 0:
                    wc_ok = True
                else:
                    diff = abs(rep_wc - wc) / max(rep_wc, 1)
                    if diff <= 0.18:
                        wc_ok = True

                if wc_ok and is_similar_title(ct, rep_ct, use_levenshtein=use_levenshtein):
                    g.append((s, ct))
                    matched = True
                    break
            if not matched:
                groups.append([(s, ct)])

        for g in groups:
            if len(g) > 1:
                songs_in_group = [item[0] for item in g]
                songs_in_group.sort(key=lambda s: (len(s[0]), -s[2]))
                delete_ids = [s[3] for s in songs_in_group[1:]]
                if delete_ids:
                    conn.executemany(
                        "DELETE FROM song WHERE id = ?", [(did,) for did in delete_ids]
                    )
                    total_deleted += len(delete_ids)

    conn.commit()
    conn.close()
    print(f"✅ Successfully deduplicated {total_deleted} song cache entries!")


if __name__ == "__main__":
    main()
