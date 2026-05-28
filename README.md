# LyricStats

A small web app that shows stats for lyrics — per song and per artist.

Pulls lyrics from Genius (with a lyrics.ovh fallback), caches everything locally in SQLite, and computes a growing set of stats: word counts, vocabulary richness, top words, structure, line repetition, chorus share, and more.

See [PLAN.md](PLAN.md) for the full roadmap.

## Run it

Prereqs: [`uv`](https://docs.astral.sh/uv/) and a free Genius API token from <https://genius.com/api-clients>.

```bash
cp .env.example .env
# put your token in .env: GENIUS_TOKEN=...
make install
make run
```

Then open the URL Streamlit prints (usually <http://localhost:8501>).

## Tests

```bash
make test
```

## Status

- ✅ Epoch 1 — foundations (fetcher, cache, app shell)
- ✅ Epoch 2 — core stats (lexical, structural, top words, charts)
- ✅ Epoch 3 — artist view (catalogue aggregation, sortable table)
- ⏳ Epoch 4 — rhyme, sentiment, readability, language mix
- ⏳ Epoch 5 — comparison page + deploy

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). You may read, modify, and use this code for any **non-commercial** purpose. Commercial use is not permitted.
