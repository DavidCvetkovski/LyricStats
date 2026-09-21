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

## The song page

A song lives at `/song/<artist>/<title>`, slugs on both sides (`/song/michael-jackson/thriller`).
The page is rendered on the server from one call to `/api/song?artist=…&title=…`, which takes
names or slugs and answers with the text, its **reading** and where the song stands:

- `lyricstats/reading.py` — the per-song numbers (words, distinct, repetition, the returning
  line, title drops, rhyme, and from synced lyrics the clock: first word, longest silence,
  busiest fifteen seconds, words per tenth). The LRCLIB importer folds the same function into
  every catalogue, so a song page and its artist's catalogue agree to the digit.
- `catalogue` — the song's rank among the artist's songs for words, variety and repetition,
  from the same `songs_json` the artist page reads.
- `percentiles` — the song against the whole archive, from `lyricstats/data/song_quantiles.json`.
  Rebuild that table after a new import:

  ```bash
  uv run python scripts/build_song_quantiles.py   # ~30 s over data/lrclib/_song_stat.db
  ```

Old `/song?artist=…&title=…` links redirect to the slug address.

The page opens on the text itself: one lead figure, and the words folded to their first lines
until asked for. Opened, the sheet carries the reading's marks — the returning line underlined
and counted, the title highlighted where it is sung, the minute each line lands (when the
provider had a timed text; `reading.line_at`) and the silences between lines drawn as rules.
`/song/<artist>/<title>#text` opens it straight away; the search page's "Just the words"
button goes there.

## The signature

The artist page's signature — the word that is theirs — comes from `scripts/build_signatures.py`,
which reads the big local tables (`data/lrclib/_artist_tok.db`, `_song_stat.db`):

- a word has to recur across the catalogue (song spread, not raw count, so a word shouted a
  hundred times in one song does not qualify), and
- be rarer among artists singing in the same language (a small function-word list tells the
  language from an artist's most frequent words; rarity is judged within that language),
- with a hook line that carries it, when one of the artist's songs has one.

It also stores the *staple* (the word they say most, grammar and ad-libs set aside), the
runner-ups, and three more corpus percentiles (`question_share`, `avg_repetition_ratio`,
`avg_word_length`). Hand-curated motifs in `data/reviews/*.json` win over the score.

```bash
uv run python scripts/build_signatures.py --df       # document frequency per language, ~1 min
uv run python scripts/build_signatures.py --only "Kendrick Lamar" --show 8   # look before writing
uv run python scripts/build_signatures.py --write    # every artist with ≥ 25 songs, ~45 min
uv run python scripts/build_signatures.py --prod-plan output/signatures-prod.json   # read-only
uv run python scripts/build_signatures.py --prod-apply output/signatures-prod.json  # one UPDATE
```

The production plan is computed against production's own song lists, because some catalogues
were curated by hand up there, and it is applied as one server-side merge into `stats_json`.

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
