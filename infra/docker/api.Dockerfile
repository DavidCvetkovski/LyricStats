# syntax=docker/dockerfile:1.7
#
# LyricStats API image for the Kubernetes setup in infra/.
#
# The root Dockerfile bundles the API and the Next.js front end into one Fly
# machine. On Kubernetes they run as separate Deployments so each can scale,
# restart and fail on its own, so this image holds the API only.
#
# Build from the repository root:
#   docker build -f infra/docker/api.Dockerfile -t lyricstats-api:dev .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# requirements.txt is the slim runtime set (the same one Vercel installs);
# prometheus-client is the only addition, for the /metrics endpoint.
COPY requirements.txt ./
RUN pip install -r requirements.txt 'prometheus-client==0.22.1'

COPY backend ./backend
COPY lyricstats ./lyricstats
COPY infra/app/metrics.py infra/app/instrumented.py ./

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001

EXPOSE 8000
# One worker per pod: Kubernetes scales by adding replicas, and a single
# process keeps the Prometheus metrics in one registry per scrape target.
CMD ["uvicorn", "instrumented:app", "--host", "0.0.0.0", "--port", "8000"]
