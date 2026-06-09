# LyricStats — Project Plan

A web app that fetches lyrics for any song or artist (must support Jala Brat & Buba Corelli) and shows as many statistics about them as possible — per song and per artist, with comparisons.

---

## 1. Decisions

### 1.1 Stack
- **Backend / app:** Python — by far the strongest NLP ecosystem (`nltk`, `spaCy`, `textstat`, `pronouncing`, `langdetect`, `transformers`), and most of the work is text processing.
- **Web framework:** **Streamlit** for v1. It is the fastest path to a working "data app" — charts, tables, inputs in ~50 lines. We can graduate to **FastAPI + React (Vite)** later if we outgrow it.
- **Storage:** SQLite via `sqlmodel`. Caches fetched lyrics + computed stats so we never re-scrape.
- **Deploy:** Streamlit Community Cloud (free) for v1, Railway later.

### 1.2 Lyrics source
- **Primary: Genius**, via `lyricsgenius` (Python wrapper). It uses the official Genius API for search/metadata and scrapes the lyric block from the song page. It is free (requires a free Genius API token) and is the only realistic free source that reliably has Balkan artists like **Jala Brat** and **Buba Corelli**.
- **Fallback: `lyrics.ovh`** (no key, no rate-limit, but limited catalogue — used only if Genius misses).
- All fetched lyrics cached in SQLite indefinitely.

### 1.3 Non-goals (for now)
- No accounts / auth.
- No commercial redistribution of lyrics — stats and short excerpts only, lyrics shown collapsed behind a toggle with "via Genius" attribution.
- No mobile app.

---

## 2. Requirements

### 2.1 Functional
- Search a song by `artist + title`, see all stats for that song.
- Search an artist, see aggregated stats across their catalogue.
- Compare 2+ songs side-by-side.
- Compare 2+ artists side-by-side.
- Top-N lists (most-used words, longest words, rhyme-densest songs, etc.).
- Language detection — handle Bosnian/Serbian/Croatian + English mixed lyrics gracefully.
- Cache everything; second visit is instant.

### 2.2 Non-functional
- Cold fetch of an artist's full catalogue should be backgrounded with a progress bar.
- Respect Genius rate limits (sleep + retry on 429).
- All stats must render in < 1s once cached.

### 2.3 Stats catalogue (target)

**Lexical**
- Total words, total lines, total characters
- Unique words, type-token ratio (vocabulary richness)
- Hapax legomena count (words used exactly once)
- Top-N words (with and without stopword filtering)
- Word-length distribution, average word length
- Longest words

**Structural**
- Line count, average words per line
- Verse / chorus detection (via repetition + Genius section tags `[Chorus]`, `[Verse 1]`, etc.)
- Chorus repetition ratio (how much of the song is chorus)
- Section count

**Phonetic / rhyme**
- Syllables per line, per word (CMU dict for EN; heuristic vowel-cluster counter for BHS)
- End-rhyme scheme (AABB / ABAB / free) — detected by phonetic suffix matching
- Internal-rhyme density
- Alliteration count

**Readability**
- Flesch reading ease, Flesch–Kincaid grade (EN)
- Avg syllables/word, avg words/sentence
- For BHS: avg word length + lexical density as a proxy

**Sentiment / themes**
- Polarity (positive/negative) — VADER for EN; for BHS use a multilingual model (`xlm-roberta` via HuggingFace) on a per-line basis
- Emotion distribution (joy/anger/sadness/etc.) — small transformer pipeline
- Top noun-phrase themes (spaCy)
- Profanity rate (configurable wordlist, BHS + EN)

**Language**
- Detected language(s) per line, mix ratio (e.g. "72% BHS, 28% EN")

**Artist-level aggregates (per artist)**
- All of the above, averaged + summed across catalogue
- Vocabulary growth over time (unique words per release year)
- Most-repeated words across whole catalogue
- Longest / shortest song, highest / lowest vocabulary richness
- Sentiment trajectory across discography

**Comparisons**
- Two-column diff for any stat
- Shared vs unique vocabulary between two artists (Venn-style)
- Stat radar chart

---

## 3. Architecture (one-screen)

```
┌────────────────────────────────────────────────────────┐
│                    Streamlit UI                        │
│  pages/  Home · Song · Artist · Compare · About        │
└──────────────────────┬─────────────────────────────────┘
                       │
              ┌────────▼─────────┐
              │   service layer   │   pure-python, no UI
              │ ─ fetch.py        │   Genius + ovh, retries
              │ ─ stats.py        │   all metrics
              │ ─ rhyme.py        │   phonetic analysis
              │ ─ sentiment.py    │   VADER + xlm-roberta
              │ ─ language.py     │   langdetect
              └────────┬──────────┘
                       │
              ┌────────▼─────────┐
              │  SQLite (cache)  │
              │  artists, songs, │
              │  lyrics, stats   │
              └──────────────────┘
```

---

## 4. Roadmap

Split into **epochs** (shippable milestones). Each epoch leaves the app in a working state.

### Epoch 1 — Foundations (weekend 1)
Goal: project boots, can fetch one song's lyrics end-to-end.

- **1.1 Repo & env**
  - `pyproject.toml` with `uv` or `poetry`
  - `.gitignore`, `.env.example` (for `GENIUS_TOKEN`)
  - `make run`, `make test`, `make fmt` targets
- **1.2 Streamlit skeleton**
  - Single page: input "artist" + "song", button "Fetch"
  - Show raw lyrics text
- **1.3 Lyrics fetcher**
  - `lyricsgenius` wrapper module with retry + 429 backoff
  - LyricsOVH fallback
  - Smoke test: fetch one Jala Brat track end-to-end
- **1.4 SQLite cache**
  - Tables: `artist`, `song`, `lyrics_blob`, `fetched_at`
  - Hit cache before calling network

### Epoch 2 — Core stats (weekend 2)
Goal: song page shows real numbers.

- **2.1 Tokenization & cleanup**
  - Strip `[Chorus]` / `[Verse]` tags into a structure list, keep clean text
  - Unicode-safe lowercasing (handles š, č, ž, etc.)
- **2.2 Lexical stats** — word count, unique words, TTR, top-N, word-length hist
- **2.3 Structural stats** — lines, sections, chorus ratio
- **2.4 Song page UI**
  - Header (artist, title, album, year)
  - Metric cards (word count, unique, TTR, lines)
  - Top-words bar chart, word-length histogram
  - Collapsible lyrics with section tags rendered

### Epoch 3 — Artist view (weekend 3)
Goal: type an artist, see their whole catalogue analyzed.

- **3.1 Catalogue fetcher** — `genius.search_artist(name, max_songs=...)` with progress bar
- **3.2 Background job pattern** — Streamlit `st.status` + cache key per artist
- **3.3 Aggregation layer** — `aggregate_stats(songs) -> ArtistStats`
- **3.4 Artist page UI**
  - Catalogue table sortable by any stat
  - Aggregate metric cards
  - Top words across catalogue
  - Longest / shortest / richest song highlights
- **3.5 Validate on Jala Brat & Buba Corelli** — confirm catalogue coverage; document any missing tracks

### Epoch 4 — Advanced stats (weekend 4)
Goal: depth beyond word-counting.

- **4.1 Language detection** — `langdetect` per line; show mix ratio chip on every song
- **4.2 Phonetics & rhyme**
  - EN: CMU dict via `pronouncing`
  - BHS: vowel-cluster syllable heuristic, end-suffix rhyme matcher
  - End-rhyme scheme display (AABB highlighted in the lyrics view)
  - Internal-rhyme + alliteration counters
- **4.3 Readability** — `textstat` for EN; custom proxy for BHS
- **4.4 Sentiment**
  - EN: VADER (fast, no model download)
  - BHS / mixed: `cardiffnlp/twitter-xlm-roberta-base-sentiment` via `transformers`
  - Per-line + overall song polarity, sentiment timeline chart
- **4.5 Themes** — spaCy noun-phrase extraction (`en_core_web_sm` + Stanza for BHS)
- **4.6 Profanity rate** — curated wordlist, configurable

### Epoch 5 — Comparison & polish (weekend 5)
Goal: the "fun" page where you put Jala vs Buba head-to-head.

- **5.1 Compare page**
  - Pick 2–4 entities (songs or artists, mixable)
  - Side-by-side stat table
  - Radar chart for normalized stats
  - Shared-vs-unique vocabulary visualization
- **5.2 Discography trends**
  - Stats per release year line chart
  - Vocabulary-growth curve
- **5.3 Performance pass**
  - Pre-compute stats on fetch, store JSON in `stats` table
  - Memoize derived views
- **5.4 Polish**
  - Empty states, error toasts, attribution footer
  - Theming, app icon, README screenshots
- **5.5 Deploy** — push to Streamlit Community Cloud, custom-ish URL

### Epoch 6 — Stretch (anytime later)
Ideas, not commitments.
- LLM-generated artist "personality" summary from aggregated stats
- Lyric search across whole cache ("find every song with the word X")
- Playlist analysis (paste a Spotify playlist URL → pull tracklist → analyze)
- Export song stats as PDF / share card
- Public API + small React frontend if Streamlit feels limiting

---

## 5. Risk register
- **Genius scraping breaks** → keep `lyricsgenius` pinned; LyricsOVH fallback; cache so old data survives.
- **BHS NLP is weaker than EN** → start with language-agnostic stats (counts, rhyme suffixes); use multilingual models where possible; document EN-only features clearly in the UI.
- **Streamlit gets clunky at scale** → service layer is already UI-free, so swapping to FastAPI + React is a port, not a rewrite.
- **Legal / ToS** → never expose bulk lyric downloads; display only behind toggle with attribution; no public API for raw text.

---

## 6. Definition of done (v1)

- Can type "Jala Brat" → get full catalogue with aggregate stats in under a minute on a cold cache, instantly on a warm one.
- Can open any song and see ≥ 20 distinct stats.
- Can compare Jala Brat vs Buba Corelli on one page.
- Deployed at a public URL.
- README has screenshots and a 30-second demo gif.
