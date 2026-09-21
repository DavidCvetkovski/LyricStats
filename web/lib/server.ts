import type { SongPayload } from "./types";

/**
 * The API as seen from the server. In production NEXT_PUBLIC_API_BASE points
 * at the API project; in development it is unset and the browser goes through
 * Next's /api rewrite, which a server component cannot use, so we talk to the
 * FastAPI process directly (the same target the rewrite uses).
 */
export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE || process.env.API_INTERNAL || "http://127.0.0.1:8000";
}

/**
 * One song, by name or slug. Null when the song is unknown to every source.
 * The result is kept for an hour per artist and title, so a shared link
 * costs the API one read, not one per visitor.
 */
export async function fetchSong(artist: string, title: string): Promise<SongPayload | null> {
  const q = new URLSearchParams({ artist, title });
  const res = await fetch(`${apiBase()}/api/song?${q.toString()}`, {
    next: { revalidate: 3600 },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as SongPayload;
}
