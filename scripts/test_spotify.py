import sqlite3
import pandas as pd
import json
import os
import sys


def normalize(title):
    if not isinstance(title, str):
        return ""
    import unicodedata
    import re

    s = title.lower()
    # basic normalize
    s = re.sub(r"[\(\[\{][^)\]\}]*[\)\]\}]", "", s)  # remove brackets
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if (c.isalnum() or c.isspace()) else " " for c in s)
    return " ".join(s.split())


print("Loading Spotify dataset...", flush=True)
url = (
    "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv"
)
try:
    df_spotify = pd.read_csv(url, usecols=["artists", "track_name"])
except Exception as e:
    print(f"Failed to download: {e}")
    sys.exit(1)

# Build a dictionary of normalized titles per artist
spotify_artists = {}
for i, row in df_spotify.iterrows():
    artist_str = str(row["artists"]).lower()
    # Spotify uses ';' to separate artists, e.g. "Ingrid Michaelson;ZAYN"
    artists = [a.strip() for a in artist_str.split(";")]
    track_norm = normalize(row["track_name"])
    for a in artists:
        if a not in spotify_artists:
            spotify_artists[a] = set()
        spotify_artists[a].add(track_norm)

print(f"Loaded {len(spotify_artists)} artists from Spotify.", flush=True)

# Check against Genius
print("Connecting to Genius DB...", flush=True)
db_path = "/Users/davidcvetkovski/Documents/Personal Projects/LyricStats/data/_import_tmp.db"
conn = sqlite3.connect(db_path)

artists_to_check = ["taylor swift", "lana del rey", "jala brat", "buba corelli"]

results = {}

for artist in artists_to_check:
    print(f"Checking {artist}...", flush=True)
    # Get Genius songs
    genius_songs = conn.execute(
        "SELECT title, wc, has_sec FROM song_stat WHERE LOWER(artist) = ? ORDER BY wc DESC",
        (artist,),
    ).fetchall()

    spotify_set = spotify_artists.get(artist, set())
    print(f"  Spotify has {len(spotify_set)} unique tracks for {artist}")
    print(f"  Genius has {len(genius_songs)} unique tracks for {artist}")

    missing_in_spotify = []
    for title, wc, has_sec in genius_songs:
        norm_t = normalize(title)
        if not norm_t:
            continue
        if norm_t not in spotify_set:
            missing_in_spotify.append(
                f"{title} (Words: {wc}, Sections: {'Yes' if has_sec else 'No'})"
            )

    results[artist] = {
        "genius_total": len(genius_songs),
        "spotify_total": len(spotify_set),
        "missing_in_spotify": missing_in_spotify,
    }

for artist, data in results.items():
    print(f"\n======================================")
    print(f"Artist: {artist.title()}")
    print(f"Genius Track Count: {data['genius_total']}")
    print(f"Spotify Track Count: {data['spotify_total']}")
    print(f"Songs in Genius but NOT in Spotify Dataset: {len(data['missing_in_spotify'])}")
    print(f"Top 20 examples of songs Spotify 'missed':")
    for s in data["missing_in_spotify"][:20]:
        print(f"  - {s}")
