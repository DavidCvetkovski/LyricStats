"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArtistAutocomplete } from "@/components/ArtistAutocomplete";
import { getArtistTitles } from "@/lib/api";
import { loadLastSong, saveLastSong } from "@/lib/lastSearch";
import { songPath } from "@/lib/slug";

/** Three readings to start from. All three sit in the catalogue with timed lines. */
const OPENERS: [string, string, string][] = [
  ["Michael Jackson", "Thriller", "A minute before the first word"],
  ["Queen", "Bohemian Rhapsody", "Six minutes, hardly a line repeated"],
  ["Kendrick Lamar", "HUMBLE.", "Two hundred words a minute"],
];

export default function SongPage() {
  return (
    <Suspense fallback={null}>
      <SongSearch />
    </Suspense>
  );
}

function SongSearch() {
  const router = useRouter();
  const params = useSearchParams();
  const [artist, setArtist] = useState("");
  const [title, setTitle] = useState("");
  const [titles, setTitles] = useState<string[]>([]);
  const titlesFor = useRef("");
  const abortRef = useRef<AbortController | null>(null);

  // Old links carried the song in the query string; send them to its page.
  useEffect(() => {
    const a = params.get("artist")?.trim();
    const t = params.get("title")?.trim();
    if (a && t) {
      router.replace(songPath(a, t));
      return;
    }
    const last = loadLastSong();
    if (last) {
      setArtist(last.artist);
      setTitle(last.title);
    }
  }, [params, router]);

  // The title field offers the artist's catalogue once we know the artist.
  function loadTitles(name: string) {
    const wanted = name.trim();
    if (wanted.length < 2 || wanted.toLowerCase() === titlesFor.current) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    getArtistTitles(wanted, ac.signal)
      .then((r) => {
        if (ac.signal.aborted) return;
        titlesFor.current = wanted.toLowerCase();
        setTitles(r.titles);
      })
      .catch(() => {
        /* the field still works without suggestions */
      });
  }

  function go(hash = "") {
    const a = artist.trim();
    const t = title.trim();
    if (!a || !t) return;
    saveLastSong({ artist: a, title: t });
    router.push(songPath(a, t) + hash);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    go();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-16 sm:pb-20">
      <header className="border-b border-rule-strong pb-6 sm:pb-8">
        <p className="smallcaps mb-2">Section II — On a Song</p>
        <h2 className="display text-ink" style={{ fontSize: "clamp(2.25rem, 8vw, 4rem)" }}>
          One song, read closely.
        </h2>
        <p className="mt-3 font-serif italic text-lg sm:text-xl text-ink-soft max-w-2xl">
          Name the artist and the song. We set the words in type, count them, time the lines,
          and mark what comes back.
        </p>
      </header>

      <form onSubmit={onSubmit} className="mt-8 sm:mt-10 grid gap-6 sm:gap-8 sm:grid-cols-2">
        <label className="block">
          <span className="smallcaps mb-1 block">The Artist</span>
          <ArtistAutocomplete
            value={artist}
            onChange={setArtist}
            onPick={loadTitles}
            placeholder="Michael Jackson"
            autoFocus
          />
        </label>
        <label className="block">
          <span className="smallcaps mb-1 block">The Song</span>
          <input
            className="field"
            type="text"
            placeholder="Thriller"
            value={title}
            list="catalogue-titles"
            autoComplete="off"
            maxLength={300}
            onFocus={() => loadTitles(artist)}
            onChange={(e) => setTitle(e.target.value)}
          />
          <datalist id="catalogue-titles">
            {titles.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </label>
        <div className="sm:col-span-2 flex flex-wrap items-center gap-x-4 gap-y-3">
          <button type="submit" className="pill" disabled={!artist.trim() || !title.trim()}>
            Read it →
          </button>
          <button
            type="button"
            className="pill pill-ghost"
            disabled={!artist.trim() || !title.trim()}
            onClick={() => go("#text")}
          >
            Just the words
          </button>
        </div>
      </form>

      <section className="mt-14 sm:mt-20">
        <p className="smallcaps mb-5">Or start with one of these</p>
        <div className="grid gap-x-8 gap-y-6 sm:grid-cols-3">
          {OPENERS.map(([a, t, note]) => (
            <Link
              key={t}
              href={songPath(a, t)}
              prefetch={false}
              className="group border-t border-rule-strong pt-4 hover:text-accent transition-colors"
            >
              <span className="smallcaps block mb-2">{a}</span>
              <span className="display text-3xl block">{t} →</span>
              <span className="mt-2 block text-[0.85rem] italic text-ink-mute group-hover:text-ink-soft">
                {note}
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
