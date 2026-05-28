"""Cover the lyricsgenius log-scraping progress hook.

If lyricsgenius ever changes its 'Song N: "Title"' log format, these
tests catch it without a network round-trip.
"""

import logging

from lyricstats.fetch import _lyricsgenius_progress


def _emit(message: str) -> None:
    logging.getLogger("lyricsgenius.genius").info(message)


def test_progress_handler_picks_up_lyricsgenius_logs():
    events: list[tuple[int, int, str]] = []
    with _lyricsgenius_progress(lambda d, t, c: events.append((d, t, c)), total=20):
        _emit('Song 1: "All Too Well (10 Minute Version)"')
        _emit('Song 2: "Wood"')
        _emit("some unrelated log message")
        _emit('Song 3: "Fortnight"')

    assert events == [
        (1, 20, "All Too Well (10 Minute Version)"),
        (2, 20, "Wood"),
        (3, 20, "Fortnight"),
    ]


def test_progress_caps_at_total_for_buffer_fetches():
    """We ask Genius for more than min_songs (buffer for skips), so we
    must not let 'Song 25' push the bar past 20/20."""
    events: list[tuple[int, int, str]] = []
    with _lyricsgenius_progress(lambda d, t, c: events.append((d, t, c)), total=20):
        _emit('Song 18: "X"')
        _emit('Song 19: "Y"')
        _emit('Song 25: "Buffer track"')  # past the cap

    assert events[-1] == (20, 20, "Buffer track")


def test_progress_handler_detaches_after_context():
    received = []
    with _lyricsgenius_progress(lambda d, t, c: received.append(c), total=5):
        _emit('Song 1: "Inside context"')
    _emit('Song 2: "Outside context"')
    assert received == ["Inside context"]


def test_no_handler_when_callback_is_none():
    # Should be a no-op context manager; no exceptions, nothing attached.
    with _lyricsgenius_progress(None, total=10):
        _emit('Song 1: "Whatever"')
