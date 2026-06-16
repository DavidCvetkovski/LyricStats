"""Configuration — reads from environment variables and .env files."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv()


def get(key: str, default: str | None = None) -> str | None:
    return os.getenv(key) or default


GENIUS_TOKEN: str | None = get("GENIUS_TOKEN")


def _truthy(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    return val.strip().lower() not in {"0", "false", "no", "off", ""}


# Whether to attempt scraping full lyrics (with [Chorus]/[Verse] section tags)
# from genius.com pages. Works from residential IPs (your laptop/phone) but
# Cloudflare 403s datacenter IPs, so we disable it on Vercel (GENIUS_SCRAPE=0)
# and fall back to lrclib/lyrics.ovh there.
GENIUS_SCRAPE: bool = _truthy(get("GENIUS_SCRAPE", "1"), default=True)

# Whether to enable live fetching to sample new songs via the Genius API.
LIVE_FETCH_ENABLED: bool = _truthy(get("LIVE_FETCH_ENABLED", "1"), default=True)

# Whether to restrict lyric fetching to ONLY use lrclib (skipping Genius and ovh).
ONLY_LRCLIB: bool = _truthy(get("ONLY_LRCLIB", "0"), default=False)

# Shared secret guarding the /api/ingest endpoint used by the seed scripts to
# push full-quality lyrics into the cloud database. Unset = endpoint disabled.
SEED_KEY: str | None = get("SEED_KEY")

# Postgres (Neon, etc.) in production; falls back to a local SQLite file when
# DATABASE_URL is unset so local dev and tests keep working as before.
DATABASE_URL: str | None = get("DATABASE_URL")
DB_PATH: Path = Path(get("LYRICSTATS_DB", "./data/lyricstats.db") or "./data/lyricstats.db")

# Only touch the filesystem for the SQLite fallback. On serverless (Postgres)
# the working dir is read-only except /tmp, so skip the mkdir entirely.
if not DATABASE_URL:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
