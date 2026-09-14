"""A tiny Alertmanager webhook receiver that prints every notification.

It stands in for PagerDuty or Slack on the local cluster:
  kubectl -n lyricstats logs -f deploy/alert-sink
shows exactly what an on-call engineer would have been sent, and when, which
is the raw material for an incident timeline.

Standard library only, so it runs in the API image.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (http.server naming)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return

        for alert in payload.get("alerts", []):
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            status = alert.get("status", "?").upper()
            when = alert.get("startsAt") if status == "FIRING" else alert.get("endsAt")
            print(
                f"{now()} {status:<8} {labels.get('alertname', '?')}"
                f" severity={labels.get('severity', '-')}"
                f" {'started' if status == 'FIRING' else 'ended'}={when}"
                f" summary={annotations.get('summary', '')!r}",
                flush=True,
            )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args: object) -> None:
        """Keep stdout to one line per alert."""


if __name__ == "__main__":
    print(f"{now()} alert-sink listening on :8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
