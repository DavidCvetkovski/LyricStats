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

Production serves at <https://lyricstats.dev> (`www` 308-redirects to the
apex via `next.config.ts`; the API answers at <https://api.lyricstats.dev>).

## SEO

- `lib/site.ts` — the canonical origin (`SITE_URL`), used everywhere below.
- `app/sitemap.ts` / `app/robots.ts` — generate `/sitemap.xml` and
  `/robots.txt`.
- `app/layout.tsx` — site-wide metadata: `metadataBase`, title template,
  canonical, Open Graph / Twitter tags.
- `app/artist/layout.tsx`, `app/song/layout.tsx` — per-route titles,
  descriptions and canonicals (the pages themselves are client components,
  so their metadata lives in these layouts).

## Test

```bash
npm test
```
