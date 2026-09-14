import { afterEach, describe, expect, it, vi } from "vitest";
import { artistCache, MemoryCacheStore } from "./cache";
import type { ArtistPayload } from "./types";

describe("MemoryCacheStore", () => {
  afterEach(() => vi.useRealTimers());

  it("should get null initially", () => {
    artistCache.clear();
    expect(artistCache.get("test-key")).toBeNull();
    expect(artistCache.getLast()).toBeNull();
  });

  it("should retrieve set value when key matches", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    expect(artistCache.get("test-key")).toBe(mockPayload);
    expect(artistCache.getLast()).toEqual({ key: "test-key", data: mockPayload });
  });

  it("should return null when key does not match", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    expect(artistCache.get("different-key")).toBeNull();
  });

  it("should clear cache", () => {
    artistCache.clear();
    const mockPayload = { name: "test artist", songs: [], stats: {} } as unknown as ArtistPayload;
    artistCache.set("test-key", mockPayload);
    artistCache.clear();
    expect(artistCache.get("test-key")).toBeNull();
    expect(artistCache.getLast()).toBeNull();
  });

  it("keeps multiple searches and evicts the least recently visited result", () => {
    const cache = new MemoryCacheStore<string>(2);
    cache.set("a", "Artist A");
    cache.set("b", "Artist B");
    expect(cache.get("a")).toBe("Artist A");
    expect(cache.getLast()).toEqual({ key: "a", data: "Artist A" });

    cache.set("c", "Artist C");
    expect(cache.get("b")).toBeNull();
    expect(cache.get("a")).toBe("Artist A");
    expect(cache.get("c")).toBe("Artist C");
  });

  it("refreshes an existing entry without evicting another result", () => {
    const cache = new MemoryCacheStore<string>(2);
    cache.set("a", "old");
    cache.set("b", "other");
    cache.set("a", "new");
    expect(cache.get("a")).toBe("new");
    expect(cache.get("b")).toBe("other");
  });

  it("expires results without extending their lifetime on repeat reads", () => {
    vi.useFakeTimers();
    const cache = new MemoryCacheStore<string>(2, 1000);
    cache.set("a", "Artist A");
    vi.advanceTimersByTime(600);
    expect(cache.get("a")).toBe("Artist A");
    vi.advanceTimersByTime(400);
    expect(cache.get("a")).toBeNull();
    expect(cache.getLast()).toBeNull();
  });

  it("restores the most recent unexpired search even if a later-read entry expired", () => {
    vi.useFakeTimers();
    const cache = new MemoryCacheStore<string>(2, 1000);
    cache.set("a", "Artist A");
    vi.advanceTimersByTime(600);
    cache.set("b", "Artist B");
    cache.get("a");
    vi.advanceTimersByTime(400);
    expect(cache.getLast()).toEqual({ key: "b", data: "Artist B" });
  });
});
