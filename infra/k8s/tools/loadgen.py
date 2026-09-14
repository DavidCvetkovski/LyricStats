"""Steady, user-shaped traffic for LyricStats.

A cluster nobody uses has no request rate, and rate-based alerts on it mean
nothing. This sends a mix of typeahead searches, artist page loads and the odd
typo (a 404, which is not an error) through the Ingress, the way a browser
would, and prints one summary line every 30 seconds. During an incident that
summary is the users' view of the outage.

Standard library only, so it runs in the API image.
"""

from __future__ import annotations

import json
import os
import random
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

TARGET = os.environ.get("TARGET", "http://traefik.kube-system.svc.cluster.local")
HOST = os.environ.get("HOST_HEADER", "lyricstats.localhost")
RPS = float(os.environ.get("RPS", "4"))
TIMEOUT = float(os.environ.get("TIMEOUT_SECONDS", "5"))
SUMMARY_EVERY = 30.0

PREFIXES = ["ta", "the", "be", "dr", "ma", "jo", "li", "ra", "so", "ke", "ar", "el", "da", "mi"]
SEED_ARTISTS = ["Taylor Swift", "The Weeknd", "Jala Brat", "Lata Mangeshkar"]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(path: str, params: dict[str, str]) -> tuple[str, bytes, float]:
    url = f"{TARGET}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Host": HOST, "User-Agent": "lyricstats-loadgen"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return str(response.status), response.read(), time.perf_counter() - start
    except urllib.error.HTTPError as error:
        return str(error.code), b"", time.perf_counter() - start
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return "conn_error", b"", time.perf_counter() - start


def main() -> None:
    artists = set(SEED_ARTISTS)
    statuses: Counter[str] = Counter()
    latencies: list[float] = []
    last_summary = time.monotonic()
    print(f"{now()} loadgen starting: target={TARGET} host={HOST} rps={RPS}", flush=True)

    while True:
        tick = time.perf_counter()
        roll = random.random()
        if roll < 0.5:
            status, body, took = get("/api/artist/suggest", {"q": random.choice(PREFIXES)})
            if status == "200" and len(artists) < 300:
                try:
                    artists.update(s["name"] for s in json.loads(body)["suggestions"])
                except (ValueError, KeyError, TypeError):
                    pass
        elif roll < 0.9:
            status, _, took = get("/api/artist", {"name": random.choice(sorted(artists))})
        else:
            typo = "".join(random.choices(string.ascii_lowercase, k=12))
            status, _, took = get("/api/artist", {"name": typo})

        statuses[status] += 1
        latencies.append(took)

        if time.monotonic() - last_summary >= SUMMARY_EVERY:
            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
            counts = " ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
            print(f"{now()} sent={sum(statuses.values())} {counts} p95_ms={p95 * 1000:.0f}", flush=True)
            statuses.clear()
            latencies.clear()
            last_summary = time.monotonic()

        time.sleep(max(0.0, 1.0 / RPS - (time.perf_counter() - tick)))


if __name__ == "__main__":
    main()
