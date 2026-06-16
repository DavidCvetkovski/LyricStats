#!/usr/bin/env python3
"""Fetch all missing songs for Taylor Swift from Genius and populate the cache."""

from __future__ import annotations

import os
import sys
import time
import requests
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lyricstats import db, fetch


def main() -> None:
    token = "nsA7LEc-u2ZOyeCsa0ESU83pj7alMAfY4NjEph0_O-t9-n437vBxnZbTkxRallx8"
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get all cached song titles for Taylor Swift
    conn = sqlite3.connect("data/lyricstats.db")
    cached_songs = conn.execute(
        "SELECT title FROM song WHERE artist_id IN (SELECT id FROM artist WHERE name = 'taylor swift')"
    ).fetchall()
    cached_titles = {s[0].strip().lower() for s in cached_songs}
    conn.close()

    print(f"Already have {len(cached_titles)} cached songs for Taylor Swift.")

    # 2. Get Taylor Swift's artist ID on Genius (1177)
    artist_id = 1177

    # 3. Paginate through all songs on Genius
    page = 1
    fetched_count = 0

    # Get the Artist object from db
    a = db.get_artist("Taylor Swift")
    if not a:
        a = db.get_or_create_artist("Taylor Swift")

    print("Fetching missing songs from Genius API...")
    while True:
        url = f"https://api.genius.com/artists/{artist_id}/songs?page={page}&per_page=50"
        res = requests.get(url, headers=headers).json()
        songs = res.get("response", {}).get("songs", [])
        if not songs:
            break

        for s_meta in songs:
            title = s_meta.get("title")
            s_id = s_meta.get("id")
            if not title or not s_id:
                continue

            # Skip if already cached
            if title.strip().lower() in cached_titles:
                continue

            # Skip non-song types if they are obviously tracklists, booklet, etc.
            if any(
                x in title.lower() for x in ("tracklist", "booklet", "liner notes", "discography")
            ):
                continue

            print(f"Fetching missing song: {title} (ID: {s_id})")
            try:
                # Use fetch_one_by_id to fetch and cache
                saved = fetch.fetch_one_by_id(a, s_id, title)
                if saved:
                    fetched_count += 1
                time.sleep(0.5)  # rate limit safety
            except Exception as e:
                print(f"Failed to fetch {title}: {e}")

        page += 1

    print(f"Done! Fetched and cached {fetched_count} missing songs.")


if __name__ == "__main__":
    main()
