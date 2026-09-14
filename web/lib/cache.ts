import type { ArtistPayload, SongPayload } from "./types";

export interface CacheStore<T> {
  get(key: string): T | null;
  set(key: string, value: T): void;
  getLast(): { key: string; data: T } | null;
  clear(): void;
}

/** Small, browser-memory LRU: repeat searches avoid another API invocation. */
export class MemoryCacheStore<T> implements CacheStore<T> {
  private cache = new Map<string, { data: T; expiresAt: number }>();

  constructor(
    private readonly capacity = 12,
    private readonly ttlMs = 30 * 60 * 1000,
  ) {
    if (!Number.isInteger(capacity) || capacity < 1 || ttlMs <= 0) {
      throw new Error("Cache capacity and lifetime must be positive.");
    }
  }

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    if (entry.expiresAt <= Date.now()) {
      this.cache.delete(key);
      return null;
    }
    // Map insertion order records the least-to-most recently used entries.
    this.cache.delete(key);
    this.cache.set(key, entry);
    return entry.data;
  }

  set(key: string, value: T): void {
    this.cache.delete(key);
    this.cache.set(key, { data: value, expiresAt: Date.now() + this.ttlMs });
    while (this.cache.size > this.capacity) {
      const oldest = this.cache.keys().next().value;
      if (oldest !== undefined) this.cache.delete(oldest);
    }
  }

  getLast(): { key: string; data: T } | null {
    const keys = Array.from(this.cache.keys()).reverse();
    for (const key of keys) {
      const data = this.get(key);
      if (data !== null) return { key, data };
    }
    return null;
  }

  clear(): void {
    this.cache.clear();
  }
}

export const artistCache = new MemoryCacheStore<ArtistPayload>();
export const songCache = new MemoryCacheStore<SongPayload>(24);
