# LyricStats — web frontend

Next.js (App Router) frontend for LyricStats. Talks to the FastAPI backend in
the repo root.

## Develop

From the repo root, `make run` starts both halves (FastAPI on :8000, Next.js
on :3000). To run just this app:

```bash
npm install
npm run dev
```

In dev, `/api/*` is proxied to the local FastAPI process via the rewrite in
`next.config.ts` (override the target with `API_INTERNAL`).

## Deploy

Deployed as its own Vercel project (`lyricstats`), rooted at `web/`. Set
`NEXT_PUBLIC_API_BASE` to the API project's URL (e.g.
`https://lyricstats-api.vercel.app`) — when it's set, the browser calls the
Python API directly and the dev rewrite is unused.

## Test

```bash
npm test
```
