#!/usr/bin/env python3
"""Seed the most popular Balkan / ex-Yu artists in one go.

Same mechanics as seed.py (residential IP → Genius scrape → /api/ingest), but
with a curated artist list baked in. Edit the lists below freely.

    export LYRICSTATS_API_BASE="https://lyricstats-api.vercel.app"
    export SEED_KEY="...secret..."
    export GENIUS_TOKEN="...token..."
    python seed_balkan.py                # all curated artists, 25 songs each
    python seed_balkan.py --songs 40     # deeper catalogues
    python seed_balkan.py --only "Senidah" "Coby"   # just a few
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow `python scripts/seed_balkan.py` from the repo root to import seed.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed import _resolve, seed_artists  # noqa: E402

# ── YOUR MUST-HAVES ─────────────────────────────────────────────────────────
# Drop the artists you definitely want at the front here; they get seeded first.
MUST_HAVES: list[str] = [
    "Jala Brat",
    "Buba Corelli",
]

# ── Curated default: popular ex-Yu / Balkan artists ─────────────────────────
# Skewed toward rap/trap and modern pop (strongest Genius coverage). Anything
# not found or without scrapeable lyrics is simply skipped.

SERBIAN_BOSNIAN_RAP = [
    "Rasta",
    "Coby",
    "Devito",
    "Nucci",
    "Voyage",
    "Surreal",
    "Mili",
    "Fox",
    "Hiljson Mandela",
    "Đus",
    "Sha",
    "THCF",
    "Bvana",
    "Marko Louis",
    "Relja Popović",
]

POP_TRAP = [
    "Senidah",
    "Teodora",
    "Breskvica",
    "Desingerica",
    "Hurricane",
    "Konstrakta",
]

CROATIAN = [
    "Vojko V",
    "Grše",
    "Hladno Pivo",
    "TBF",
    "Severina",
    "Gibonni",
]

MACEDONIAN = [
    "DNK",
    "Vrčak",
    "Kaliopi",
    "Toše Proeski",
    "Elena Risteska",
]

POP_FOLK = [
    "Dino Merlin",
    "Zdravko Čolić",
    "Halid Bešlić",
    "Aca Lukas",
    "Ceca",
    "Lepa Brena",
]


def curated_list() -> list[str]:
    """Must-haves first, then the rest, de-duplicated, order preserved."""
    everyone = MUST_HAVES + SERBIAN_BOSNIAN_RAP + POP_TRAP + CROATIAN + MACEDONIAN + POP_FOLK
    seen: set[str] = set()
    ordered: list[str] = []
    for name in everyone:
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(name)
    return ordered


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Seed curated Balkan artists.")
    p.add_argument("--songs", type=int, default=25, help="Songs per artist (default 25)")
    p.add_argument("--only", nargs="*", help="Seed only these names (subset of any list)")
    p.add_argument("--api-base", help="Deployed API base (env LYRICSTATS_API_BASE)")
    p.add_argument("--seed-key", help="Ingest secret (env SEED_KEY)")
    p.add_argument("--genius-token", help="Genius API token (env GENIUS_TOKEN)")
    p.add_argument("--list", action="store_true", help="Print the artist list and exit")
    args = p.parse_args(argv)

    names = args.only if args.only else curated_list()

    if args.list:
        for n in names:
            print(n)
        print(f"\n{len(names)} artists.")
        return

    api_base = _resolve(args.api_base, "LYRICSTATS_API_BASE", "api_base")
    seed_key = _resolve(args.seed_key, "SEED_KEY", "seed_key")
    token = _resolve(args.genius_token, "GENIUS_TOKEN", "genius_token")

    print(f"Seeding {len(names)} artist(s), up to {args.songs} songs each.\n")
    seed_artists(names, args.songs, api_base, seed_key, token)


if __name__ == "__main__":
    main()
