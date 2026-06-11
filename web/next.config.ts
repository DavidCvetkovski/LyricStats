import type { NextConfig } from "next";

/**
 * In dev we proxy `/api/*` from the browser through Next to the local
 * FastAPI backend, so the frontend stays same-origin (no CORS): `uv run
 * uvicorn …` is on :8000 and `next dev` is on :3000.
 *
 * In production the browser calls the Python API directly via
 * NEXT_PUBLIC_API_BASE (a separate Vercel project), so this rewrite is a
 * dev convenience only. Override the target with API_INTERNAL if needed.
 */
const API_INTERNAL = process.env.API_INTERNAL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async redirects() {
    // Collapse www onto the apex domain so search engines index one host.
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.lyricstats.dev" }],
        destination: "https://lyricstats.dev/:path*",
        permanent: true,
      },
    ];
  },
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
