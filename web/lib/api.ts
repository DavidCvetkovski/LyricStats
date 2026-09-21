import type { ArtistPayload, SongPayload } from "./types";
import { MemoryCacheStore } from "./cache";
import { artistKey } from "./utils";

// In production NEXT_PUBLIC_API_BASE points at the Vercel Python API project
// (e.g. https://api.lyricstats.dev), so the browser calls it directly
// (CORS is allowed for *.vercel.app). Empty → relative paths, which works for
// local dev where the FastAPI process is proxied via Next's /api/* rewrite.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  // Let API response headers govern browser/CDN reuse. Explicit refreshes
  // below opt out, while ordinary reading can reuse a recent response.
  const res = await fetch(`${BASE}${path}`, { cache: "default", ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return (await res.json()) as T;
}

/** One song by name or slug. Song pages fetch on the server (lib/server.ts);
 * this is for anything that needs a reading in the browser. */
export function getSong(
  artist: string,
  title: string,
  opts?: { force?: boolean; signal?: AbortSignal },
): Promise<SongPayload> {
  const q = new URLSearchParams({ artist, title });
  if (opts?.force) q.set("force", "1");
  return get<SongPayload>(`/api/song?${q.toString()}`, {
    signal: opts?.signal,
    ...(opts?.force ? { cache: "no-store" } : {}),
  });
}

/** Every title we can open for an artist, for the song search box. */
export function getArtistTitles(
  name: string,
  signal?: AbortSignal,
): Promise<{ name: string; titles: string[] }> {
  const q = new URLSearchParams({ name });
  return get(`/api/artist/titles?${q.toString()}`, { signal });
}

// ── artist typeahead ───────────────────────────────────────────────────────

export type ArtistSuggestion = { name: string; song_count: number };

// Shared by the artist and song fields, with a fixed memory budget and refresh
// window so catalogue updates become visible during long browsing sessions.
const suggestionCache = new MemoryCacheStore<ArtistSuggestion[]>(100, 5 * 60 * 1000);

export function getCachedArtistSuggestions(q: string, limit = 8): ArtistSuggestion[] | null {
  const key = artistKey(q);
  if (key.length < 2) return [];
  const exact = suggestionCache.get(`${limit}:${key}`);
  if (exact) return exact;

  // Only a complete prefix result can safely answer a narrower query. A list
  // capped at `limit` may omit the very artist the longer query is looking for.
  for (let i = key.length - 1; i >= 2; i--) {
    const prefix = suggestionCache.get(`${limit}:${key.slice(0, i)}`);
    if (prefix && prefix.length < limit) {
      return prefix
        .filter((item) => artistKey(item.name).includes(key))
        .sort((a, b) => {
          const aStarts = Number(artistKey(a.name).startsWith(key));
          const bStarts = Number(artistKey(b.name).startsWith(key));
          return bStarts - aStarts || b.song_count - a.song_count;
        });
    }
  }
  return null;
}

/** Dataset autocomplete; repeated and safely narrowed queries stay local. */
export function suggestArtists(
  q: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<ArtistSuggestion[]> {
  if (signal?.aborted) {
    return Promise.reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
  }
  const cached = getCachedArtistSuggestions(q, limit);
  if (cached) return Promise.resolve(cached);
  const query = new URLSearchParams({ q, limit: String(limit) });
  return get<{ suggestions: ArtistSuggestion[] }>(
    `/api/artist/suggest?${query.toString()}`,
    { signal },
  ).then((r) => {
    if (!signal?.aborted) suggestionCache.set(`${limit}:${artistKey(q)}`, r.suggestions);
    return r.suggestions;
  });
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
  // Set when the typed name didn't match but a close dataset artist exists.
  suggestion?: string;
};

/** Plan a fetch: which songs (if any) the client must fetch one-by-one. */
export function getArtistPool(
  name: string,
  min: number,
  fresh: boolean,
  shuffle: string,
  signal?: AbortSignal,
): Promise<ArtistPool> {
  const q = new URLSearchParams({ name, min: String(min) });
  if (fresh) q.set("fresh", "1");
  if (shuffle) q.set("shuffle", shuffle);
  return get<ArtistPool>(`/api/artist/pool?${q.toString()}`, {
    signal,
    ...(fresh ? { cache: "no-store" } : {}),
  });
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
  signal?: AbortSignal,
): Promise<ArtistPayload> {
  const q = new URLSearchParams({ name, min: String(min) });
  if (shuffle) q.set("shuffle", shuffle);
  return get<ArtistPayload>(`/api/artist?${q.toString()}`, { signal });
}
