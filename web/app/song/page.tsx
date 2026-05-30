"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSong } from "@/lib/api";
import type { SongPayload } from "@/lib/types";
import { StatFigure } from "@/components/StatFigure";
import { WordTable } from "@/components/WordTable";
import { PullQuote } from "@/components/PullQuote";
import { loadLastSong, saveLastSong } from "@/lib/lastSearch";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { ErrorNote } from "@/components/ErrorNote";

export default function SongPage() {
  return (
    <Suspense fallback={null}>
      <SongPageInner />
    </Suspense>
  );
}

function SongPageInner() {
  const router = useRouter();
  const params = useSearchParams();

  const urlArtist = params.get("artist") ?? "";
  const urlTitle = params.get("title") ?? "";

  const [artist, setArtist] = useState(urlArtist);
  const [title, setTitle] = useState(urlTitle);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [song, setSong] = useState<SongPayload | null>(null);

  const lastKey = useRef<string>("");

  const run = useCallback(async (a: string, t: string) => {
    if (!a || !t) return;
    setLoading(true);
    setError(null);
    try {
      const s = await getSong(a, t);
      setSong(s);
      saveLastSong({ artist: a, title: t });
    } catch (err) {
      setError(friendlyError(err));
      setSong(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load when URL has params; else restore from localStorage.
  useEffect(() => {
    if (urlArtist && urlTitle) {
      const key = `${urlArtist}|${urlTitle}`;
      if (key === lastKey.current) return;
      lastKey.current = key;
      setArtist(urlArtist);
      setTitle(urlTitle);
      run(urlArtist, urlTitle);
      return;
    }
    if (lastKey.current) return;
    const last = loadLastSong();
    if (last) {
      lastKey.current = `${last.artist}|${last.title}`;
      setArtist(last.artist);
      setTitle(last.title);
      const q = new URLSearchParams({ artist: last.artist, title: last.title }).toString();
      router.replace(`/song?${q}`);
      run(last.artist, last.title);
    }
  }, [urlArtist, urlTitle, run, router]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!artist || !title) return;
    const q = new URLSearchParams({ artist, title }).toString();
    router.push(`/song?${q}`);
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      <header className="border-b border-rule-strong pb-6 sm:pb-8">
        <p className="smallcaps mb-2">Section II — On a Song</p>
        <h2
          className="display text-ink"
          style={{ fontSize: "clamp(2.25rem, 8vw, 4rem)" }}
        >
          A single track, examined.
        </h2>
        <p className="mt-3 font-serif italic text-lg sm:text-xl text-ink-soft max-w-2xl">
          Name an artist and a song. We will retrieve the lyrics, count them, and
          set the result in&nbsp;type.
        </p>
      </header>

      <form onSubmit={onSubmit} className="mt-8 sm:mt-10 grid gap-6 sm:gap-8 sm:grid-cols-2">
        <label className="block">
          <span className="smallcaps mb-1 block">The Artist</span>
          <input
            className="field"
            type="text"
            placeholder="Jala Brat"
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
            autoFocus
          />
        </label>
        <label className="block">
          <span className="smallcaps mb-1 block">The Song</span>
          <input
            className="field"
            type="text"
            placeholder="Bombaclat"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <div className="sm:col-span-2">
          <button type="submit" className="pill" disabled={loading}>
            {loading ? "Setting type…" : "Examine →"}
          </button>
        </div>
      </form>

      {loading && (
        <p className="mt-10 font-serif italic text-ink-soft text-lg">
          Retrieving the lyrics. One moment…
        </p>
      )}

      {error && <ErrorNote err={error} onRetry={() => run(artist, title)} />}

      {song && !loading && <SongView song={song} />}
    </div>
  );
}

function SongView({ song }: { song: SongPayload }) {
  const s = song.stats;
  return (
    <article className="mt-16 rise">
      {/* Article header */}
      <header className="text-center border-b border-rule-strong pb-12">
        <h1
          className="display text-ink mx-auto"
          style={{ fontSize: "clamp(3rem, 9vw, 7rem)", maxWidth: "16ch" }}
        >
          {song.title}
        </h1>
        <p className="mt-5 font-serif italic text-2xl text-ink-soft">
          by{" "}
          <span className="not-italic">{titleCase(song.artist)}</span>
          {song.album ? (
            <>
              {" "}
              <span className="diamond" />
              <span>{song.album}</span>
            </>
          ) : null}
          {song.year ? <span className="text-ink-mute"> ({song.year})</span> : null}
        </p>
      </header>

      {s.top_words_no_stop[0] && (
        <PullQuote cite={`appears ${s.top_words_no_stop[0][1]} times`}>
          {s.top_words_no_stop[0][0]}
        </PullQuote>
      )}

      <section className="grid gap-6 sm:gap-10 grid-cols-2 lg:grid-cols-4 my-10 sm:my-12">
        <StatFigure
          label="Total Words"
          value={s.word_count.toLocaleString()}
          caption={`across ${s.line_count} lines`}
          size="lg"
        />
        <StatFigure
          label="Unique Words"
          value={s.unique_words.toLocaleString()}
          caption={`${s.hapax_count} used only once`}
          size="lg"
        />
        <StatFigure
          label="Word Variety"
          value={`${(s.type_token_ratio * 100).toFixed(1)}%`}
          caption="distinct words ÷ total words"
          size="lg"
        />
        <StatFigure
          label="Chorus Share"
          value={`${Math.round(s.chorus_ratio * 100)}%`}
          caption="of all lines"
          size="lg"
        />
      </section>

      <section className="grid gap-10 sm:gap-12 lg:grid-cols-[1.1fr_1fr] mt-12">
        <div>
          <WordTable title="Most-used Words" rows={s.top_words_no_stop} max={15} />
          <p className="mt-3 text-[0.78rem] italic text-ink-mute">
            Stopwords filtered. The bar beneath each word is its share of the
            most-used.
          </p>
        </div>

        <div className="space-y-10">
          <Inline label="Avg. word length" value={`${s.avg_word_length} chars`} />
          <Inline label="Avg. words per line" value={String(s.avg_words_per_line)} />
          <Inline label="Sections" value={String(s.section_count)} />
          <Inline
            label="Line repetition"
            value={`${Math.round(s.repetition_ratio * 100)}%`}
          />

          <div>
            <p className="smallcaps mb-3">Longest words</p>
            <p className="font-serif text-2xl leading-snug text-ink">
              {s.longest_words.join(" · ")}
            </p>
          </div>

          {s.section_sequence.length > 0 && (
            <div>
              <p className="smallcaps mb-3">Architecture</p>
              <ol className="border-t border-rule">
                {s.section_sequence.map((kind, i) => (
                  <li
                    key={i}
                    className="grid grid-cols-[2rem_1fr] items-baseline gap-3 border-b border-rule py-1.5"
                  >
                    <span className="figure text-ink-mute text-sm tabular-nums">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-serif italic text-xl text-ink">
                      {kind}
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-[0.78rem] italic text-ink-mute">
                the order, from first to last
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Lyrics — always expanded */}
      <section className="mt-20 border-t border-rule-strong pt-10">
        <header className="text-center mb-8">
          <p className="smallcaps mb-2">The Text</p>
          <h3 className="display text-3xl sm:text-4xl">The lyrics in full</h3>
        </header>
        <pre className="font-serif text-lg leading-[1.7] whitespace-pre-wrap text-ink-soft max-w-3xl mx-auto">
          {song.lyrics}
        </pre>
        <p className="text-[0.72rem] italic text-ink-mute mt-6 text-center">
          Lyrics retrieved via Genius. Shown for analytical purposes only.
        </p>
      </section>
    </article>
  );
}

function Inline({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-rule pb-2">
      <span className="smallcaps">{label}</span>
      <span className="figure text-2xl">{value}</span>
    </div>
  );
}

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase());
}
