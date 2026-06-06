"""Vercel serverless entrypoint for the LyricStats API.

Vercel's Python runtime serves the ASGI `app` object exported here. The
`vercel.json` rewrite sends every request to this function, and FastAPI routes
on the original path (`/api/song`, `/api/artist`, …).
"""

from backend.main import app  # noqa: F401
