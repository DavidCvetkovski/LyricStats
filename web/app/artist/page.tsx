"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { streamArtist, type ArtistProgress } from "@/lib/api";
import type { ArtistPayload } from "@/lib/types";
import { StatFigure } from "@/components/StatFigure";
import { WordTable } from "@/components/WordTable";
import { PullQuote } from "@/components/PullQuote";
import { ProgressLine } from "@/components/ProgressLine";
import { loadLastArtist, saveLastArtist } from "@/lib/lastSearch";

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
  const urlMin = Math.max(1, Math.min(100, parseInt(params.get("min") ?? "20") || 20));
  const urlPreferCache = params.get("prefer_cache") !== "0"; // default true

  const [name, setName] = useState(urlName);
  const [minText, setMinText] = useState(String(urlMin));
  const min = clampMin(minText);
  const [preferCache, setPreferCache] = useState(urlPreferCache);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ArtistProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ArtistPayload | null>(null);

  const lastKey = useRef<string>("");

  const run = useCallback(async (n: string, m: number, pc: boolean) => {
    if (!n) return;
    setLoading(true);
    setError(null);
    setProgress(null);
    try {
      const a = await streamArtist(n, m, pc, {
        onProgress: (p) => setProgress(p),
      });
      setData(a);
      setProgress(null);
      saveLastArtist({ name: n, min: m, preferCache: pc });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (urlName) {
      const key = `${urlName}|${urlMin}|${urlPreferCache}`;
      if (key === lastKey.current) return;
      lastKey.current = key;
      setName(urlName);
      setMinText(String(urlMin));
      setPreferCache(urlPreferCache);
      run(urlName, urlMin, urlPreferCache);
      return;
    }
    if (lastKey.current) return;
    const last = loadLastArtist();
    if (last) {
      const pc = last.preferCache ?? true;
      lastKey.current = `${last.name}|${last.min}|${pc}`;
      setName(last.name);
      setMinText(String(last.min));
      setPreferCache(pc);
      const q = new URLSearchParams({
        name: last.name,
        min: String(last.min),
        prefer_cache: pc ? "1" : "0",
      }).toString();
      router.replace(`/artist?${q}`);
      run(last.name, last.min, pc);
    }
  }, [urlName, urlMin, urlPreferCache, run, router]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    const q = new URLSearchParams({
      name,
      min: String(min),
      prefer_cache: preferCache ? "1" : "0",
    }).toString();
    router.push(`/artist?${q}`);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 pt-10 pb-20">
      <header className="border-b border-rule-strong pb-8">
        <p className="smallcaps mb-2">Section III — The Artist</p>
        <h2 className="display text-5xl sm:text-6xl text-ink">A career, in figures.</h2>
        <p className="mt-3 font-serif italic text-xl text-ink-soft max-w-2xl">
          Pull a catalogue from the wires. Read it as a single body of work.
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="mt-10 grid gap-8 sm:grid-cols-[2fr_1fr_auto] items-end"
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
          <span className="smallcaps mb-1 block">Songs at least</span>
          <input
            className="field no-spin"
            type="number"
            inputMode="numeric"
            min={1}
            max={100}
            value={minText}
            onChange={(e) => setMinText(e.target.value)}
            onBlur={() => setMinText(String(clampMin(minText)))}
          />
        </label>
        <button type="submit" className="pill" disabled={loading}>
          {loading ? "Filing…" : "Examine →"}
        </button>

        {/* Editorial source toggle — small caps + a thin underline state */}
        <div className="sm:col-span-3 flex items-center gap-3 pt-1">
          <button
            type="button"
            role="switch"
            aria-checked={preferCache}
            onClick={() => setPreferCache((v) => !v)}
            className="group inline-flex items-center gap-2 text-[0.72rem] uppercase tracking-[0.18em] text-ink hover:text-accent transition-colors"
          >
            <span
              className={`inline-block w-3.5 h-3.5 border border-ink-soft transition-all ${
                preferCache ? "bg-ink" : "bg-paper"
              }`}
              aria-hidden
            />
            Prefer the archive
          </button>
          <span className="text-[0.72rem] italic font-serif text-ink-mute">
            — use what we already have on file
          </span>
        </div>
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
          Reading what is on file…
        </p>
      )}

      {error && (
        <p className="mt-10 font-serif italic text-accent text-lg border-l-2 border-accent pl-4">
          {error}
        </p>
      )}

      {data && !loading && <ArtistView data={data} />}
    </div>
  );
}

function ArtistView({ data }: { data: ArtistPayload }) {
  const s = data.stats;
  const topSongs = [...data.songs].sort((a, b) => b.word_count - a.word_count);

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

      <section className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4 my-12">
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
        <StatFigure
          label="Avg. chorus share"
          value={`${Math.round(s.avg_chorus_ratio * 100)}%`}
          size="lg"
        />
        <StatFigure
          label="Avg. repetition"
          value={`${Math.round(s.avg_repetition_ratio * 100)}%`}
          size="lg"
        />
      </section>

      <section className="grid gap-12 lg:grid-cols-[1fr_1.1fr] mt-12">
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

      <section className="mt-20">
        <h3 className="display text-3xl mb-6">The Catalogue</h3>
        <div className="border-t border-rule-strong">
          {topSongs.map((song, i) => (
            <div
              key={song.title}
              className="grid grid-cols-[2.5rem_1fr_auto_auto_auto] gap-4 items-baseline border-b border-rule py-3"
            >
              <span className="figure text-ink-mute tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="font-serif text-xl text-ink leading-tight">
                  {song.title}
                </p>
                {song.album && (
                  <p className="text-[0.78rem] italic text-ink-mute mt-0.5">
                    {song.album}
                    {song.year ? ` · ${song.year}` : ""}
                  </p>
                )}
              </div>
              <Mini label="words" value={song.word_count.toLocaleString()} />
              <Mini label="unique" value={song.unique_words.toLocaleString()} />
              <Mini
                label="variety"
                value={`${(song.type_token_ratio * 100).toFixed(0)}%`}
              />
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
  return (
    <div className="text-right min-w-[3.5rem]">
      <div className="figure text-base tabular-nums">{value}</div>
      <div className="smallcaps text-[0.65rem]">{label}</div>
    </div>
  );
}

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase());
}

/** Parse a possibly-empty text value into a 1..100 song count, defaulting to 20. */
function clampMin(text: string): number {
  const n = parseInt(text || "20", 10);
  if (Number.isNaN(n)) return 20;
  return Math.max(1, Math.min(100, n));
}
