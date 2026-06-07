import type { ArtistPayload, SongPayload } from "./types";

export interface CacheStore<T> {
  get(key: string): T | null;
  set(key: string, value: T): void;
  getLast(): { key: string; data: T } | null;
  clear(): void;
}

class MemoryCacheStore<T> implements CacheStore<T> {
  private cache: { key: string; data: T } | null = null;

  get(key: string): T | null {
    if (this.cache && this.cache.key === key) {
      return this.cache.data;
    }
    return null;
  }

  set(key: string, value: T): void {
    this.cache = { key, data: value };
  }

  getLast(): { key: string; data: T } | null {
    return this.cache;
  }

  clear(): void {
    this.cache = null;
  }
}

export const artistCache = new MemoryCacheStore<ArtistPayload>();
export const songCache = new MemoryCacheStore<SongPayload>();
