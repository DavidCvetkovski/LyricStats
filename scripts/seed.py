#!/usr/bin/env python3
"""Seed the LyricStats database with full-quality lyrics.

Run this on a machine with a *residential* IP (your MacBook, or your iPhone via
a-Shell) — genius.com lets those scrape full lyrics (with [Chorus]/[Verse]
section tags), which Vercel's servers can't. It then POSTs each song to the
deployed app's /api/ingest endpoint, which writes to the shared database.

Dependencies (just two, both pip-installable on a-Shell / iSH):
    pip install requests lyricsgenius

Usage:
    export LYRICSTATS_API_BASE="https://lyricstats-api.vercel.app"
    export SEED_KEY="...the secret you set on Vercel..."
    export GENIUS_TOKEN="...your Genius token..."
    python seed.py "Jala Brat" "Buba Corelli" --songs 30

Anything you can override with a flag instead of an env var:
    python seed.py "Senidah" --songs 25 \
        --api-base https://lyricstats-api.vercel.app \
        --seed-key XXX --genius-token YYY
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

GENIUS_API = "https://api.genius.com"
UA = "LyricStats-Seeder/1.0"


# ── Genius official metadata API ────────────────────────────────────────────


def genius_get(token: str, path: str, params: dict | None = None) -> dict:
    r = requests.get(
        f"{GENIUS_API}{path}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": UA},
        params=params or {},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def resolve_artist(token: str, name: str) -> tuple[int, str, str | None]:
    data = genius_get(token, "/search", {"q": name})
    hits = data.get("response", {}).get("hits", [])
    target = name.strip().lower()
    best = None
    for h in hits:
        pa = (h.get("result") or {}).get("primary_artist") or {}
        if not pa.get("id"):
            continue
        if best is None:
            best = pa
        if (pa.get("name") or "").strip().lower() == target:
            best = pa
            break
    if not best:
        raise RuntimeError(f"artist not found: {name}")
    return int(best["id"]), best.get("name") or name, best.get("url")


def list_songs(token: str, artist_id: int, want: int) -> list[dict]:
    """Top songs by popularity, normalised to slim meta dicts."""
    out: list[dict] = []
    page: int | None = 1
    # Pull a little extra so songs we can't scrape don't starve the target.
    pool_target = want * 2 + 10
    while page and len(out) < pool_target:
        data = genius_get(
            token,
            f"/artists/{artist_id}/songs",
            {"per_page": 50, "page": page, "sort": "popularity"},
        )
        resp = data.get("response", {})
        for s in resp.get("songs", []) or []:
            if not s.get("id"):
                continue
            album = s.get("album")
            year = (s.get("release_date_components") or {}).get("year")
            pa = s.get("primary_artist") or {}
            out.append(
                {
                    "id": s.get("id"),
                    "title": s.get("title") or "?",
                    "url": s.get("url"),
                    "album": album.get("name") if isinstance(album, dict) else None,
                    "year": year,
                    "artist_id": pa.get("id"),
                    "artist_url": pa.get("url"),
                }
            )
        page = resp.get("next_page")
        if page:
            time.sleep(0.1)
    return out


# ── lyric scraping (residential IP only) ────────────────────────────────────


def make_genius_client(token: str):
    import lyricsgenius  # imported here so --help works without it installed

    client = lyricsgenius.Genius(
        token,
        timeout=20,
        retries=2,
        sleep_time=0.4,
        remove_section_headers=False,  # keep [Chorus]/[Verse] for section stats
        skip_non_songs=True,
    )
    client.verbose = False
    return client


def scrape_lyrics(client, url: str | None) -> str | None:
    if not url:
        return None
    try:
        lyrics = client.lyrics(song_url=url)
        lyrics = (lyrics or "").strip()
        return lyrics or None
    except Exception as e:  # noqa: BLE001
        print(f"      ! scrape failed: {e}", file=sys.stderr)
        return None


# ── push to the deployed app ────────────────────────────────────────────────


def ingest(api_base: str, seed_key: str, payload: dict) -> bool:
    try:
        r = requests.post(
            f"{api_base.rstrip('/')}/api/ingest",
            json=payload,
            headers={"X-Seed-Key": seed_key, "User-Agent": UA},
            timeout=30,
        )
        if r.status_code == 200:
            return True
        print(f"      ! ingest {r.status_code}: {r.text[:160]}", file=sys.stderr)
        return False
    except requests.RequestException as e:
        print(f"      ! ingest error: {e}", file=sys.stderr)
        return False


# ── orchestration ───────────────────────────────────────────────────────────


def seed_artist(
    token: str,
    client,
    api_base: str,
    seed_key: str,
    name: str,
    songs: int,
) -> int:
    print(f"→ {name}")
    try:
        artist_id, artist_name, artist_url = resolve_artist(token, name)
    except Exception as e:  # noqa: BLE001
        print(f"   skipped ({e})")
        return 0
    pool = list_songs(token, artist_id, songs)
    saved = 0
    for meta in pool:
        if saved >= songs:
            break
        title = meta["title"]
        lyrics = scrape_lyrics(client, meta.get("url"))
        if not lyrics:
            continue
        ok = ingest(
            api_base,
            seed_key,
            {
                "artist": artist_name,
                "title": title,
                "lyrics": lyrics,
                "album": meta.get("album"),
                "year": meta.get("year"),
                "genius_id": meta.get("id"),
                "artist_id": artist_id,
                "artist_url": artist_url,
            },
        )
        if ok:
            saved += 1
            print(f"   [{saved}/{songs}] {title}")
        time.sleep(0.3)  # be gentle with Genius
    print(f"   ✓ {artist_name}: {saved} songs seeded")
    return saved


def seed_artists(
    names: list[str],
    songs: int,
    api_base: str,
    seed_key: str,
    token: str,
) -> int:
    client = make_genius_client(token)
    total = 0
    for name in names:
        total += seed_artist(token, client, api_base, seed_key, name, songs)
    print(f"\nDone. {total} songs across {len(names)} artist(s).")
    return total


def _resolve(value: str | None, env: str, label: str) -> str:
    out = value or os.getenv(env)
    if not out:
        sys.exit(f"Missing {label}: pass --{label.replace('_', '-')} or set ${env}")
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Seed LyricStats with full lyrics.")
    p.add_argument("artists", nargs="+", help='Artist names, e.g. "Jala Brat"')
    p.add_argument("--songs", type=int, default=25, help="Songs per artist (default 25)")
    p.add_argument("--api-base", help="Deployed API base (env LYRICSTATS_API_BASE)")
    p.add_argument("--seed-key", help="Ingest secret (env SEED_KEY)")
    p.add_argument("--genius-token", help="Genius API token (env GENIUS_TOKEN)")
    args = p.parse_args(argv)

    api_base = _resolve(args.api_base, "LYRICSTATS_API_BASE", "api_base")
    seed_key = _resolve(args.seed_key, "SEED_KEY", "seed_key")
    token = _resolve(args.genius_token, "GENIUS_TOKEN", "genius_token")

    seed_artists(args.artists, args.songs, api_base, seed_key, token)


if __name__ == "__main__":
    main()
