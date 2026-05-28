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

// ── streaming artist ──────────────────────────────────────────────────────

export type ArtistProgress = {
  done: number;
  total: number;
  current: string;
};

export type ArtistStreamHandlers = {
  onProgress?: (p: ArtistProgress) => void;
  signal?: AbortSignal;
};

/**
 * Streams the artist endpoint, calling onProgress for each progress event
 * and resolving with the final ArtistPayload when the result arrives.
 */
export async function streamArtist(
  name: string,
  min: number,
  preferCache: boolean,
  handlers: ArtistStreamHandlers = {},
): Promise<ArtistPayload> {
  const q = new URLSearchParams({
    name,
    min: String(min),
    prefer_cache: preferCache ? "1" : "0",
  });
  const res = await fetch(`${BASE}/api/artist?${q.toString()}`, {
    signal: handlers.signal,
    cache: "no-store",
  });
  if (!res.ok || !res.body) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let result: ArtistPayload | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let ev: {
        type: string;
        done?: number;
        total?: number;
        current?: string;
        message?: string;
        payload?: ArtistPayload;
      };
      try {
        ev = JSON.parse(line);
      } catch {
        continue;
      }
      if (ev.type === "progress") {
        handlers.onProgress?.({
          done: ev.done ?? 0,
          total: ev.total ?? 1,
          current: ev.current ?? "",
        });
      } else if (ev.type === "result" && ev.payload) {
        result = ev.payload;
      } else if (ev.type === "error") {
        throw new Error(ev.message || "Unknown server error");
      }
    }
  }

  if (!result) throw new Error("Stream ended without a result");
  return result;
}
