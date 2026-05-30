# syntax=docker/dockerfile:1.7

# ─── Stage 1: install Python deps with uv into a venv ──────────────────────
FROM python:3.12-slim AS py-deps
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir 'uv>=0.5,<1.0'
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# ─── Stage 2: build Next.js (full deps) ─────────────────────────────────────
FROM node:20-bookworm-slim AS web-build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund --include=dev
COPY web/ ./
RUN npm run build
# Drop devDeps from node_modules so we ship a smaller image.
RUN npm prune --omit=dev

# ─── Stage 3: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    PATH="/app/.venv/bin:$PATH" \
    LYRICSTATS_DB=/data/lyricstats.db \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Install Node.js (for `next start`) + tini (init) using the bullseye archive
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg tini \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get purge -y curl gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python venv + source
COPY --from=py-deps /app/.venv /app/.venv
COPY backend ./backend
COPY lyricstats ./lyricstats

# Web: built output + pruned production deps + manifest/config
COPY --from=web-build /app/web/.next ./web/.next
COPY --from=web-build /app/web/public ./web/public
COPY --from=web-build /app/web/node_modules ./web/node_modules
COPY web/package.json web/package-lock.json web/next.config.ts ./web/

# Entrypoint
COPY scripts/entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

EXPOSE 3000
ENTRYPOINT ["/usr/bin/tini", "--", "./entrypoint.sh"]
