import type { ArtistPayload, SongPayload } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE || process.env.API_BASE || "http://localhost:8000";

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

export function getArtist(
  name: string,
  opts?: { fetch?: boolean; max?: number },
): Promise<ArtistPayload> {
  const q = new URLSearchParams({ name });
  if (opts?.fetch) q.set("fetch", "1");
  if (opts?.max) q.set("max", String(opts.max));
  return get<ArtistPayload>(`/api/artist?${q.toString()}`);
}
