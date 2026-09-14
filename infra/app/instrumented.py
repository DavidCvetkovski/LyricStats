"""ASGI entrypoint for the Kubernetes image: the LyricStats API plus /metrics.

backend/main.py is left exactly as it is; the image runs `instrumented:app`
instead of `backend.main:app`. Moving these two lines into backend/main.py
would give the Vercel deployment the same metrics.
"""

from backend.main import app
from metrics import instrument

instrument(app)
