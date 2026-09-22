# Hand reviews of the top catalogues

One file per artist, named by the artist's key (`lyricstats.db.normalize_key`),
read by `scripts/clean_catalogues.py` when it folds that artist. The rules in
`scripts/catalogue.py` run first; a review only corrects them. The top 500
artists (`output/review/top.tsv`) were reviewed by hand on 2026-09-22, the
next 251 (ranks 501–751, `output/review/next250.tsv`) the day after. Ranks
752 and down have the rules and the namesake check (below) only.

```json
{
  "artist": "Michael Jackson",
  "reviewed": "2026-09-22",
  "drop": {"ABC": "The Jackson 5", "Muscles": "written for Diana Ross"},
  "keep": ["Say Say Say"],
  "rename": {"Enrique Iglesias": "Miente"},
  "only": [],
  "note": "why the file looks the way it does"
}
```

- `drop`: title → why. Matched by the catalogue's title key, so "01 ABC" or
  "ABC (Remastered)" are the same entry. A drop matches the song's shown
  title only, so a drop whose uploads were merged into another song does
  nothing.
- `keep`: titles a rule set aside that are the artist's after all, most often
  a released covers album the ownership rule gave to the original artist.
- `rename`: a song shown under a wrong or broken title → its real title.
- `only`: a list curated in full; anything else is set aside.
- `remove`: instead of all of the above, the page is not an artist's page (the
  first importer split "Simon & Garfunkel" into "Simon" and "Garfunkel"; "AC"
  and "DC" are halves of "AC/DC"). The page is deleted and its uploads claim
  no songs from anyone else.

`_aliases_manual.tsv` folds pages into one: `alias<TAB>canonical`, for the
halves of a split duo credit that should land on the duo's page. Automatic
aliases ("beatles" → "thebeatles") are built by `clean_catalogues.py` into
`data/lrclib/_aliases.json`. Review an alias page's junk in the canonical
page's file.

## What a catalogue holds

The songs the artist performs on, as they would be listed on the artist's own
page of a lyrics site: songs where they are the artist, a co-lead or a credited
feature, released or circulating unreleased (their words either way). One entry
per song, in its studio version. Recordings in another language are separate
songs.

Set aside:

- another act's songs: a group the artist belonged to (The Jackson 5 under
  Michael Jackson, The Highwaymen under Waylon Jennings), a band member's solo
  work under the band, a namesake (Queen Latifah under Queen, She & Him under
  HIM);
- songs the artist wrote or produced for others but does not sing;
- their remixes of other artists' songs, and mash-ups;
- medleys, megamixes, live medleys;
- a second copy of a song: a remix, live take, demo or edit that kept a title
  of its own, a typo'd title, another transliteration;
- what is not a song: interviews, commentary, spoken skits, intros and
  interludes, speeches, radio spots and station IDs, spoken narrations;
- an upload whose words are another song's (an instrumental's title carrying
  somebody else's lyrics).

Covers the artist recorded and released are theirs and stay; a live or radio
cover that was never released is set aside.

`_display.tsv` fixes display names the uploads got wrong ("simon  garfunkel",
"Beatles (the)"): `name<TAB>display<TAB>why`. Only the display changes; name
and name_key stay, so every stored link keeps resolving. `--commit` applies it
locally and `--prod-display` in production.

`_prefer.txt` pins the page's spelling when several spellings fold together
(the first importer read "Emerson, Lake & Palmer" as "Surname, First").

## Tools

In `tools/`:

- `compact.py START END [BUDGET]`: the review sheet for ranks START to END,
  from `data/lrclib/_clean_agg.db` (or `REPORT_DB`) and the ranked list
  `output/review/top.tsv` (or `TOP_TSV`; ranks 1–1000 are in
  `output/review-later/top1000.tsv`, kept out of `output/review/` so the
  namesake check still covers the ranks not reviewed by hand).
- `namesakes.py OUT_DIR [BUDGET]`: hint sheets for pages outside the ranked
  lists that hold a cluster of songs in a language the page otherwise does not
  sing in, from albums the rest never appears on — often a namesake. Nothing
  is dropped automatically: most such clusters are the artist's own.
- `write_reviews.py < batch.json`: writes review files from
  `{gkey: {"drop": {...}, "keep": [...], "rename": {...}}}`. An existing file
  is added to, never replaced.
- `check_reviews.py [gkey ...]`: lists review entries that match no song, or
  several.
