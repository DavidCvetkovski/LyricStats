"""FastAPI backend — thin wrapper around the lyricstats package.

Serves JSON for the Next.js frontend. The artist endpoint streams NDJSON
so the client can render fetch progress without polling.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, Generator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from lyricstats import db, fetch, stats

log = logging.getLogger("lyricstats.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="LyricStats API", version="0.2.0")
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
    return {"ok": True, "version": "0.2.0"}


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

    db_song = db.find_song(s.artist, s.title)
    cached = db.load_stats(db_song) if db_song else None
    # Migrate old caches that pre-date new fields (e.g. section_sequence)
    if cached and "section_sequence" in cached:
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


# ── artist (streaming) ─────────────────────────────────────────────────────


def _aggregate_payload(name: str) -> dict[str, Any]:
    a = db.get_artist(name)
    if not a:
        raise HTTPException(status_code=404, detail=f"No cached data for '{name}'.")
    songs = db.list_songs(a)
    if not songs:
        raise HTTPException(status_code=404, detail=f"No songs for '{name}'.")

    pairs: list[tuple[str, str]] = []
    metas: list[dict[str, Any]] = []
    for s in songs:
        cached = db.load_stats(s)
        if cached and "section_sequence" in cached:
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
    return {"name": a.name, "songs": metas, "stats": agg.to_dict()}


def _line(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


@app.get("/api/artist")
def artist(
    name: str = Query(..., min_length=1),
    max: int = Query(20, ge=1, le=100),
) -> StreamingResponse:
    """Stream NDJSON: zero or more `{type:"progress"}` events, then exactly
    one terminal `{type:"result"}` or `{type:"error"}`.
    """

    def gen() -> Generator[bytes, None, None]:
        existing = db.get_artist(name)
        has_cache = existing is not None and bool(db.list_songs(existing))

        if not has_cache:
            # Fetch with progress in a worker thread, drain a queue here.
            events: queue.Queue[dict[str, Any]] = queue.Queue()

            def on_progress(done: int, total: int, current: str) -> None:
                events.put(
                    {"type": "progress", "done": done, "total": total, "current": current}
                )

            def worker() -> None:
                try:
                    fetch.fetch_artist_catalogue(name, max_songs=max, progress=on_progress)
                    events.put({"type": "_done"})
                except fetch.FetchError as e:
                    events.put({"type": "error", "message": str(e)})
                except Exception as e:  # noqa: BLE001
                    log.exception("artist fetch worker failed")
                    events.put({"type": "error", "message": str(e)})

            t = threading.Thread(target=worker, daemon=True)
            t.start()

            yield _line({"type": "progress", "done": 0, "total": max, "current": "starting…"})

            while True:
                ev = events.get()
                if ev["type"] == "_done":
                    break
                if ev["type"] == "error":
                    yield _line(ev)
                    return
                yield _line(ev)

        # Aggregate and emit result
        try:
            payload = _aggregate_payload(name)
        except HTTPException as e:
            yield _line({"type": "error", "message": e.detail})
            return
        except Exception as e:  # noqa: BLE001
            log.exception("aggregate failed")
            yield _line({"type": "error", "message": str(e)})
            return

        yield _line({"type": "result", "payload": payload})

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
