# Hand reviews of the top catalogues

One file per artist, named by the artist's key (`lyricstats.db.normalize_key`),
read by `scripts/clean_catalogues.py` when it folds that artist. The rules in
`scripts/catalogue.py` run first; a review only corrects them.

```json
{
  "artist": "Michael Jackson",
  "reviewed": "2026-09-22",
  "drop": {"ABC": "The Jackson 5", "Muscles": "written for Diana Ross"},
  "keep": ["Say Say Say"],
  "only": []
}
```

- `drop`: title → why. Matched by the catalogue's title key, so "01 ABC" or
  "ABC (Remastered)" are the same entry.
- `keep`: titles a rule set aside that are the artist's after all.
- `only`: a list curated in full; anything else is set aside.

## What a catalogue holds

The songs the artist performs on, as they would be listed on the artist's own
page of a lyrics site: songs where they are the artist, a co-lead or a credited
feature, released or circulating unreleased (their words either way). One entry
per song, in its studio version.

Set aside:

- another act's songs: a group the artist belonged to (The Jackson 5 under
  Michael Jackson, Destiny's Child under Beyoncé), a band member's solo work
  under the band, a namesake (Queen Latifah under Queen);
- songs the artist wrote or produced for others but does not sing;
- their remixes of other artists' songs, and mash-ups;
- medleys, megamixes, live medleys;
- a second copy of a song: a remix, live take, demo or edit that kept a title
  of its own, a typo'd title;
- what is not a song: interviews, commentary, spoken skits and intros,
  speeches, radio promos.

Covers the artist recorded and released are theirs and stay; a live or radio
cover that was never released is set aside.
