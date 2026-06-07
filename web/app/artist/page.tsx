"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  getArtistPool,
  fetchSongById,
  getArtistStats,
  type ArtistProgress,
} from "@/lib/api";
import type { ArtistPayload } from "@/lib/types";
import { StatFigure } from "@/components/StatFigure";
import { WordTable } from "@/components/WordTable";
import { PullQuote } from "@/components/PullQuote";
import { ProgressLine } from "@/components/ProgressLine";
import { loadLastArtist, saveLastArtist } from "@/lib/lastSearch";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { ErrorNote } from "@/components/ErrorNote";
import { artistCache } from "@/lib/cache";

export default function ArtistPage() {
  return (
    <Suspense fallback={null}>
      <ArtistPageInner />
    </Suspense>
  );
}

function ArtistPageInner() {
  const router = useRouter();
  const params = useSearchParams();

  const urlName = params.get("name") ?? "";
  const urlMin = Math.max(1, Math.min(500, parseInt(params.get("min") ?? "500") || 500));
  const urlShuffle = params.get("shuffle") ?? "";

  const cached = artistCache.getLast();

  const [name, setName] = useState(() => {
    if (urlName) return urlName;
    if (cached) return cached.data.name;
    return "";
  });
  // Songs-count input removed — we always aggregate the whole catalogue.
  const min = 500;
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ArtistProgress | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [data, setData] = useState<ArtistPayload | null>(() => {
    if (cached) {
      const [cacheName, cacheMin, cacheShuffle] = cached.key.split("|");
      if (!urlName || (urlName === cacheName && String(urlMin) === cacheMin && urlShuffle === cacheShuffle)) {
        return cached.data;
      }
    }
    return null;
  });

  const lastKey = useRef<string>(cached ? cached.key : "");
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setProgress(null);
  }, []);

  const run = useCallback(async (n: string, m: number, sh: string) => {
    if (!n) return;
    const key = `${n}|${m}|${sh}`;
    const cachedData = artistCache.get(key);
    if (cachedData) {
      setData(cachedData);
      setLoading(false);
      setProgress(null);
      setError(null);
      setSuggestion(null);
      return;
    }
    // Abort any in-flight run so a new search never gets stuck behind it.
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    const { signal } = ac;

    setLoading(true);
    setError(null);
    setProgress(null);
    setData(null);
    setSuggestion(null);
    try {
      // 1. Plan: resolve + sample on Genius. If the cache already holds
      //    enough, to_fetch comes back empty and we skip straight to stats.
      const pool = await getArtistPool(n, m, false, sh, signal);
      // Typo with no exact match but a close dataset artist → offer it and stop.
      if (pool.suggestion) {
        if (signal.aborted) return;
        setSuggestion(pool.suggestion);
        return;
      }
      const total = pool.to_fetch.length;
      // 2. Fetch each sampled song in turn, advancing the progress bar.
      //    Sequential by design — keeps us within Genius rate limits.
      for (let i = 0; i < total; i++) {
        if (signal.aborted) return;
        const ref = pool.to_fetch[i];
        setProgress({ done: i, total, current: ref.title });
        await fetchSongById(pool.name, ref, signal);
      }
      if (total > 0) setProgress({ done: total, total, current: "done" });
      // 3. Aggregate from the now-populated cache.
      const a = await getArtistStats(pool.name, m, sh, signal);
      if (signal.aborted) return;
      setData(a);
      artistCache.set(key, a);
      setProgress(null);
      saveLastArtist({ name: n, min: m, preferCache: true });
    } catch (err) {
      // A cancel surfaces as an AbortError — that's expected, not a failure.
      if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) {
        return;
      }
      setError(friendlyError(err));
      setData(null);
    } finally {
      if (abortRef.current === ac) {
        abortRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (urlName) {
      const key = `${urlName}|${urlMin}|${urlShuffle}`;
      if (key === lastKey.current) return;
      lastKey.current = key;
      setName(urlName);
      run(urlName, urlMin, urlShuffle);
      return;
    }
    if (lastKey.current) return;
    const last = loadLastArtist();
    if (last) {
      lastKey.current = `${last.name}|${last.min}|`;
      setName(last.name);
    }
  }, [urlName, urlMin, urlShuffle, run]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    // Fresh shuffle token on every Examine click → new random sample.
    const shuffle = Math.random().toString(36).slice(2, 10);
    // Mark this key as handled so the URL change below doesn't double-run,
    // then kick the search off directly (don't depend on param reactivity).
    lastKey.current = `${name}|${min}|${shuffle}`;
    const q = new URLSearchParams({
      name,
      min: String(min),
      shuffle,
    }).toString();
    router.push(`/artist?${q}`);
    run(name, min, shuffle);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      <header className="border-b border-rule-strong pb-6 sm:pb-8">
        <p className="smallcaps mb-2">Section III — The Artist</p>
        <h2
          className="display text-ink"
          style={{ fontSize: "clamp(2.25rem, 8vw, 4rem)" }}
        >
          A career, in figures.
        </h2>
        <p className="mt-3 font-serif italic text-lg sm:text-xl text-ink-soft max-w-2xl">
          Pull a catalogue from the wires. Read it as a single body of work.
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="mt-8 sm:mt-10 grid gap-6 sm:gap-8 sm:grid-cols-[1fr_auto] items-end"
      >
        <label className="block">
          <span className="smallcaps mb-1 block">The Artist</span>
          <input
            className="field"
            type="text"
            placeholder="Buba Corelli"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </label>
        <button type="submit" className="pill" disabled={loading}>
          {loading ? "Filing…" : "Examine →"}
        </button>
      </form>

      {loading && progress && (
        <ProgressLine
          done={progress.done}
          total={progress.total}
          current={progress.current}
          label="Filing"
        />
      )}

      {loading && !progress && (
        <p className="mt-10 font-serif italic text-ink-soft text-lg max-w-2xl mx-auto text-center">
          Loading…
        </p>
      )}

      {loading && (
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={cancel}
            className="text-[0.72rem] uppercase tracking-[0.18em] text-ink-mute hover:text-accent transition-colors underline decoration-rule-strong underline-offset-4 hover:decoration-accent"
          >
            Cancel
          </button>
        </div>
      )}

      {suggestion && !loading && !data && (
        <p className="mt-10 font-serif text-lg sm:text-xl text-ink-soft text-center">
          No exact match. Did you mean{" "}
          <button
            type="button"
            onClick={() => {
              setName(suggestion);
              setSuggestion(null);
              const shuffle = Math.random().toString(36).slice(2, 10);
              lastKey.current = `${suggestion}|${min}|${shuffle}`;
              router.push(
                `/artist?${new URLSearchParams({ name: suggestion, min: String(min), shuffle }).toString()}`,
              );
              run(suggestion, min, shuffle);
            }}
            className="italic text-accent underline decoration-rule-strong underline-offset-4 hover:decoration-accent"
          >
            {suggestion}
          </button>
          ?
        </p>
      )}

      {error && (
        <ErrorNote err={error} onRetry={() => run(name, min, "")} />
      )}

      {data && !loading && <ArtistView data={data} />}
    </div>
  );
}

function ArtistView({ data }: { data: ArtistPayload }) {
  const s = data.stats;

  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<"title" | "words" | "unique" | "variety">("words");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const handleSort = (field: "title" | "words" | "unique" | "variety") => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder(field === "title" ? "asc" : "desc");
    }
  };

  const topSongs = [...data.songs]
    .filter((song) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      const titleMatch = song.title.toLowerCase().includes(q);
      const albumMatch = song.album ? song.album.toLowerCase().includes(q) : false;
      return titleMatch || albumMatch;
    })
    .sort((a, b) => {
      let valA: any = "";
      let valB: any = "";
      if (sortField === "title") {
        valA = a.title.toLowerCase();
        valB = b.title.toLowerCase();
      } else if (sortField === "words") {
        valA = a.word_count;
        valB = b.word_count;
      } else if (sortField === "unique") {
        valA = a.unique_words;
        valB = b.unique_words;
      } else if (sortField === "variety") {
        valA = a.type_token_ratio;
        valB = b.type_token_ratio;
      }

      if (valA < valB) return sortOrder === "asc" ? -1 : 1;
      if (valA > valB) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });

  // Only show structure-derived figures when there's real section data.
  // Dataset artists carry it at the payload level (no per-song list to infer
  // from); lyrics-backed artists infer it from the sampled songs.
  const hasSections = data.has_sections ?? data.songs.some((song) => song.has_sections);
  // Dataset aggregates have no per-song catalogue to show.
  const hasCatalogue = data.songs.length > 0;

  return (
    <article className="mt-16 rise">
      <header className="text-center border-b border-rule-strong pb-12">
        <p className="smallcaps mb-3">A Reader</p>
        <h1
          className="display text-ink"
          style={{ fontSize: "clamp(3rem, 10vw, 8rem)" }}
        >
          {titleCase(data.name)}
        </h1>
        <p className="mt-5 font-serif italic text-xl text-ink-soft">
          {s.song_count} songs · {s.total_words.toLocaleString()} words ·{" "}
          {s.total_unique_words.toLocaleString()} distinct
        </p>
        {data.cached_total > data.sampled && (
          <p className="mt-2 text-[0.78rem] italic text-ink-mute">
            a random sample of {data.sampled} drawn from a catalogue of {data.cached_total}
          </p>
        )}
        {data.genius_url && (
          <p className="mt-3 text-[0.78rem] smallcaps">
            <a
              href={data.genius_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-accent transition-colors underline decoration-rule-strong underline-offset-4 hover:decoration-accent"
            >
              wrong artist? · view on Genius{" "}
              <svg
                className="inline-block w-2.5 h-2.5 ml-0.5 align-baseline"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M3.5 2.5h6v6M9.5 2.5l-7 7" />
              </svg>
            </a>
          </p>
        )}
      </header>

      {s.top_words_no_stop[0] && (
        <PullQuote cite={`${s.top_words_no_stop[0][1]} times, across ${s.song_count} songs`}>
          {s.top_words_no_stop[0][0]}
        </PullQuote>
      )}

      <section className="grid gap-6 sm:gap-10 grid-cols-2 lg:grid-cols-4 my-10 sm:my-12">
        <StatFigure
          label="Avg. words / song"
          value={s.avg_words_per_song.toFixed(0)}
          size="lg"
        />
        <StatFigure
          label="Avg. word variety"
          value={`${(s.avg_ttr * 100).toFixed(1)}%`}
          size="lg"
        />
        {hasSections && (
          <StatFigure
            label="Avg. chorus share"
            value={`${Math.round(s.avg_chorus_ratio * 100)}%`}
            size="lg"
          />
        )}
        <StatFigure
          label="Avg. repetition"
          value={`${Math.round(s.avg_repetition_ratio * 100)}%`}
          size="lg"
        />
      </section>

      <section className="grid gap-10 sm:gap-12 lg:grid-cols-[1fr_1.1fr] mt-10 sm:mt-12">
        <div className="space-y-8">
          {s.longest_song?.title && (
            <Highlight
              label="Longest song"
              title={s.longest_song.title}
              detail={`${s.longest_song.words} words`}
            />
          )}
          {s.richest_song?.title && (
            <Highlight
              label="Widest vocabulary"
              title={s.richest_song.title}
              detail={`${((s.richest_song.ttr ?? 0) * 100).toFixed(1)}% variety`}
            />
          )}
          {s.shortest_song?.title && (
            <Highlight
              label="Shortest song"
              title={s.shortest_song.title}
              detail={`${s.shortest_song.words} words`}
            />
          )}
        </div>

        <WordTable title="Most-used Words" rows={s.top_words_no_stop} max={20} />
      </section>

      {hasCatalogue && (
      <section className="mt-16 sm:mt-20">
        <div className="flex flex-col md:flex-row md:items-baseline justify-between gap-6 mb-6">
          <h3
            className="display"
            style={{ fontSize: "clamp(1.75rem, 6vw, 2.5rem)" }}
          >
            The Catalogue
          </h3>
          
          <div className="flex gap-4 items-center w-full sm:w-auto">
            {/* Search Box */}
            <input
              type="text"
              placeholder="Search title or album..."
              className="field text-sm py-1.5 px-1 max-w-xs flex-1 sm:flex-initial"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            
            {/* Mobile-only Sort Dropdown */}
            <div className="sm:hidden">
              <select
                value={`${sortField}-${sortOrder}`}
                onChange={(e) => {
                  const [field, order] = e.target.value.split("-") as [any, any];
                  setSortField(field);
                  setSortOrder(order);
                }}
                className="cursor-pointer bg-transparent border-0 border-b border-rule-strong py-1.5 px-1 text-xs smallcaps text-ink font-serif italic outline-none focus:border-accent"
              >
                <option value="words-desc" className="bg-paper text-ink">Words (high to low)</option>
                <option value="words-asc" className="bg-paper text-ink">Words (low to high)</option>
                <option value="unique-desc" className="bg-paper text-ink">Unique (high to low)</option>
                <option value="unique-asc" className="bg-paper text-ink">Unique (low to high)</option>
                <option value="variety-desc" className="bg-paper text-ink">Variety (high to low)</option>
                <option value="variety-asc" className="bg-paper text-ink">Variety (low to high)</option>
                <option value="title-asc" className="bg-paper text-ink">Title (A-Z)</option>
                <option value="title-desc" className="bg-paper text-ink">Title (Z-A)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="border-t border-rule-strong">
          {/* Desktop Table Header */}
          <div className="hidden sm:grid sm:grid-cols-[2.5rem_1fr_auto_auto_auto] gap-x-4 items-baseline border-b border-rule-strong pb-2 pt-4 text-xs smallcaps text-ink-mute mb-2">
            <span className="figure text-left select-none">#</span>
            <button
              type="button"
              onClick={() => handleSort("title")}
              className={`text-left cursor-pointer hover:text-ink transition-colors ${
                sortField === "title" ? "text-accent font-semibold" : ""
              }`}
            >
              Title{" "}
              <span className={sortField === "title" ? "opacity-100" : "opacity-0 select-none"}>
                {sortField === "title" && sortOrder === "desc" ? "↓" : "↑"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleSort("words")}
              className={`text-right cursor-pointer hover:text-ink transition-colors min-w-[3.5rem] ${
                sortField === "words" ? "text-accent font-semibold" : ""
              }`}
            >
              Words{" "}
              <span className={sortField === "words" ? "opacity-100" : "opacity-0 select-none"}>
                {sortField === "words" && sortOrder === "asc" ? "↑" : "↓"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleSort("unique")}
              className={`text-right cursor-pointer hover:text-ink transition-colors min-w-[3.5rem] ${
                sortField === "unique" ? "text-accent font-semibold" : ""
              }`}
            >
              Unique{" "}
              <span className={sortField === "unique" ? "opacity-100" : "opacity-0 select-none"}>
                {sortField === "unique" && sortOrder === "asc" ? "↑" : "↓"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleSort("variety")}
              className={`text-right cursor-pointer hover:text-ink transition-colors min-w-[3.5rem] ${
                sortField === "variety" ? "text-accent font-semibold" : ""
              }`}
            >
              Variety{" "}
              <span className={sortField === "variety" ? "opacity-100" : "opacity-0 select-none"}>
                {sortField === "variety" && sortOrder === "asc" ? "↑" : "↓"}
              </span>
            </button>
          </div>

          {topSongs.length === 0 ? (
            <p className="font-serif italic text-ink-soft text-lg py-8 text-center">
              No matching songs in catalogue.
            </p>
          ) : (
            topSongs.map((song, i) => (
            <div
              key={song.title}
              className="grid grid-cols-[2rem_1fr] sm:grid-cols-[2.5rem_1fr_auto_auto_auto] gap-x-3 sm:gap-x-4 gap-y-2 items-baseline border-b border-rule py-3"
            >
              <span className="figure text-ink-mute tabular-nums text-sm sm:text-base self-start mt-1">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <Link
                  href={`/song?artist=${encodeURIComponent(data.name)}&title=${encodeURIComponent(song.title)}`}
                  className="font-serif text-lg sm:text-xl text-ink hover:text-accent transition-colors leading-tight break-words hover:underline decoration-rule underline-offset-4 hover:decoration-accent"
                >
                  {song.title}
                </Link>
                {song.album && (
                  <p className="text-[0.72rem] sm:text-[0.78rem] italic text-ink-mute mt-0.5 break-words">
                    {song.album}
                    {song.year ? ` · ${song.year}` : ""}
                  </p>
                )}
              </div>
              {/* On mobile, the three minis sit below the title spanning both
                  columns; on desktop they slide into their own grid columns. */}
              <div className="col-start-2 sm:col-start-auto flex sm:contents gap-5 sm:gap-0 pt-1 sm:pt-0">
                <Mini label="words" value={song.word_count.toLocaleString()} />
                <Mini label="unique" value={song.unique_words.toLocaleString()} />
                <Mini
                  label="variety"
                  value={`${(song.type_token_ratio * 100).toFixed(0)}%`}
                />
              </div>
            </div>
          )))
        }
        </div>
      </section>
      )}
    </article>
  );
}

function Highlight({
  label,
  title,
  detail,
}: {
  label: string;
  title: string;
  detail: string;
}) {
  return (
    <div className="border-b border-rule pb-5">
      <p className="smallcaps mb-1">{label}</p>
      <p className="font-serif text-3xl text-ink leading-tight">{title}</p>
      <p className="text-[0.85rem] italic text-ink-mute mt-1">{detail}</p>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  // On mobile (flex row), align left and let them sit side-by-side.
  // On desktop (contents → real grid columns), align right.
  return (
    <div className="text-left sm:text-right min-w-[3rem] sm:min-w-[3.5rem]">
      <div className="figure text-sm sm:text-base tabular-nums">{value}</div>
      <div className="smallcaps text-[0.62rem] sm:text-[0.65rem]">{label}</div>
    </div>
  );
}

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase());
}
