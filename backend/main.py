"""FastAPI backend — thin wrapper around the lyricstats package.

Serves JSON for the Next.js frontend to consume.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from lyricstats import db, fetch, stats

log = logging.getLogger("lyricstats.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LyricStats API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": "0.1.0"}


# ── single song ────────────────────────────────────────────────────────────


@app.get("/api/song")
def song(
    artist: str = Query(..., min_length=1),
    title: str = Query(..., min_length=1),
    force: bool = Query(False),
) -> dict[str, Any]:
    try:
        s = fetch.fetch_song(artist, title, force=force)
    except fetch.FetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("song fetch failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Persist computed stats to cache
    db_song = db.find_song(s.artist, s.title)
    cached = db.load_stats(db_song) if db_song else None
    if cached:
        st = stats.SongStats(**cached)
    else:
        st = stats.compute(s.lyrics)
        if db_song:
            db.save_stats(db_song, st.to_dict())

    return {
        "artist": s.artist,
        "title": s.title,
        "album": s.album,
        "year": s.year,
        "source": s.source,
        "lyrics": s.lyrics,
        "stats": st.to_dict(),
    }


# ── artist ─────────────────────────────────────────────────────────────────


@app.get("/api/artist")
def artist(
    name: str = Query(..., min_length=1),
    fetch_now: bool = Query(False, alias="fetch"),
    max: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    if fetch_now:
        try:
            fetch.fetch_artist_catalogue(name, max_songs=max)
        except fetch.FetchError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001
            log.exception("artist catalogue fetch failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

    a = db.get_artist(name)
    if not a:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No cached data for '{name}'. Enable 'fetch fresh from Genius' to pull it."
            ),
        )

    songs = db.list_songs(a)
    if not songs:
        raise HTTPException(status_code=404, detail=f"No songs for '{name}'.")

    pairs: list[tuple[str, str]] = []
    metas: list[dict[str, Any]] = []
    for s in songs:
        cached = db.load_stats(s)
        if cached:
            st = stats.SongStats(**cached)
        else:
            st = stats.compute(s.lyrics)
            db.save_stats(s, st.to_dict())
        pairs.append((s.title, s.lyrics))
        metas.append(
            {
                "title": s.title,
                "album": s.album,
                "year": s.year,
                "word_count": st.word_count,
                "unique_words": st.unique_words,
                "type_token_ratio": st.type_token_ratio,
                "chorus_ratio": st.chorus_ratio,
                "repetition_ratio": st.repetition_ratio,
                "line_count": st.line_count,
            }
        )

    agg = stats.aggregate(pairs)
    return {
        "name": a.name,
        "songs": metas,
        "stats": agg.to_dict(),
    }
