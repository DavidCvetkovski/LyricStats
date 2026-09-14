# Product expansions with bounded costs

## Implemented in this preview

- Song readings now show an interactive line map, repeated-line navigation,
  vocabulary accumulation, late-arriving words, word concordance and full text.
- Pasted text is analysed in browser memory, with a 50,000-character limit.
  Neither lyrics nor pasted artist/title metadata are uploaded or persisted.
- Song titles are suggested from the artist catalogue already in memory.
  Catalogue summaries open without an additional request; full text is explicit.
- Spotify search and artist links, bounded caches, request cancellation and
  autocomplete reuse make exploration smoother without background enrichment.
- A new sourced current-phenomenon issue replaces the previous Issue 02 and is
  the front page. Issue 01 remains accessible in the archive.
- Artist quotations require matching word counts and a matching catalogue title.
  Fabricated percentile estimates were removed. Shared count-up animations
  respect reduced-motion preferences.
- The legacy motif sync now matches exact normalized artist names, defaults to
  a read-only plan, caps a run at 20 named artists, and preserves prior values
  before explicitly requested updates. It has not been run against production.

## Next experiments worth building

1. **Compare two songs on the same page.** Reuse readings already in memory and
   draw the two vocabulary curves with explicit text-length normalization.
   Begin with pasted text or cached songs: no new backend service is needed.
2. **Verified recording links.** Start with an explicitly selected 20-song
   list. Store reviewed Spotify IDs alongside source/confidence and checkpoint
   after every lookup. Never enrich IDs during a visitor’s request. Current
   links deliberately open Spotify searches; no exact ID is guessed.
3. **Coverage that explains itself.** Carry existing source/build-date metadata
   in the normal artist response. Show what is indexed and why versions differ,
   without another page-load query. Keep zero/unknown section data distinct.
4. **A small editorial archive.** Issue cards and topic filters can be generated
   from a static manifest. Publication remains a deliberate preview build.

Backend cache and query improvements are tested in this branch but are not
part of the frontend deployment. They need a separate API preview before any
production promotion. No actual billing reduction has been measured.

For future data jobs: exact indexed reads, explicit size/time budgets, incremental
checkpoints, and new output paths. Never drop or recreate tables for a refresh.
Preserve all user databases and any artifact that cost more than two minutes to
compute. Do not introduce a scheduled crawler or bulk sync as a convenience.
