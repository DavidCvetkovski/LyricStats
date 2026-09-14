# syntax=docker/dockerfile:1.7
#
# LyricStats Next.js front end for the Kubernetes setup in infra/.
#
# Build from the repository root:
#   docker build -f infra/docker/web.Dockerfile -t lyricstats-web:dev .

FROM node:20-bookworm-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /web

COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./

# NEXT_PUBLIC_API_BASE stays unset, so the browser calls /api on the same host
# and the Ingress routes those requests straight to the API Service.
# API_INTERNAL only feeds the Next.js /api rewrite, which is resolved at build
# time; pointing it at the in-cluster Service keeps that path working too.
ARG API_INTERNAL=http://lyricstats-api:8000
ENV API_INTERNAL=${API_INTERNAL}

# Standalone output copies only the files `next start` needs into
# .next/standalone, which keeps the runtime image small. It is patched into
# this build's copy of next.config.ts rather than the file itself so the Vercel
# deployment is unaffected; the grep fails the build loudly if the config
# changes shape and the patch no longer applies.
RUN grep -q 'const nextConfig: NextConfig = {' next.config.ts \
 && sed -i 's/const nextConfig: NextConfig = {/const nextConfig: NextConfig = {\n  output: "standalone",/' next.config.ts \
 && mkdir -p public \
 && npm run build

FROM node:20-bookworm-slim
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /web

COPY --from=build --chown=node:node /web/.next/standalone ./
COPY --from=build --chown=node:node /web/.next/static ./.next/static
COPY --from=build --chown=node:node /web/public ./public

USER node
EXPOSE 3000
CMD ["node", "server.js"]
