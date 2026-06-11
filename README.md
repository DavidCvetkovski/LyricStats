# LyricStats

A small web app that shows stats for lyrics — per song and per artist. **Live at [lyricstats.dev](https://lyricstats.dev)** (API at [api.lyricstats.dev](https://api.lyricstats.dev)).

Pulls lyrics from Genius (with lrclib / lyrics.ovh fallbacks), caches everything in SQLite locally (Postgres in production), and computes a growing set of stats: word counts, vocabulary richness, top words, structure, line repetition, chorus share, and more.

The site is styled as a quarterly broadsheet: the front page is the current issue's feature essay, written from the database itself. Issue 01, "The Monsters of Sarajevo," reads Jala Brat & Buba Corelli's full catalogues (492 songs, 180k words) against their 2026 album *GODZILLA*.

See [PLAN.md](PLAN.md) for the original roadmap (historical — it predates the move from Streamlit to FastAPI + Next.js).

## Run it

Prereqs: [`uv`](https://docs.astral.sh/uv/), Node.js (with `npm`), and a free Genius API token from <https://genius.com/api-clients>.

```bash
cp .env.example .env
# put your token in .env: GENIUS_TOKEN=...
make run        # starts FastAPI on :8000 and Next.js on :3000
```

Then open <http://localhost:3000>. (`make api` runs the backend alone.)

## Deploy

Two Vercel projects, both linked in this repo:

- **`lyricstats-api`** (repo root) — the FastAPI backend as a Python serverless function (`api/index.py`, rewritten via `vercel.json`). Needs `DATABASE_URL`, `GENIUS_TOKEN`, `GENIUS_SCRAPE=0`, and optionally `SEED_KEY`.
- **`lyricstats`** (`web/`) — the Next.js frontend. Needs `NEXT_PUBLIC_API_BASE` pointing at the API project.

```bash
vercel --prod            # deploy the API (from the repo root)
cd web && vercel --prod  # deploy the frontend
```

Custom domains: `lyricstats.dev` (frontend; `www` redirects to the apex) and `api.lyricstats.dev` (API). The frontend ships `sitemap.xml`, `robots.txt`, and canonical/OG metadata — see [web/README.md](web/README.md#seo).

## Tests

```bash
make test            # python: pytest
cd web && npm test   # frontend: vitest
```

## Status

- ✅ Epoch 1 — foundations (fetcher, cache, app shell)
- ✅ Epoch 2 — core stats (lexical, structural, top words, charts)
- ✅ Epoch 3 — artist view (catalogue aggregation, sortable table)
- ⏳ Epoch 4 — rhyme, sentiment, readability, language mix
- 🟡 Epoch 5 — comparison page (deploy ✅ — live at [lyricstats.dev](https://lyricstats.dev))

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You may read, modify, and use this code for any **non-commercial** purpose. Commercial use is not permitted.
