"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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

export default function ArtistPage() {
  return (
    <Suspense fallback={null}>
      <ArtistPageInner />
    </Suspense>
  );
}

let cachedArtistData: {
  key: string;
  data: ArtistPayload;
} | null = null;

function ArtistPageInner() {
  const router = useRouter();
  const params = useSearchParams();

  const urlName = params.get("name") ?? "";
  const urlMin = Math.max(1, Math.min(500, parseInt(params.get("min") ?? "20") || 20));
  const urlShuffle = params.get("shuffle") ?? "";

  const [name, setName] = useState(urlName);
  const [minText, setMinText] = useState(String(urlMin));
  const min = clampMin(minText);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ArtistProgress | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [data, setData] = useState<ArtistPayload | null>(null);

  const lastKey = useRef<string>("");
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
    if (cachedArtistData && cachedArtistData.key === key) {
      setData(cachedArtistData.data);
      setLoading(false);
      setProgress(null);
      setError(null);
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
    try {
      // 1. Plan: resolve + sample on Genius. If the cache already holds
      //    enough, to_fetch comes back empty and we skip straight to stats.
      const pool = await getArtistPool(n, m, false, sh, signal);
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
      cachedArtistData = { key, data: a };
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
      setMinText(String(urlMin));
      run(urlName, urlMin, urlShuffle);
      return;
    }
    if (lastKey.current) return;
    const last = loadLastArtist();
    if (last) {
      lastKey.current = `${last.name}|${last.min}|`;
      setName(last.name);
      setMinText(String(last.min));
    }
  }, [urlName, urlMin, urlShuffle, run]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    setMinText(String(min));
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
        className="mt-8 sm:mt-10 grid gap-6 sm:gap-8 sm:grid-cols-[2fr_1fr_auto] items-end"
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
        <label className="block">
          <span className="smallcaps mb-1 block">Songs</span>
          <input
            className="field no-spin"
            type="number"
            inputMode="numeric"
            min={1}
            value={minText}
            onChange={(e) => setMinText(e.target.value)}
            onBlur={() => setMinText(String(clampMin(minText)))}
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

      {error && (
        <ErrorNote err={error} onRetry={() => run(name, min, "")} />
      )}

      {data && !loading && <ArtistView data={data} />}
    </div>
  );
}

function ArtistView({ data }: { data: ArtistPayload }) {
  const s = data.stats;
  const topSongs = [...data.songs].sort((a, b) => b.word_count - a.word_count);
  // Only show structure-derived figures when at least one sampled song has
  // real section tags ([Chorus] etc.) — plain lrclib/ovh lyrics don't carry them.
  const hasSections = data.songs.some((song) => song.has_sections);

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
            a random sample of {data.sampled} drawn from {data.cached_total} on file
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
              wrong artist? · view on Genius ↗
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

      <section className="mt-16 sm:mt-20">
        <h3
          className="display mb-5 sm:mb-6"
          style={{ fontSize: "clamp(1.75rem, 6vw, 2.5rem)" }}
        >
          The Catalogue
        </h3>
        <div className="border-t border-rule-strong">
          {topSongs.map((song, i) => (
            <div
              key={song.title}
              className="grid grid-cols-[2rem_1fr] sm:grid-cols-[2.5rem_1fr_auto_auto_auto] gap-x-3 sm:gap-x-4 gap-y-2 items-baseline border-b border-rule py-3"
            >
              <span className="figure text-ink-mute tabular-nums text-sm sm:text-base self-start mt-1">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <p className="font-serif text-lg sm:text-xl text-ink leading-tight break-words">
                  {song.title}
                </p>
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
          ))}
        </div>
      </section>
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

/** Parse a possibly-empty text value into a 1..500 song count, defaulting to 20. */
function clampMin(text: string): number {
  const n = parseInt(text || "20", 10);
  if (Number.isNaN(n)) return 20;
  return Math.max(1, Math.min(500, n));
}
