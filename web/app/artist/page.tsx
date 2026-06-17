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
import { ArtistStory } from "@/components/ArtistStory";
import { HighlightsShowcase } from "@/components/HighlightsShowcase";
import { ProgressLine } from "@/components/ProgressLine";
import { loadLastArtist, saveLastArtist } from "@/lib/lastSearch";
import { friendlyError, type FriendlyError } from "@/lib/errors";
import { ErrorNote } from "@/components/ErrorNote";
import { artistCache } from "@/lib/cache";
import { titleCase } from "@/lib/utils";
import { ArtistAutocomplete } from "@/components/ArtistAutocomplete";

const NON_NOUNS = new Set([
  // Auxiliary / Modal / Pronouns / Stop-words
  "im", "dont", "cant", "wanna", "gonna", "gotta", "aint", "cause", "cuz", "bout", "em", "ya", "yall", "yeah", "yes", "no", "oh", "ah", "ooh", "uh", "la", "da", "na", "hey", "whoa", "yeh", "let",
  // Common verbs & filler
  "know", "get", "got", "go", "make", "see", "say", "come", "want", "look", "tell", "think", "feel", "take", "give", "need", "keep", "find", "leave", "show", "try", "call", "play", "put", "turn", "break", "hold", "bring", "fall", "run", "stop", "hear", "wait", "stand", "live", "die", "believe", "care", "start", "watch", "walk", "mean", "seem", "talk", "miss", "forget", "remember", "cry", "smile", "laugh", "sleep", "wake", "dream", "fly",
  "like", "still", "even", "back", "thing", "things", "way", "really", "much", "never", "always", "just", "only", "well", "too", "very", "so", "also", "another", "other", "ro", "dem", "dat", "dis", "tha", "imma",
  // Adjectives / Adverbs
  "good", "bad", "right", "wrong", "true", "false", "real", "fake", "hot", "cold", "high", "low", "fast", "slow", "hard", "soft", "new", "old", "young", "early", "late", "first", "last", "next", "only", "just", "very", "too", "so", "much", "little", "more", "less", "always", "never", "sometimes", "often", "now", "then", "soon", "later", "today", "tomorrow", "yesterday", "tonight", "here", "there", "up", "down", "in", "out", "on", "off", "over", "under", "above", "below", "behind", "front", "back", "left", "right", "near", "far", "close", "away", "well", "better", "best", "worse", "worst", "all", "some", "any", "none", "every", "both", "many", "few", "other", "same", "different", "own", "really",
  // Specific English generic/fallback adverbs and verbs
  "yet", "wouldve", "shouldve", "couldve", "isnt", "didnt", "wasnt", "wont", "wanted", "gave", "saw", "said", "who", "what", "where", "when", "why", "how", "which", "whose", "whom", "this", "that", "these", "those",
  // BHS non-nouns
  "znam", "hoću", "neću", "mogu", "nemogu", "volim", "želim", "kažem", "mislim", "vidim", "čujem", "idem", "dođem", "čekam", "dajem", "uzmem", "dobar", "loš", "lep", "ružan", "veliki", "mali", "dug", "kratak", "brz", "spor", "topao", "hladan", "nov", "star", "mlad", "jak", "slab", "lak", "težak", "pun", "prazan", "moj", "tvoj", "njegov", "njen", "naš", "vaš", "njihov", "ovo", "ono", "to", "sve", "ništa", "nešto", "svako", "niko", "neko", "uvek", "nikad", "ponekad", "često", "retko", "sada", "onda", "posle", "pre", "juče", "danas", "sutra", "ovde", "tamo", "negde", "svuda", "nigde", "da", "ne", "možda", "kao", "kako", "zašto", "zato", "ali", "ili", "ako", "jer", "dok", "kroz", "preko", "oko", "sa", "bez", "iz", "od", "do", "na", "u", "po", "o", "pri", "k", "ka", "uz", "niz", "jako", "mnogo", "malo", "više", "manje", "samo", "još", "već", "tek", "baš", "čak", "zar", "šta", "ko", "koji", "kakav", "koliki", "čiji", "sam", "si", "je", "smo", "ste", "su", "cu", "ces", "ce", "cemo", "cete", "ću", "ćeš", "će", "ćemo", "ćete", "te", "me", "se", "mi", "ti", "mu", "joj", "nam", "vam", "im", "ih", "nas", "vas",
  // Top 30 Universal English Cliches
  "love", "time", "girl", "boy", "baby", "way", "day", "night", "life", "heart", "man", "woman", "thing", "cause", "world", "mind", "eye", "eyes", "face", "word", "nothing", "everything", "yeah", "shit", "nigga", "niggas", "bitch", "bitches", "fuck", "money",
  // Top 15 Universal Balkan Cliches
  "ljubav", "srce", "duša", "oči", "noć", "dan", "život", "suze", "bol", "tuga", "pesma", "pjesma", "sreća", "zora", "nebo", "balkan"
]);

// @ts-expect-error - wink-pos-tagger has no typescript definitions
import posTagger from "wink-pos-tagger";

const tagger = posTagger();

const AD_LIBS = new Set(["ooh", "ah", "oh", "uh", "la", "da", "na", "hey", "whoa", "yeh", "yeah", "imma", "yes", "no"]);

function getTopNoun(
  signatureWords?: [string, number, number][] | null,
  topWordsNoStop?: [string, number][] | null
): [string, number] | null {
  // 1. If we have Signature Words, use Mathematical Scoring: Count * Log(Ratio)
  if (signatureWords && signatureWords.length > 0) {
    const scoredWords = signatureWords.map(w => {
      const cleanWord = w[0].replace(/['’]/g, "").toLowerCase();
      // Score = Count * Max(0, Log(Ratio))
      const score = w[1] * Math.max(0, Math.log(w[2]));
      return { word: w[0], cleanWord, count: w[1], score, original: w };
    });

    // Sort by highest score
    scoredWords.sort((a, b) => b.score - a.score);

    // Find the first valid Noun that isn't a cliche
    for (const item of scoredWords) {
      if (item.word.length <= 2) continue;
      if (item.word.includes("'") || item.word.includes("’")) continue;
      if (NON_NOUNS.has(item.cleanWord)) continue;

      const tags = tagger.tagSentence(item.word);
      if (tags.length > 0) {
        const pos = tags[0].pos;
        // Accept Nouns and Plural Nouns. Reject Proper Nouns (names like 'Buba' or 'Karli')
        if (pos === 'NN' || pos === 'NNS') {
          return [item.word, item.count];
        }
      }
    }

    // Fallback: If no nouns found (often happens for Balkan artists due to English ML tagger),
    // just return the mathematically highest scoring word that isn't a cliche!
    for (const item of scoredWords) {
      if (item.word.length <= 2) continue;
      if (item.word.includes("'") || item.word.includes("’")) continue;
      if (!NON_NOUNS.has(item.cleanWord)) {
        return [item.word, item.count];
      }
    }
  }

  // 2. Absolute Desperate Fallback to Top Frequency Words
  if (topWordsNoStop && topWordsNoStop.length > 0) {
    for (const [w, c] of topWordsNoStop) {
      if (w.length <= 2) continue;
      if (w.includes("'") || w.includes("’")) continue;
      
      const cleanWord = w.replace(/['’]/g, "").toLowerCase();
      if (!NON_NOUNS.has(cleanWord)) {
        return [w, c];
      }
    }
    // Final desperate return
    for (const [w, c] of topWordsNoStop) {
      if (!w.includes("'") && !w.includes("’")) return [w, c];
    }
    return topWordsNoStop.length > 0 ? topWordsNoStop[0] : null;
  }

  return null;
}

function getTopFreqNoun(topWordsNoStop?: [string, number][] | null): [string, number] | null {
  if (!topWordsNoStop || topWordsNoStop.length === 0) return null;
  
  for (const [w, c] of topWordsNoStop) {
    if (w.length <= 2) continue;
    if (w.includes("'") || w.includes("’")) continue;
    
    const cleanWord = w.replace(/['’]/g, "").toLowerCase();
    if (AD_LIBS.has(cleanWord)) continue;
    
    const tags = tagger.tagSentence(w);
    if (tags.length > 0) {
      const pos = tags[0].pos;
      if (pos === 'NN' || pos === 'NNS') {
        return [w, c];
      }
    }
  }
  
  // Desperate fallback for non-English artists where tagger fails
  for (const [w, c] of topWordsNoStop) {
    if (w.length <= 2) continue;
    if (w.includes("'") || w.includes("’")) continue;
    const cleanWord = w.replace(/['’]/g, "").toLowerCase();
    if (AD_LIBS.has(cleanWord)) continue;
    return [w, c];
  }
  
  for (const [w, c] of topWordsNoStop) {
    if (!w.includes("'") && !w.includes("’")) {
      const cleanWord = w.replace(/['’]/g, "").toLowerCase();
      if (!AD_LIBS.has(cleanWord)) return [w, c];
    }
  }
  
  return topWordsNoStop.length > 0 ? topWordsNoStop[0] : null;
}

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
    if (cached) return cached.key.split("|")[0];
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
      /*
      // LIVE FETCHING DISABLED ON THE FRONTEND
      // We rely exclusively on the database/backend scripts to populate data.
      for (let i = 0; i < total; i++) {
        if (signal.aborted) return;
        const ref = pool.to_fetch[i];
        setProgress({ done: i, total, current: ref.title });
        await fetchSongById(pool.name, ref, signal);
      }
      if (total > 0) setProgress({ done: total, total, current: "done" });
      */
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

  const examine = useCallback(
    (n: string) => {
      if (!n) return;
      // Fresh shuffle token on every search → new random sample.
      const shuffle = Math.random().toString(36).slice(2, 10);
      // Mark this key as handled so the URL change below doesn't double-run,
      // then kick the search off directly (don't depend on param reactivity).
      lastKey.current = `${n}|${min}|${shuffle}`;
      const q = new URLSearchParams({
        name: n,
        min: String(min),
        shuffle,
      }).toString();
      router.push(`/artist?${q}`);
      run(n, min, shuffle);
    },
    [min, router, run],
  );

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    examine(name);
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
          <ArtistAutocomplete
            value={name}
            onChange={setName}
            onPick={(picked) => {
              setName(picked);
              examine(picked);
            }}
            placeholder="Buba Corelli"
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

type SortField = "title" | "words" | "unique" | "variety";
type SortOrder = "asc" | "desc";

function ArtistView({ data }: { data: ArtistPayload }) {
  const s = data.stats;
  const containerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!containerRef.current) return;
      const element = containerRef.current;
      const targetY = Math.max(0, element.getBoundingClientRect().top + window.scrollY - 24);
      const startY = window.scrollY;
      const distance = targetY - startY;

      if (Math.abs(distance) < 8) return;

      const duration = 1500; // Slower, more gentle duration
      let startTime: number | null = null;

      function step(timestamp: number) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease-in-out Quart (distinct acceleration, fast middle, gentle slow down)
        const eased = progress < 0.5 
          ? 8 * Math.pow(progress, 4) 
          : 1 - Math.pow(-2 * progress + 2, 4) / 2;
          
        window.scrollTo(0, startY + distance * eased);

        if (progress < 1) {
          requestAnimationFrame(step);
        }
      }

      requestAnimationFrame(step);
    }, 200);

    return () => clearTimeout(timer);
  }, [data.name]);

  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("words");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder(field === "title" ? "asc" : "desc");
    }
  };

  function sortValue(song: (typeof data.songs)[0]): string | number {
    switch (sortField) {
      case "title":    return song.title.toLowerCase();
      case "words":    return song.word_count;
      case "unique":   return song.unique_words;
      case "variety":  return song.type_token_ratio;
    }
  }

  const topSongs = [...data.songs]
    .filter((song) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      return (
        song.title.toLowerCase().includes(q) ||
        (song.album?.toLowerCase().includes(q) ?? false)
      );
    })
    .sort((a, b) => {
      const va = sortValue(a);
      const vb = sortValue(b);
      if (va < vb) return sortOrder === "asc" ? -1 : 1;
      if (va > vb) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });

  // Only show structure-derived figures when there's real section data.
  // Dataset artists carry it at the payload level (no per-song list to infer
  // from); lyrics-backed artists infer it from the sampled songs.
  const hasSections = data.has_sections ?? data.songs.some((song) => song.has_sections);
  // Dataset aggregates have no per-song catalogue to show.
  const hasCatalogue = data.songs.length > 0;
  const topNoun = getTopNoun(s.signature_words, s.top_words_no_stop);
  const topFreqNoun = getTopFreqNoun(s.top_words_no_stop);

  return (
    <article ref={containerRef} className="mt-16 rise">
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
        {data.limited && (
          <p className="mt-2 text-[0.72rem] uppercase tracking-[0.18em] text-ink-mute">
            Limited view — this artist isn’t in our dataset, so only{" "}
            {s.song_count} {s.song_count === 1 ? "song was" : "songs were"} found
          </p>
        )}
        {data.source === "cache" && data.cached_total > data.sampled && (
          <p className="mt-2 text-[0.78rem] italic text-ink-mute">
            a random sample of {data.sampled} drawn from a catalogue of {data.cached_total}
          </p>
        )}
        {data.source === "dataset" && data.cached_total > data.sampled && (
          <p className="mt-2 text-[0.78rem] italic text-ink-mute">
            full catalogue analysis • top {data.sampled} longest songs displayed below
          </p>
        )}
      </header>


      <ArtistStory 
        artistName={data.name} 
        stats={s}
        topFreqNoun={topFreqNoun}
      />

      <HighlightsShowcase stats={s} artistName={data.name} />

      {/* Put WordTable and Top Noun side-by-side */}
      {s.top_words_no_stop && s.top_words_no_stop.length > 0 && (
        <section className="mt-16 sm:mt-24 max-w-5xl mx-auto px-4">
          {(() => {
            if (!topNoun) return null;
            return (
              <div className="grid md:grid-cols-[auto_auto_auto] gap-8 md:gap-20 items-start justify-center w-full">
                
                {/* Left Side: Quote Pull (Top Left) */}
                <div className="flex flex-col max-w-xs opacity-80 pt-2">
                  <blockquote className="relative pt-4">
                    <span className="absolute top-0 left-0 text-7xl text-rule font-serif leading-none -ml-5 mt-1">"</span>
                    <p className="relative z-10 font-serif italic text-lg leading-snug text-ink-soft">
                      {s.motif_quote ? (
                        s.motif_quote.quote.split(new RegExp(`(${s.motif_quote.word})`, 'gi')).map((part, i) => 
                          part.toLowerCase() === s.motif_quote!.word.toLowerCase() 
                            ? <span key={i} className="text-[#B4995F] font-medium">{part}</span> 
                            : part
                        )
                      ) : (
                        <>This is an example lyric where they use the word <span className="text-[#B4995F] font-medium">{topNoun[0]}</span> to devastating effect.</>
                      )}
                    </p>
                    <div className="mt-4 text-xs uppercase tracking-widest text-ink-mute">
                      — {s.motif_quote ? s.motif_quote.song_title : "Song Name"}
                    </div>
                  </blockquote>
                </div>

                {/* Center: The Motif (Noun) - Pushed Down */}
                <div className="flex flex-col justify-center items-start md:items-end md:text-right pt-6 md:mt-32 md:-translate-x-6">
                  <div className="smallcaps text-ink-mute mb-4 md:mb-6">The Signature</div>
                  <div className="text-7xl sm:text-8xl lg:text-[7rem] leading-none font-serif italic text-[#B4995F] tracking-tight mb-6">
                    {(s.motif_quote?.word || topNoun[0]).toLowerCase()}
                  </div>
                  <p className="font-serif italic text-ink-soft text-lg sm:text-xl max-w-[280px]">
                    An undeniable lyrical fingerprint uniquely woven throughout their catalogue.
                  </p>
                </div>

                {/* Right Side: The Lyrical Staples (Table) */}
                <div className="w-full max-w-xl mx-auto md:mx-0">
                  <WordTable 
                    title="Lyrical Staples" 
                    rows={s.top_words_no_stop?.filter(w => !w[0].includes("'") && !w[0].includes("’") && !AD_LIBS.has(w[0].toLowerCase()))} 
                    motifWord={topNoun[0]} 
                  />
                </div>
              </div>
            );
          })()}
        </section>
      )}

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
                  const [field, order] = e.target.value.split("-") as [SortField, SortOrder];
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
  artistName,
}: {
  label: string;
  title: string;
  detail: string;
  artistName?: string;
}) {
  const content = (
    <div className="border-b border-rule pb-5 group">
      <p className="smallcaps mb-1">{label}</p>
      <p className={`font-serif text-3xl text-ink leading-tight ${artistName ? "group-hover:text-accent transition-colors" : ""}`}>
        {title}
      </p>
      <p className="text-[0.85rem] italic text-ink-mute mt-1">{detail}</p>
    </div>
  );

  if (artistName) {
    return (
      <Link
        href={`/song?artist=${encodeURIComponent(artistName)}&title=${encodeURIComponent(title)}`}
        className="block no-underline"
      >
        {content}
      </Link>
    );
  }

  return content;
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

