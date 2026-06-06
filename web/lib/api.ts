import type { ArtistPayload, SongPayload } from "./types";

// In production NEXT_PUBLIC_API_BASE points at the Vercel Python API project
// (e.g. https://lyricstats-api.vercel.app), so the browser calls it directly
// (CORS is allowed for *.vercel.app). Empty → relative paths, which works for
// local dev where the FastAPI process is proxied via Next's /api/* rewrite.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return (await res.json()) as T;
}

export function getSong(
  artist: string,
  title: string,
  opts?: { force?: boolean },
): Promise<SongPayload> {
  const q = new URLSearchParams({ artist, title });
  if (opts?.force) q.set("force", "1");
  return get<SongPayload>(`/api/song?${q.toString()}`);
}

// ── artist (client-orchestrated fetch) ─────────────────────────────────────
//
// A catalogue fetch is three steps the browser drives itself, so each request
// stays short enough for a serverless function:
//   1. getArtistPool — resolve + sample on Genius (fetches no lyrics)
//   2. fetchSongById — one call per sampled song, populates the cache
//   3. getArtistStats — aggregate from the now-populated cache

export type ArtistProgress = {
  done: number;
  total: number;
  current: string;
};

export type ArtistSongRef = { id: number; title: string };

export type ArtistPool = {
  name: string;
  genius_url: string | null;
  to_fetch: ArtistSongRef[];
  cached_total: number;
};

/** Plan a fetch: which songs (if any) the client must fetch one-by-one. */
export function getArtistPool(
  name: string,
  min: number,
  fresh: boolean,
  shuffle: string,
): Promise<ArtistPool> {
  const q = new URLSearchParams({ name, min: String(min) });
  if (fresh) q.set("fresh", "1");
  if (shuffle) q.set("shuffle", shuffle);
  return get<ArtistPool>(`/api/artist/pool?${q.toString()}`);
}

/** Fetch and cache one song's lyrics by Genius id. */
export function fetchSongById(
  name: string,
  ref: ArtistSongRef,
  signal?: AbortSignal,
): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({
    name,
    id: String(ref.id),
    title: ref.title,
  });
  return get<{ ok: boolean }>(`/api/song/by-id?${q.toString()}`, { signal });
}

/** Aggregate stats over a random sample of the artist's cached songs. */
export function getArtistStats(
  name: string,
  min: number,
  shuffle: string,
): Promise<ArtistPayload> {
  const q = new URLSearchParams({ name, min: String(min) });
  if (shuffle) q.set("shuffle", shuffle);
  return get<ArtistPayload>(`/api/artist?${q.toString()}`);
}
