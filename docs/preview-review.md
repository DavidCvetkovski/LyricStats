# Product preview review — 14 September 2026

Branch: `codex/song-experience-preview`. Site changes are being committed and
pushed to this dedicated branch. Existing unrelated workspace files remain
local. Preview URLs and deployment reports are retained in `output/`.

## Navigation and publication design

The masthead has three clear sections: Journal, Songs and Artists. The old
volume label is now a native issue selector with both edition titles and a
link to the archive. It supports keyboard opening, Escape, outside click and
normal tab navigation. The selector closes on issue navigation.

`/issues` presents distinct typographic covers for both editions. Issue pages
have an All issues breadcrumb. The shared colophon includes both issue links
and the creator credit as an italic imprint byline, aligned with the publication
wordmark. Shared issue metadata keeps menu, archive and footer consistent.
The muted ink token was darkened for readable small labels. The shared masthead
wordmark is no longer an extra H1; a skip link leads to the page content.

Design references: The Paris Review’s issue/archive separation
(https://www.theparisreview.org/) and The Pudding’s identifiable story archive
(https://pudding.cool/). The implementation uses LyricStats’ existing type,
paper and oxblood palette, with no new imagery, fonts or UI dependencies.

## Delivered

The song page is rebuilt around animated editorial sections, a selectable line
map, repeated-line navigation, vocabulary accumulation, words introduced in the
second half and word concordance. Plain Spotify search links and artist links
connect the reading to listening and further exploration. Missing lyrics offer
a direct route into private pasted-text analysis. Pasted text and its metadata
stay in browser memory; the input is capped at 50,000 characters.

Issue 02 is “The hit that wouldn’t stay in 2012,” about current catalogue-hit
revivals. It is the front page; Issue 01 remains at `/issues/01`. Source links,
chart periods, issue metadata and shared explanatory copy were checked for
consistency. Neither issue performs runtime research or database queries.

Artist quotations require matching word and track evidence. The saved live
Jala Brat response contains an unrelated Hebrew quote; the revised browser
correctly suppresses it and displays “mala,” 240 recorded appearances, instead.
No language is banned. Unsupported estimated percentile claims were removed.
The old sync script’s row-number join is a plausible source of cross-artist
contamination; historical execution was not established. Its replacement uses
exact artist identities, defaults to a saved read-only plan and never loads
whole tables. No production sync or data repair was executed.

## Verification

- 40 frontend tests passed, including text analysis, cache behavior and quote
  evidence. TypeScript passed. The production build prerendered all page routes.
- 152 backend tests passed with isolated test databases.
- Desktop (1280 px) and phone (390 px) compositions inspected locally.
- Selecting a returning line selected the corresponding numbered line and
  changed map mode. Word search found the expected original test-song line.
- Missing-song error recovered through pasted-text analysis.
- Opening a song from an already-loaded artist catalogue added no API request;
  explicit full-text expansion added one request with `full=1`.
- Browser logs showed no errors during the main song interaction checks.
- The deployed browser inspection was blocked by automatic approval review
  because its review service reported a usage limit. No workaround was used.
  Deployment readiness is checked separately through Vercel’s status command.

## Cost and preservation

Frontend preview deployments only. The substantial rebuild uploaded 106.4 KB
incrementally. The final follow-up uploaded 29.6 KB for copy/metadata consistency.
The final source manifest is 52 files, 524,989 bytes; local environment files,
databases, dependencies, build caches and output artifacts are excluded.

The frontend uses the existing API. Backend query/cache improvements are
branch-local and were not deployed. First uncached searches and full-text
requests can still incur existing API work; no measured billing savings are
claimed. Interactive reading and pasted-text analysis run in the browser.

No user database was deleted, rebuilt, synced or overwritten. One live artist
response was saved for diagnosis and reused in local fixtures. No broad data
scan or bulk enrichment job ran. The superseded issue, extraction snapshot,
exporter, test logs and source backups remain available.

See `docs/issue-02.md` for editorial provenance and `docs/upgrade-options.md`
for the next bounded product experiments.

Creator credit follow-up: the shared footer credits David Cvetkovski on every page. This preview-only update uploaded one changed file (1,000 bytes).
