"""Tests for the FastAPI endpoints (called directly, against an isolated DB).

Covers the artist-aggregate precedence, the `limited` flag, the dataset
catalogue payload, fuzzy suggestions, and the ingest auth guard.
"""

from __future__ import annotations

import json
import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend import main
from backend.main import IngestSong
from lyricstats import db


def _add_dataset(name: str, song_count: int, songs=None) -> None:
    stats = {
        "song_count": song_count,
        "total_words": song_count * 100,
        "total_unique_words": 500,
        "avg_words_per_song": 100.0,
        "avg_ttr": 0.4,
        "avg_chorus_ratio": 0.2,
        "avg_repetition_ratio": 0.2,
        "top_words": [],
        "top_words_no_stop": [],
        "longest_song": {},
        "shortest_song": {},
        "richest_song": {},
    }
    if songs is None:
        songs = [[f"Song {i}", 2020, 100, 50, 0.5, 0.5, 0.5, 1] for i in range(song_count)]
    agg = db.ArtistAggregate(
        name=name.strip().lower(),
        name_key=db.normalize_key(name),
        display_name=name,
        song_count=song_count,
        has_sections=True,
        stats_json=json.dumps(stats),
        songs_json=json.dumps(songs),
    )
    with db.session() as s:
        s.add(agg)
        s.commit()


def _add_lyrics_artist(name: str, n_songs: int, words: int = 30) -> None:
    a = db.get_or_create_artist(name)
    for i in range(n_songs):
        db.upsert_song(a, title=f"Live Song {i}", lyrics=("la na song word here " * (words // 5)))


# ── health ───────────────────────────────────────────────────────────────────


def test_health():
    assert main.health()["ok"] is True


@pytest.mark.parametrize("path", ["/api/song", "/api/artist/suggest", "/api/artist/titles"])
def test_public_reads_have_bounded_browser_and_edge_cache(path):
    request = Request(
        {"type": "http", "method": "GET", "path": path, "query_string": b"", "headers": []}
    )

    async def respond(request):
        return JSONResponse({"ok": True})

    response = asyncio.run(main.cache_public_reads(request, respond))
    assert response.headers["Cache-Control"] == "public, max-age=60"
    assert (
        response.headers["Vercel-CDN-Cache-Control"]
        == "public, max-age=300, stale-while-revalidate=600"
    )
    assert response.headers["Vary"] == "Origin"


@pytest.mark.parametrize(
    "query,status",
    [
        (b"force=true", 200),
        (b"force=1", 200),
        (b"", 404),
        (b"", 500),
    ],
)
def test_refreshes_and_errors_are_never_cached(query, status):
    request = Request(
        {"type": "http", "method": "GET", "path": "/api/song", "query_string": query, "headers": []}
    )

    async def respond(request):
        return JSONResponse({"ok": status == 200}, status_code=status)

    response = asyncio.run(main.cache_public_reads(request, respond))
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Vercel-CDN-Cache-Control"] == "no-store"


# ── one song, read ───────────────────────────────────────────────────────────


def _no_provider(*args, **kwargs):
    pytest.fail("A stored song must not call an external lyric provider")


def _provider(calls, lyrics="hello world\nhello world\nhello again", source="lrclib"):
    def available(artist, title, *, force):
        calls.append((artist, title, force))
        return main.fetch.FetchedSong(artist=artist, title=title, lyrics=lyrics, source=source)

    return available


def _unavailable(calls):
    def missing(artist, title, *, force):
        calls.append((artist, title, force))
        raise main.fetch.FetchError("No lyrics available")

    return missing


HALO = ["Halo", 2008, 300, 150, 0.5, 0.2, 0.1, 1]
CRAZY = ["Crazy in Love", 2003, 400, 120, 0.3, 0.4, 0.3, 1]


def test_song_serves_cached_text_without_provider(temp_db, monkeypatch):
    artist = db.get_or_create_artist("Drake")
    saved = db.upsert_song(artist, title="Halo", lyrics="[Verse]\nhello world", year=2021)
    main.fetch.save_song_stats(saved)
    monkeypatch.setattr(main.fetch, "fetch_song", _no_provider)
    monkeypatch.setattr(main.stats, "compute", _no_provider)
    out = main.song(artist="Drake", title="Halo")
    assert out["source"] == "cache"
    assert out["analysis_complete"] is True
    assert out["stats"]["word_count"] == 2
    assert out["reading"]["wc"] == 2
    assert out["reading"]["line_count"] == 1
    assert out["year"] == 2021
    assert out["catalogue"] is None
    assert out["slug"] == {"artist": "drake", "title": "halo"}


def test_song_rereads_an_old_cache_entry_but_keeps_its_clock(temp_db, monkeypatch):
    artist = db.get_or_create_artist("Drake")
    saved = db.upsert_song(artist, title="Halo", lyrics="Halo, halo\nHalo, halo\nHalo, halo\nNever let go")
    st = main.stats.compute(saved.lyrics).to_dict()
    # A reading stored before the marks existed: no drop_at, but a clock.
    st["reading"] = {"wc": 9, "uniq": 4, "ttr": 0.44, "rep": 0.5, "first": 12.5,
                     "curve": [1] * 10, "duration": 200.0, "wpm": 2.7}
    db.save_stats(saved, st)
    monkeypatch.setattr(main.fetch, "fetch_song", _no_provider)
    out = main.song(artist="Drake", title="Halo")
    r = out["reading"]
    assert r["drop_at"] == [0, 1, 2]
    assert r["top_line_n"] == 3
    assert (r["first"], r["duration"], r["wpm"]) == (12.5, 200.0, 2.7)
    remembered = db.load_stats(db.find_song_by_key(artist, "Halo"))["reading"]
    assert remembered["drop_at"] == [0, 1, 2] and remembered["first"] == 12.5


def test_song_resolves_slugs_through_the_catalogue(temp_db, monkeypatch):
    _add_dataset("Beyoncé", 2, [HALO, CRAZY])
    calls = []
    monkeypatch.setattr(main.fetch, "fetch_song", _provider(calls))
    out = main.song(artist="beyonce", title="halo")
    assert calls == [("Beyoncé", "Halo", False)]
    assert out["artist"] == "Beyoncé"
    assert out["title"] == "Halo"
    assert out["slug"] == {"artist": "beyonce", "title": "halo"}
    assert out["reading"]["wc"] == 6
    catalogue = out["catalogue"]
    assert catalogue["songs"] == 2
    assert catalogue["in_catalogue"] is True
    assert catalogue["words"]["rank"] == 3  # both catalogue songs are longer
    assert catalogue["words"]["points"] == [300, 400]
    assert catalogue["variety"]["median"] == 0.5


def test_song_falls_back_to_catalogue_figures_when_text_is_missing(temp_db, monkeypatch):
    _add_dataset("Beyoncé", 1, [HALO])
    calls = []
    monkeypatch.setattr(main.fetch, "fetch_song", _unavailable(calls))
    monkeypatch.setattr(db, "save_stats", _no_provider)
    out = main.song(artist="beyonce", title="  HALO  ")
    assert calls == [("Beyoncé", "Halo", False)]
    assert out["source"] == "dataset"
    assert out["analysis_complete"] is False
    assert out["lyrics"] == ""
    assert out["year"] == 2008
    assert out["has_sections"] is True
    assert out["stats"]["word_count"] == 300
    assert out["reading"] == {"wc": 300, "uniq": 150, "ttr": 0.5, "rep": 0.1}
    assert out["catalogue"]["words"]["rank"] == 1
    assert db.get_artist("Beyoncé") is None


def test_song_prefers_cached_text_under_the_catalogue_name(temp_db, monkeypatch):
    _add_dataset("Beyoncé", 1, [HALO])
    artist = db.get_or_create_artist("Beyoncé")
    db.upsert_song(artist, title="Halo", lyrics="hello world")
    monkeypatch.setattr(main.fetch, "fetch_song", _no_provider)
    out = main.song(artist="beyonce", title="Halo")
    assert out["source"] == "cache"
    assert out["artist"] == "Beyoncé"
    assert out["reading"]["wc"] == 2  # read on first sight, then remembered
    assert "reading" in db.load_stats(db.find_song("Beyoncé", "Halo"))


def test_song_force_asks_the_provider_again(temp_db, monkeypatch):
    artist = db.get_or_create_artist("Drake")
    db.upsert_song(artist, title="Halo", lyrics="old words")
    calls = []
    monkeypatch.setattr(main.fetch, "fetch_song", _provider(calls, lyrics="new words here"))
    out = main.song(artist="Drake", title="Halo", force=True)
    assert calls == [("Drake", "Halo", True)]
    assert out["reading"]["wc"] == 3


def test_song_does_not_confuse_original_with_remix(temp_db, monkeypatch):
    _add_dataset("Drake", 1, [["Halo (Remix)", 2020, 300, 150, 0.5, 0.2, 0.1, 1]])
    calls = []
    monkeypatch.setattr(main.fetch, "fetch_song", _unavailable(calls))
    with pytest.raises(HTTPException) as error:
        main.song(artist="Drake", title="Halo")
    assert calls == [("Drake", "Halo", False)]
    assert error.value.status_code == 404


def test_song_unslugs_names_outside_the_dataset(temp_db, monkeypatch):
    calls = []
    monkeypatch.setattr(main.fetch, "fetch_song", _provider(calls))
    out = main.song(artist="new-band", title="new-song")
    assert calls == [("new band", "new song", False)]
    assert out["analysis_complete"] is True
    assert out["source"] == "lrclib"
    assert out["catalogue"] is None
    assert out["percentiles"]["wc"] is not None


def test_song_finds_cached_text_by_slug_outside_the_dataset(temp_db, monkeypatch):
    artist = db.get_or_create_artist("Jay-Z")
    db.upsert_song(artist, title="Empire State of Mind", lyrics="concrete jungle")
    monkeypatch.setattr(main.fetch, "fetch_song", _no_provider)
    out = main.song(artist="jay-z", title="empire-state-of-mind")
    assert out["title"] == "Empire State of Mind"
    assert out["slug"] == {"artist": "jay-z", "title": "empire-state-of-mind"}


def test_song_whitespace_input_does_not_query_or_fetch(temp_db, monkeypatch):
    monkeypatch.setattr(db, "find_song", _no_provider)
    with pytest.raises(HTTPException) as error:
        main.song(artist="  ", title="Song")
    assert error.value.status_code == 422


def test_artist_titles_lists_the_catalogue(temp_db):
    _add_dataset("Beyoncé", 2, [HALO, CRAZY])
    assert main.artist_titles(name="beyonce") == {"name": "Beyoncé", "titles": ["Halo", "Crazy in Love"]}
    assert main.artist_titles(name="nobody") == {"name": "nobody", "titles": []}
    artist = db.get_or_create_artist("Jay-Z")
    db.upsert_song(artist, title="Empire State of Mind", lyrics="concrete jungle")
    db.upsert_song(artist, title="Lost One", lyrics="")
    assert main.artist_titles(name="jay-z") == {"name": "jay-z", "titles": ["Empire State of Mind"]}


def test_autocomplete_uses_one_compact_read_without_lyrics(temp_db):
    from sqlalchemy import event

    _add_dataset("Drake", 100)
    _add_lyrics_artist("Drake", 2)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(temp_db, "before_cursor_execute", capture)
    try:
        out = main.artist_suggest(q="dra", limit=8)
    finally:
        event.remove(temp_db, "before_cursor_execute", capture)
    assert out == {"suggestions": [{"name": "Drake", "song_count": 100}]}
    assert len(statements) == 1
    assert "songs_json" not in statements[0]
    assert "stats_json" not in statements[0]
    assert "lyrics" not in statements[0]


# ── dataset payload ──────────────────────────────────────────────────────────


def test_dataset_payload_expands_catalogue(temp_db):
    songs = [["Song A", 2020, 300, 150, 0.5, 0.2, 0.1, 1]]
    _add_dataset("Drake", 1, songs)
    p = main._dataset_payload(db.get_artist_aggregate("Drake"))
    assert p["source"] == "dataset"
    assert p["limited"] is False
    assert len(p["songs"]) == 1
    assert p["songs"][0]["title"] == "Song A"
    assert p["songs"][0]["word_count"] == 300
    assert p["songs"][0]["has_sections"] is True


# ── artist() precedence + limited flag ───────────────────────────────────────


def test_artist_prefers_richer_dataset_over_thin_cache(temp_db):
    _add_dataset("Drake", 100)
    _add_lyrics_artist("Drake", 1)  # a stray cached song must not shadow
    out = main.artist(name="Drake", min=500)
    assert out["source"] == "dataset"
    assert out["stats"]["song_count"] == 101


def test_artist_limited_when_under_floor(temp_db):
    _add_lyrics_artist("Tiny Artist", 3)
    out = main.artist(name="Tiny Artist", min=500)
    assert out["limited"] is True
    assert out["stats"]["song_count"] == 3


def test_artist_not_limited_when_enough(temp_db):
    _add_lyrics_artist("Big Artist", 25)
    out = main.artist(name="Big Artist", min=500)
    assert out["limited"] is False
    assert out["stats"]["song_count"] >= main.MIN_VIEW


def test_artist_404_when_unknown(temp_db):
    with pytest.raises(HTTPException) as e:
        main.artist(name="Nobody At All", min=500)
    assert e.value.status_code == 404


# ── pool planning ────────────────────────────────────────────────────────────


def test_pool_dataset_exact_skips_fetch(temp_db):
    _add_dataset("Drake", 100)
    res = main.artist_pool(name="Drake", min=500, fresh=False, shuffle="")
    assert res["to_fetch"] == []
    assert res["cached_total"] == 100


def test_pool_typo_offers_suggestion(temp_db):
    _add_dataset("Drake", 100)
    res = main.artist_pool(name="drakee", min=500, fresh=False, shuffle="")
    assert res.get("suggestion") == "Drake"
    assert res["to_fetch"] == []


def test_pool_exhausted_catalogue_serves_cache(temp_db):
    a = db.get_or_create_artist("Niche")
    with db.session() as s:
        row = s.get(db.Artist, a.id)
        row.total_songs = 6  # Genius has 6
        s.add(row)
        s.commit()
    db.upsert_song(a, title="Only One", lyrics="hello world")
    for i in range(5):
        db.upsert_song(a, title=f"Empty {i}", lyrics="")  # the rest had no lyrics
    res = main.artist_pool(name="Niche", min=500, fresh=False, shuffle="")
    assert res["to_fetch"] == []  # already exhausted Genius → no re-fetch


def test_pool_live_fetch_targets_min_view(temp_db, monkeypatch):
    fake_artist = db.get_or_create_artist("New Band")
    sample = [
        {"id": i, "title": f"T{i}", "url": None, "album": None, "year": None} for i in range(1, 6)
    ]
    called = {}

    def fake_resolve(name, n, **kw):
        called["n"] = n
        return fake_artist, sample

    monkeypatch.setattr(main.fetch, "resolve_and_sample", fake_resolve)
    res = main.artist_pool(name="New Band", min=500, fresh=False, shuffle="")
    assert called["n"] == 500  # targets the requested floor
    assert len(res["to_fetch"]) == 5


# ── ingest auth guard ────────────────────────────────────────────────────────


def test_ingest_rejects_bad_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", "secret")
    with pytest.raises(HTTPException) as e:
        main.ingest(IngestSong(artist="A", title="T", lyrics="x"), x_seed_key="wrong")
    assert e.value.status_code == 403


def test_ingest_disabled_without_seed_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", None)
    with pytest.raises(HTTPException) as e:
        main.ingest(IngestSong(artist="A", title="T", lyrics="x"), x_seed_key="")
    assert e.value.status_code == 503


def test_ingest_accepts_valid_key(temp_db, monkeypatch):
    monkeypatch.setattr(main, "SEED_KEY", "secret")
    out = main.ingest(IngestSong(artist="A", title="T", lyrics="hello world"), x_seed_key="secret")
    assert out["ok"] is True
    assert db.find_song("a", "T") is not None
