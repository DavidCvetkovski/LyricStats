"""Where one song stands among every song in the archive.

`data/song_quantiles.json` is built offline by scripts/build_song_quantiles.py
from the per-song table of the LRCLIB import: for each metric, the values at
the 0th…100th percentile. A song's percentile is then a bisect, no database.
"""

from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from functools import lru_cache
from pathlib import Path

QUANTILES_PATH = Path(__file__).with_name("data") / "song_quantiles.json"


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        with open(QUANTILES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"metrics": {}, "archive_songs": 0}


def archive_songs() -> int:
    """How many distinct songs the quantiles speak for."""
    return int(_table().get("archive_songs") or 0)


def percentile(metric: str, value: float | int | None) -> int | None:
    """Share of archive songs with a value below this one, 0–100.

    Ties are split down the middle, so a value sitting on a plateau (most
    songs have zero title drops) reads as the middle of that plateau rather
    than its top.
    """
    if value is None:
        return None
    cuts = _table().get("metrics", {}).get(metric)
    if not cuts:
        return None
    lo = bisect_left(cuts, value)
    hi = bisect_right(cuts, value)
    pct = (lo + hi) / 2 / (len(cuts) - 1) * 100
    return int(round(max(0.0, min(100.0, pct))))


def percentiles(reading: dict) -> dict[str, int]:
    """Percentiles for every metric of a reading the table knows."""
    out: dict[str, int] = {}
    for metric in _table().get("metrics", {}):
        p = percentile(metric, reading.get(metric))
        if p is not None:
            out[metric] = p
    return out
