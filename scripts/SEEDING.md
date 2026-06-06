# Seeding LyricStats with full lyrics

The deployed app (on Vercel) **can't scrape genius.com** — Cloudflare blocks
datacenter IPs. So on Vercel it lists catalogues via the Genius API and pulls
lyric *text* from lrclib/lyrics.ovh (plain text, no `[Chorus]`/`[Verse]` tags).

To get **full lyrics with section tags** — especially for regional/Balkan
artists that lrclib/ovh don't cover — run a small script from a **residential
IP** (your MacBook or iPhone). It scrapes Genius and pushes each song to the
deployed app's `/api/ingest` endpoint, which writes to the shared database.
Once seeded, `lyricstats.vercel.app` serves it instantly from cache.

## What you need (set once)

| Value | Where to get it |
|---|---|
| `LYRICSTATS_API_BASE` | `https://lyricstats-api.vercel.app` |
| `GENIUS_TOKEN` | https://genius.com/api-clients (same one the app uses) |
| `SEED_KEY` | the secret set on the Vercel API project (env var `SEED_KEY`) |

---

## MacBook

```bash
cd "Personal Projects/LyricStats/scripts"
pip3 install requests lyricsgenius      # one time

export LYRICSTATS_API_BASE="https://lyricstats-api.vercel.app"
export GENIUS_TOKEN="your-genius-token"
export SEED_KEY="your-seed-key"

# one or more artists
python3 seed.py "Jala Brat" "Buba Corelli" --songs 30

# the whole curated Balkan list
python3 seed_balkan.py --songs 30
python3 seed_balkan.py --list            # preview the list, seed nothing
python3 seed_balkan.py --only "Senidah"  # just one
```

---

## iPhone (a-Shell)

1. Install **a-Shell** from the App Store (free).
2. Open it and install the two dependencies:
   ```
   pip install requests lyricsgenius
   ```
3. Get the two script files onto the phone. Easiest: in a-Shell,
   ```
   curl -O https://raw.githubusercontent.com/DavidCvetkovski/LyricStats/main/scripts/seed.py
   curl -O https://raw.githubusercontent.com/DavidCvetkovski/LyricStats/main/scripts/seed_balkan.py
   ```
   (or AirDrop them into the a-Shell documents folder).
4. Set the env vars for this session and run:
   ```
   export LYRICSTATS_API_BASE="https://lyricstats-api.vercel.app"
   export GENIUS_TOKEN="your-genius-token"
   export SEED_KEY="your-seed-key"
   python seed.py "Jala Brat" --songs 20
   ```

> Tip: on cellular your phone has a residential/mobile IP, which is exactly why
> Genius lets it scrape. Keep a-Shell in the foreground while it runs — iOS
> suspends backgrounded apps.

---

## Notes

- **Re-running is safe.** Songs upsert by (artist, title); re-seeding an artist
  refreshes their lyrics (and upgrades any plain lrclib/ovh text the live app
  cached into full Genius lyrics with section tags).
- **Coverage:** anything Genius can't scrape (instrumentals, missing pages) is
  skipped — the script just moves on.
- **Only two dependencies** (`requests`, `lyricsgenius`) so it runs anywhere,
  including a-Shell. No database driver needed; the writes go through the app.
