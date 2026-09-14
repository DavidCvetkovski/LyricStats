"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getSong } from "@/lib/api";
import type { SongPayload } from "@/lib/types";
import { loadLastSong, saveLastSong } from "@/lib/lastSearch";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { ErrorNote } from "@/components/ErrorNote";
import { artistCache, songCache } from "@/lib/cache";
import { catalogueSong, songSearchKey } from "@/lib/songExperience";
import { SongStory } from "@/components/SongStory";
import { localSong, wordsIn } from "@/lib/reading";
import Link from "next/link";
import { ArtistAutocomplete } from "@/components/ArtistAutocomplete";

export default function SongPage() {
  return (
    <Suspense fallback={null}>
      <SongPageInner />
    </Suspense>
  );
}

function SongPageInner() {
  const params = useSearchParams();

  const urlArtist = params.get("artist") ?? "";
  const urlTitle = params.get("title") ?? "";

  const urlMode = params.get("mode");
  const [inputMode, setInputMode] = useState<"search" | "text">(urlMode === "text" ? "text" : "search");
  const [draft, setDraft] = useState("");
  const cached = songCache.getLast();
  const initial = urlMode === "text" ? null : urlArtist && urlTitle
    ? songCache.get(songSearchKey(urlArtist, urlTitle))
    : (!urlArtist && !urlTitle ? cached?.data ?? null : null);
  const [artist, setArtist] = useState(() => urlArtist || initial?.artist || "");
  const [title, setTitle] = useState(() => urlTitle || initial?.title || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [song, setSong] = useState<SongPayload | null>(initial);
  const [expanding, setExpanding] = useState(false);
  const lastKey = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const requestRef = useRef(0);
  const pendingRef = useRef<string | null>(null);
  const retryRef = useRef<{ artist: string; title: string; full: boolean } | null>(null);

  const run = useCallback(async (a: string, t: string, full = false) => {
    a = a.trim();
    t = t.trim();
    if (!a || !t) return;
    const key = songSearchKey(a, t);
    const pendingKey = `${key}:${full}`;
    if (pendingRef.current === pendingKey && !abortRef.current?.signal.aborted) return;
    lastKey.current = key;
    abortRef.current?.abort();
    pendingRef.current = null;
    retryRef.current = null;
    const request = ++requestRef.current;
    setError(null);
    setExpanding(full);
    saveLastSong({ artist: a, title: t });
    if (!full) {
      const cachedSong = songCache.get(key);
      const stored = cachedSong ?? catalogueSong(artistCache.getLast()?.data, a, t);
      if (stored) {
        if (!cachedSong) songCache.set(key, stored);
        setSong(stored);
        setLoading(false);
        return;
      }
      setSong(null);
    }
    const controller = new AbortController();
    abortRef.current = controller;
    pendingRef.current = pendingKey;
    setLoading(true);
    try {
      const result = await getSong(a, t, { full, signal: controller.signal });
      if (controller.signal.aborted || request !== requestRef.current) return;
      setSong(result);
      songCache.set(key, result);
      if (full && result.analysis_complete === false) {
        retryRef.current = { artist: a, title: t, full };
        setError({ headline: "The full text is not available yet.", detail: "You can still explore the stored figures and find this track on Spotify." });
      }
    } catch (err) {
      if (controller.signal.aborted || request !== requestRef.current) return;
      retryRef.current = { artist: a, title: t, full };
      setError(friendlyError(err));
    } finally {
      if (!controller.signal.aborted && request === requestRef.current) {
        setLoading(false);
        setExpanding(false);
        pendingRef.current = null;
      }
    }
  }, []);

  const catalogue = artistCache.getLast()?.data;
  const titles = catalogue?.name.trim().toLowerCase() === artist.trim().toLowerCase() ? catalogue.songs : [];

  // Keep URL navigation, form submission and browser history on one search path.
  useEffect(() => {
    if (urlMode === "text") { setInputMode("text"); return; }
    setInputMode("search");
    if (urlArtist && urlTitle) {
      const key = songSearchKey(urlArtist, urlTitle);
      if (key === lastKey.current) return;
      setArtist(urlArtist);
      setTitle(urlTitle);
      void run(urlArtist, urlTitle);
    } else if (!urlArtist && !urlTitle) {
      abortRef.current?.abort();
      ++requestRef.current;
      lastKey.current = "";
      setLoading(false);
      setExpanding(false);
      setError(null);
      const recent = songCache.getLast()?.data;
      const last = recent ?? loadLastSong();
      setSong(recent ?? null);
      if (last) { setArtist(last.artist); setTitle(last.title); }
    } else {
      abortRef.current?.abort();
      ++requestRef.current;
      lastKey.current = "";
      setArtist(urlArtist);
      setTitle(urlTitle);
      setSong(null);
      setError(null);
      setLoading(false);
      setExpanding(false);
    }
  }, [urlArtist, urlTitle, urlMode, run]);

  useEffect(() => () => {
    abortRef.current?.abort();
    ++requestRef.current;
    lastKey.current = "";
  }, []);

  function switchMode(mode: "search" | "text") {
    abortRef.current?.abort(); ++requestRef.current; pendingRef.current = null; retryRef.current = null;
    lastKey.current = ""; setLoading(false); setExpanding(false); setError(null); setSong(null); setInputMode(mode);
    window.history.replaceState(null, "", mode === "text" ? "/song?mode=text" : "/song");
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputMode === "text") {
      if (!wordsIn(draft).length) return;
      abortRef.current?.abort(); ++requestRef.current; pendingRef.current = null;
      setLoading(false); setExpanding(false); setError(null);
      window.history.replaceState(null, "", "/song?mode=text");
      setSong(localSong(artist, title, draft));
      return;
    }
    const a = artist.trim(), t = title.trim();
    if (!a || !t) return;
    setArtist(a);
    setTitle(t);
    const query = new URLSearchParams({ artist: a, title: t });
    if (urlArtist !== a || urlTitle !== t) {
      window.history.pushState(null, "", `/song?${query}`);
    }
    void run(a, t);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      <header className="border-b border-rule-strong pb-6 sm:pb-8">
        <p className="smallcaps mb-2">Section II — On a Song</p>
        <h2
          className="display text-ink"
          style={{ fontSize: "clamp(2.25rem, 8vw, 4rem)" }}
        >
          Every song has a shape.
        </h2>
        <p className="font-serif italic text-xl text-ink-soft mt-5 max-w-2xl">See where it turns, what it repeats, and the words it saves for later.</p>
      </header>
      <div className="reading-switch mt-7" aria-label="Analysis input">
        <button aria-pressed={inputMode === "search"} onClick={() => switchMode("search")}>Find a song</button>
        <button aria-pressed={inputMode === "text"} onClick={() => switchMode("text")}>Use your own text</button>
      </div>
      <form onSubmit={onSubmit} className="mt-8 sm:mt-10 grid gap-6 sm:gap-8 sm:grid-cols-2">
        <label className="block">
          <span className="smallcaps mb-1 block">The Artist</span>
          {inputMode === "text" ? <input className="field" value={artist} onChange={e => setArtist(e.target.value)} placeholder="Artist (optional)" maxLength={300}/> : <ArtistAutocomplete
            value={artist}
            onChange={setArtist}
            placeholder="Justin Bieber"
            autoFocus
          />}
        </label>
        <label className="block">
          <span className="smallcaps mb-1 block">The Song</span>
          <input
            className="field"
            type="text"
            placeholder="Beauty and a Beat"
            required={inputMode === "search"}
            list={inputMode === "search" ? "catalogue-titles" : undefined}
            maxLength={300}
            autoComplete="off"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <datalist id="catalogue-titles">{titles.map(track => <option key={track.title} value={track.title}/>)}</datalist>
        {inputMode === "text" && <label className="sm:col-span-2"><span className="smallcaps block mb-3">The text</span><textarea className="field min-h-48 font-serif text-lg" placeholder="Paste the lyrics or your own writing here…" maxLength={50000} value={draft} onChange={e => setDraft(e.target.value)} required/><span className="text-xs text-ink-mute block mt-3">Stays in your browser. No upload, no account, no saved copy. Up to 50,000 characters.</span></label>}
        <div className="sm:col-span-2 flex items-center flex-wrap gap-5">
          <button type="submit" className="pill" disabled={inputMode === "search" ? !artist.trim() || !title.trim() : !wordsIn(draft).length}>
            {loading ? "Opening…" : "Read the song →"}
          </button>
        </div>
      </form>

      {loading && (
        <p role="status" className="mt-10 font-serif italic text-ink-soft text-lg">
          {expanding ? "Looking for the full text…" : "Opening the song’s figures…"}
        </p>
      )}

      {error && <div><p className="mt-6 font-serif italic text-ink-soft">You can also <button className="reading-link cursor-pointer" onClick={() => switchMode("text")}>use your own text</button> to explore the song here.</p><ErrorNote err={error} onRetry={() => {
        const failed = retryRef.current;
        if (failed) void run(failed.artist, failed.title, failed.full);
      }} /></div>}

      {!song && !loading && !error && inputMode === "search" && (
        <div className="mt-12 border-t border-rule pt-6 max-w-2xl">
          <p className="font-serif italic text-lg text-ink-soft">
            Every song has its own fingerprint. Start with an artist and a title,
            or open a track from an artist’s catalogue.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[["Justin Bieber", "Beauty and a Beat"], ["Billie Eilish", "BIRDS OF A FEATHER"], ["Kendrick Lamar", "Not Like Us"]].map(([a,t]) => <Link key={t} prefetch={false} href={`/song?${new URLSearchParams({artist:a,title:t})}`} className="border-t border-rule-strong pt-4 hover:text-accent"><span className="smallcaps block mb-2">{a}</span><span className="font-serif italic text-xl">{t} →</span></Link>)}
          </div>
        </div>
      )}
      {song && (!loading || expanding) && <SongStory key={`${song.artist}:${song.title}:${song.source}`} song={song} expanding={expanding}
        onExpand={() => run(song.artist, song.title, true)} />}
    </div>
  );
}
