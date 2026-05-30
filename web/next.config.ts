import type { NextConfig } from "next";

/**
 * In production the FastAPI backend runs on 127.0.0.1:8000 inside the
 * same Fly machine as the Next server. We proxy `/api/*` from the
 * browser through Next to the backend so the frontend uses
 * same-origin (no CORS, no public surface for the API).
 *
 * In dev the same rewrite works: `uv run uvicorn …` is on :8000 and
 * `next dev` is on :3000.
 */
const API_INTERNAL = process.env.API_INTERNAL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
