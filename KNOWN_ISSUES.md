# Known issues & deferred cleanups

Found during the pre-deployment audit (June 2026). Fixed-on-the-spot items are
in git history; these are the ones deliberately left alone, smallest-risk
first.

## Deployment / infra

- **Sensitive env vars pull as empty** — `vercel env pull` writes `""` for
  vars stored as *sensitive* (e.g. production `NEXT_PUBLIC_API_BASE`,
  `GENIUS_TOKEN`). Don't be alarmed by an empty pull, and don't pipe a pulled
  production env file into anything that needs those values — use
  `.env.local` (Development) values instead, which pull fine.
- **Production API base is `https://api.lyricstats.dev`** (custom domain on
  the `lyricstats-api` project), not the `*.vercel.app` URL. Preview is
  wired to the same domain.

- **CORS regex is broad** — `backend/main.py` allows
  `https://.*\.vercel\.app`, i.e. *any* Vercel-hosted site can call the API
  from a browser. Low risk today (read-only public data; `/api/ingest` is
  guarded by `SEED_KEY`), but if the API ever grows mutating or quota-bound
  endpoints, tighten it to this project's own preview-URL pattern, e.g.
  `^https://lyricstats[a-z0-9-]*\.vercel\.app$`.
- **Docker/Fly leftovers** — `Dockerfile`, `.dockerignore` and
  `scripts/entrypoint.sh` remain from the removed Fly.io deployment
  (`entrypoint.sh` still says "inside one Fly machine"). They still work for
  generic self-hosting; delete them if Vercel is the only target.
- **`vercel.json` rewrites everything to the function** — `/(.*) →
  /api/index` means even static-asset-looking paths hit Python. Fine for an
  API-only project; just don't add static files to the root project expecting
  them to be served.

## Backend

- **No unique constraint on `(artist_id, title)`** — `db.upsert_song` does a
  read-then-write, so two concurrent serverless invocations fetching the same
  song can insert duplicate rows. Rare (the client fetches sequentially), but
  a DB-level unique constraint + `ON CONFLICT` upsert would close it.
- **`fetch_one_by_id` returns `True` even when no lyrics were found** — it
  saves an empty-lyrics row to mark the attempt (by design), but the caller's
  "saved" count in `fetch_artist_catalogue` then overcounts. Cosmetic.
- **`scripts/seed.sh` env parsing** — `export $(grep -v '^#' .env | xargs)`
  breaks on values containing spaces. Current `.env` values are simple, but
  it's fragile.

## Frontend

- **React `key={song.title}`** in the artist catalogue
  (`web/app/artist/page.tsx`) — collides if a catalogue contains two songs
  with identical titles (possible in dataset aggregates). Harmless warning
  today; proper fix is deduping titles at dataset-import time or keying on a
  stable id.
- **`errors.ts` AUTH_PATTERNS includes bare `/401/`** — any error message
  containing the digits "401" maps to "Genius API key isn't accepted".
  Unlikely in practice.

## Docs

- **`PLAN.md` is historical** — it still describes the Streamlit v1
  architecture. Kept as a record of the original roadmap; the README now says
  so. Epochs 4–5 listed there are still the live to-do list.
