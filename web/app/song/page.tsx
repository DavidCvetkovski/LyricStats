"use client";

import { useState } from "react";
import { getSong } from "@/lib/api";
import type { SongPayload } from "@/lib/types";
import { StatFigure } from "@/components/StatFigure";
import { WordTable } from "@/components/WordTable";
import { PullQuote } from "@/components/PullQuote";

export default function SongPage() {
  const [artist, setArtist] = useState("");
  const [title, setTitle] = useState("");
  const [force, setForce] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [song, setSong] = useState<SongPayload | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!artist || !title) return;
    setLoading(true);
    setError(null);
    try {
      const s = await getSong(artist, title, { force });
      setSong(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSong(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 pt-10 pb-20">
      <header className="border-b border-rule-strong pb-8">
        <p className="smallcaps mb-2">Section II — On a Song</p>
        <h2 className="display text-5xl sm:text-6xl text-ink">A single track, examined.</h2>
        <p className="mt-3 font-serif italic text-xl text-ink-soft max-w-2xl">
          Name an artist and a song. We will retrieve the lyrics, count them, and
          set the result in&nbsp;type.
        </p>
      </header>

      <form onSubmit={onSubmit} className="mt-10 grid gap-8 sm:grid-cols-2">
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
        <div className="sm:col-span-2 flex items-center gap-4">
          <button type="submit" className="pill" disabled={loading}>
            {loading ? "Setting type…" : "Examine →"}
          </button>
          <label className="flex items-center gap-2 text-[0.78rem] text-ink-mute cursor-pointer">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              className="accent-accent"
            />
            re-fetch from source
          </label>
        </div>
      </form>

      {error && (
        <p className="mt-10 font-serif italic text-accent text-lg border-l-2 border-accent pl-4">
          {error}
        </p>
      )}

      {song && <SongView song={song} />}
    </div>
  );
}

function SongView({ song }: { song: SongPayload }) {
  const s = song.stats;
  return (
    <article className="mt-16 rise">
      {/* Article header — hero */}
      <header className="text-center border-b border-rule-strong pb-12">
        <p className="smallcaps mb-3">
          {song.source === "cache" ? "Recalled from the archive" : `Filed via ${song.source}`}
        </p>
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

      {/* Pull quote — the artist's most-used content word */}
      {s.top_words_no_stop[0] && (
        <PullQuote
          cite={`appears ${s.top_words_no_stop[0][1]} times`}
        >
          {s.top_words_no_stop[0][0]}
        </PullQuote>
      )}

      {/* Big figures */}
      <section className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4 my-12">
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
          label="Vocab Richness"
          value={`${(s.type_token_ratio * 100).toFixed(1)}%`}
          caption="unique ÷ total"
          size="lg"
        />
        <StatFigure
          label="Chorus Share"
          value={`${Math.round(s.chorus_ratio * 100)}%`}
          caption="of all lines"
          size="lg"
        />
      </section>

      {/* Body — two-column editorial */}
      <section className="grid gap-12 lg:grid-cols-[1.1fr_1fr] mt-12">
        <div>
          <WordTable
            title="Most-used Words"
            rows={s.top_words_no_stop}
            max={15}
          />
          <p className="mt-3 text-[0.78rem] italic text-ink-mute">
            Stopwords filtered. The bar beneath each word is its share of the
            most-used.
          </p>
        </div>

        <div className="space-y-10">
          <Inline label="Avg. word length" value={`${s.avg_word_length} chars`} />
          <Inline label="Avg. words per line" value={String(s.avg_words_per_line)} />
          <Inline label="Sections" value={String(s.section_count)} />
          <Inline label="Line repetition" value={`${Math.round(s.repetition_ratio * 100)}%`} />

          <div>
            <p className="smallcaps mb-3">Longest words</p>
            <p className="font-serif text-2xl leading-snug text-ink">
              {s.longest_words.join(" · ")}
            </p>
          </div>

          {Object.keys(s.section_kinds).length > 0 && (
            <div>
              <p className="smallcaps mb-3">Architecture</p>
              <ul className="space-y-2">
                {Object.entries(s.section_kinds).map(([kind, n]) => (
                  <li key={kind} className="flex justify-between border-b border-rule py-1">
                    <span className="font-serif italic">{kind}</span>
                    <span className="figure">{n}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* Lyrics — collapsed details */}
      <details className="mt-16 border-t border-rule-strong pt-6 group">
        <summary className="smallcaps cursor-pointer select-none flex items-center justify-between">
          <span>The lyrics in full</span>
          <span className="text-ink-mute group-open:rotate-90 transition-transform">→</span>
        </summary>
        <pre className="mt-6 font-serif text-lg leading-[1.7] whitespace-pre-wrap text-ink-soft max-w-3xl mx-auto">
          {song.lyrics}
        </pre>
        <p className="text-[0.72rem] italic text-ink-mute mt-4 text-center">
          Lyrics retrieved via Genius. Shown for analytical purposes only.
        </p>
      </details>
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
