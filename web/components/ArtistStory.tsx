"use client";

import { useEffect, useRef, useState } from "react";
import { titleCase } from "@/lib/utils";
import type { ArtistStats } from "@/lib/types";

// ── Stat registry ────────────────────────────────────────────────────────────
// Each entry defines a rankable dimension with display + editorial metadata.

type StatDef = {
  key: string;
  percentileKey?: string; // key into stats.percentiles
  getValue: (s: ArtistStats) => number | undefined;
  format: (v: number) => string;
  unit: string;
  label: string | ((isHigh: boolean) => string); // editorial section name, dynamic based on rank
  highCopy: (name: string, pct: number) => string;
  lowCopy: (name: string, pct: number) => string;
  globalMedian: number; // fallback when no percentile
  // For the dot-on-line visual: what range to map onto [0, 100]
  scaleMin: number;
  scaleMax: number;
};

const STAT_REGISTRY: StatDef[] = [
  {
    key: "avg_wpm",
    percentileKey: "avg_wpm",
    getValue: (s) => s.avg_wpm,
    format: (v) => `${Math.round(v)}`,
    unit: "words per minute",
    label: "The Flow",
    highCopy: (n, p) => `${n} delivers lyrics **faster** than ${p}% of all artists — maintaining a relentless pace.`,
    lowCopy: (n, p) => `${n} takes their time — **slower** than ${100 - p}% of artists, letting every word land.`,
    globalMedian: 95,
    scaleMin: 40,
    scaleMax: 200,
  },
  {
    key: "avg_ttr",
    percentileKey: "avg_ttr",
    getValue: (s) => s.avg_ttr,
    format: (v) => `${(v * 100).toFixed(1)}%`,
    unit: "lexical variety",
    label: "The Vocabulary",
    highCopy: (n, p) => `${n} commands a vocabulary **richer** than ${p}% of all artists — rarely repeating a word.`,
    lowCopy: (n, p) => `${n} leans on a tight, **focused** vocabulary — more concentrated than ${100 - p}% of artists.`,
    globalMedian: 0.41,
    scaleMin: 0.2,
    scaleMax: 0.75,
  },
  {
    key: "avg_words_per_song",
    percentileKey: "avg_words_per_song",
    getValue: (s) => s.avg_words_per_song,
    format: (v) => `${Math.round(v)}`,
    unit: "words per song",
    label: "The Output",
    highCopy: (n, p) => `${n} writes **more words** per song than ${p}% of artists — dense, verbose, maximalist.`,
    lowCopy: (n, p) => `${n} keeps it concise, writing **fewer words** per song than ${100 - p}% of all artists.`,
    globalMedian: 243,
    scaleMin: 80,
    scaleMax: 700,
  },
  {
    key: "avg_hook_share",
    percentileKey: "avg_hook_share",
    getValue: (s) => s.avg_hook_share,
    format: (v) => `${(v * 100).toFixed(0)}%`,
    unit: "hook share",
    label: "The Hook",
    highCopy: (n, p) => `${n} is **hook-driven** — more of each song is catchy repetition than ${p}% of artists.`,
    lowCopy: (n, p) => `${n} rarely leans on the hook, leaving **less to repetition** than ${100 - p}% of artists.`,
    globalMedian: 0.29,
    scaleMin: 0.05,
    scaleMax: 0.65,
  },
  {
    key: "avg_rhyme",
    percentileKey: "avg_rhyme",
    getValue: (s) => s.avg_rhyme,
    format: (v) => `${(v * 100).toFixed(0)}%`,
    unit: "rhyme density",
    label: "The Rhyme",
    highCopy: (n, p) => `${n} rhymes **harder** than ${p}% of all artists — nearly every line finds its echo.`,
    lowCopy: (n, p) => `${n} cares **less for rhyme** than ${100 - p}% of artists, choosing words for meaning over sound.`,
    globalMedian: 0.25,
    scaleMin: 0.05,
    scaleMax: 0.55,
  },
  {
    key: "avg_repetition_ratio",
    getValue: (s) => s.avg_repetition_ratio,
    format: (v) => `${(v * 100).toFixed(0)}%`,
    unit: "line repetition",
    label: "The Echo",
    highCopy: (n, p) => `${n} **repeats** their lines more than ${p}% of all artists — building mantras, not verses.`,
    lowCopy: (n, p) => `${n} rarely says the same thing twice — **less repetitive** than ${100 - p}% of artists.`,
    globalMedian: 0.31,
    scaleMin: 0.10,
    scaleMax: 0.70,
  },
  {
    key: "question_share",
    getValue: (s) => s.question_share,
    format: (v) => `${(v * 100).toFixed(1)}%`,
    unit: "questions asked",
    label: (isHigh) => isHigh ? "The Interrogator" : "The Conviction",
    highCopy: (n, p) => `${n} asks questions in ${p}% **more** of their lines than the median artist.`,
    lowCopy: (n, p) => `${n} rarely asks questions — ${100 - p}% **fewer** than the average lyricist.`,
    globalMedian: 0.035,
    scaleMin: 0,
    scaleMax: 0.12,
  },
  {
    key: "avg_word_length",
    getValue: (s) => s.avg_word_length,
    format: (v) => v.toFixed(1),
    unit: "chars per word",
    label: "The Weight",
    highCopy: (n, p) => `${n} uses heavier, **longer words** than ${p}% of all artists — polysyllabic and deliberate.`,
    lowCopy: (n, p) => `${n} favours short, **punchy** words — more compact than ${100 - p}% of artists.`,
    globalMedian: 4.2,
    scaleMin: 3.0,
    scaleMax: 6.0,
  },
];

// ── Interestingness scoring ──────────────────────────────────────────────────

type RankedStat = {
  def: StatDef;
  value: number;
  percentile: number; // 0–100, computed or estimated
  score: number;      // |percentile - 50|, higher = more interesting
  isHigh: boolean;    // above median?
};

function rankStats(stats: ArtistStats): RankedStat[] {
  const ranked: RankedStat[] = [];

  for (const def of STAT_REGISTRY) {
    const value = def.getValue(stats);
    if (value == null || value === 0) continue;

    let percentile: number;
    if (def.percentileKey && stats.percentiles?.[def.percentileKey] != null) {
      percentile = stats.percentiles[def.percentileKey]!;
    } else {
      // Estimate percentile from deviation against global median
      const deviation = (value - def.globalMedian) / def.globalMedian;
      percentile = Math.max(0, Math.min(100, 50 + deviation * 50));
    }

    ranked.push({
      def,
      value,
      percentile,
      score: Math.abs(percentile - 50),
      isHigh: percentile >= 50,
    });
  }

  // Split into highs and lows, each sorted by extremity
  const highs = ranked.filter(r => r.isHigh).sort((a, b) => b.score - a.score);
  const lows = ranked.filter(r => !r.isHigh).sort((a, b) => b.score - a.score);

  // Pick top 2 positives + 1 negative (the "worst" stat)
  const result: RankedStat[] = [];
  result.push(...highs.slice(0, 2));
  if (lows.length > 0) {
    result.push(lows[0]);
  } else if (highs.length > 2) {
    result.push(highs[2]);
  }
  return result;
}

// ── Highlighted Text Helper ──────────────────────────────────────────────────

function HighlightedText({ text, isHero = false }: { text: string; isHero?: boolean }) {
  if (!text) return null;
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className={isHero ? "text-accent" : "text-ink font-medium"}>
            {part}
          </span>
        ) : (
          part
        )
      )}
    </>
  );
}

// ── Vocal Signature Box ──────────────────────────────────────────────────────

function VocalSignatureBox({ 
  word, 
  count, 
  songCount,
  quote
}: { 
  word: string; 
  count: number; 
  songCount: number;
  quote?: { quote: string; song_title: string } | null;
}) {
  return (
    <div className="border border-rule-strong p-6 bg-paper-soft text-center w-full max-w-[280px] md:max-w-xs relative paper-grain shadow-sm transition-all duration-700">
      <div className="absolute inset-1 border border-dashed border-rule-strong/60 pointer-events-none" />
      <span className="smallcaps text-accent block mb-2">Vocal Signature</span>
      <div className="font-serif italic text-4xl text-ink font-bold my-4 leading-none break-words">
        &ldquo;{word}&rdquo;
      </div>
      
      {quote ? (
        <div className="mt-6 mb-2 text-left border-l-2 border-accent/40 pl-4">
          <p className="font-serif italic text-sm text-ink leading-relaxed mb-2">
            &ldquo;{quote.quote}&rdquo;
          </p>
          <span className="text-[0.65rem] uppercase tracking-wider text-ink-soft font-sans font-semibold block">
            — {quote.song_title}
          </span>
        </div>
      ) : (
        <p className="font-serif text-sm text-ink-soft leading-normal mb-2">
          Repeated <strong className="font-sans font-bold text-ink">{count.toLocaleString()}</strong> times
          <br />
          across <strong className="font-sans font-bold text-ink">{songCount}</strong> songs
        </p>
      )}
    </div>
  );
}

// ── Counting number hook ─────────────────────────────────────────────────────

function useCountUp(target: number, active: boolean, duration = 1200, delay = 0): number {
  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!active) {
      setCurrent(0);
      return;
    }
    const start = performance.now() + delay;
    const animate = (now: number) => {
      if (now < start) {
        rafRef.current = requestAnimationFrame(animate);
        return;
      }
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(target * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, active, duration, delay]);

  return current;
}

// ── Intersection observer (fires once) ───────────────────────────────────────

function useScrollReveal(threshold = 0.3) {
  const [revealed, setRevealed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setRevealed(true); },
      { threshold }
    );
    obs.observe(el);
    return () => obs.unobserve(el);
  }, [threshold]);

  return { ref, revealed };
}

// ── Roman numerals ───────────────────────────────────────────────────────────

const ROMAN = ["I", "II", "III", "IV", "V"];

// ── Animation A: The Typewriter ──────────────────────────────────────────────

type Align = "left" | "right";

function TypewriterCard({
  stat,
  index,
  isHero,
  artistName,
  align = "left",
  topWord,
  songCount,
}: {
  stat: RankedStat;
  index: number;
  isHero?: boolean;
  artistName?: string;
  align?: Align;
  topWord?: [string, number];
  songCount?: number;
  motifQuote?: { word: string; quote: string; song_title: string } | null;
}) {
  const { ref, revealed } = useScrollReveal(0.25);
  // The hero number is the percentile (always impressive side)
  const displayPct = stat.isHigh
    ? Math.round(stat.percentile)
    : Math.round(100 - stat.percentile);
  const counted = useCountUp(displayPct, revealed, 1400, isHero ? 500 : 200);

  // The actual stat value shown smaller
  const formatted = stat.def.format(stat.value);

  // Dot positions on the comparison line
  const medianPct = 50;
  const artistPct = Math.max(3, Math.min(97, stat.percentile));

  const contextCopy = stat.isHigh
    ? stat.def.highCopy("They", Math.round(stat.percentile))
    : stat.def.lowCopy("They", Math.round(stat.percentile));
  const contextClean = contextCopy
    .replace("They", "")
    .replace(/^\s*/, "")
    .replace(/^./, (c) => c.toUpperCase());

  // Build the hero headline copy
  const heroCopy = artistName
    ? (stat.isHigh
        ? stat.def.highCopy(titleCase(artistName), Math.round(stat.percentile))
        : stat.def.lowCopy(titleCase(artistName), Math.round(stat.percentile)))
    : "";

  const twPadding = ["py-12 sm:py-16", "py-14 sm:py-18", "py-10 sm:py-14"];
  const twFontSize = ["clamp(4rem, 15vw, 8rem)", "clamp(3rem, 12vw, 6rem)", "clamp(2.25rem, 9vw, 4.5rem)"];

  const cardContent = (
    <>
      {/* Hero headline — only on first card */}
      {isHero && (
        <h3
          className="font-serif italic text-2xl sm:text-3xl lg:text-4xl text-ink leading-relaxed max-w-4xl mb-12 sm:mb-16 transition-all duration-1200 ease-out"
          style={{
            opacity: revealed ? 1 : 0,
            transform: revealed ? "translateY(0)" : "translateY(16px)",
          }}
        >
          &ldquo;<HighlightedText text={heroCopy} isHero={true} />&rdquo;
        </h3>
      )}

      {/* Label */}
      <div
        className="smallcaps text-ink-mute mb-5 transition-all duration-700"
        style={{
          opacity: revealed ? 1 : 0,
          transform: revealed ? "translateY(0)" : "translateY(8px)",
          transitionDelay: isHero ? "400ms" : "0ms",
        }}
      >
        {ROMAN[index]}. {typeof stat.def.label === 'function' ? stat.def.label(stat.isHigh) : stat.def.label}
      </div>

      {/* Big number — the percentile */}
      <div className="overflow-hidden">
        <div
          className="figure text-ink transition-all duration-1000 ease-out"
          style={{
            fontSize: twFontSize[index] || twFontSize[2],
            lineHeight: 1,
            opacity: revealed ? 1 : 0,
            transform: revealed ? "translateY(0)" : "translateY(24px)",
            transitionDelay: isHero ? "500ms" : "200ms",
          }}
        >
          {revealed ? counted : 0}%
        </div>
      </div>

      {/* Actual stat value — smaller */}
      <div
        className="font-serif text-lg sm:text-xl text-ink-soft mt-2 transition-all duration-700"
        style={{
          opacity: revealed ? 1 : 0,
          transform: revealed ? "translateY(0)" : "translateY(8px)",
          transitionDelay: isHero ? "700ms" : "400ms",
        }}
      >
        {formatted} {stat.def.unit}
      </div>

      {/* Comparison line */}
      <div className={`relative w-full h-10 mt-8 mb-4 flex items-center ${align === "right" ? "ml-auto" : ""}`}>
        {/* The Line */}
        <div
          className="absolute left-0 h-[1px] bg-rule-strong transition-all duration-700 ease-out"
          style={{ width: revealed ? "100%" : "0%", transitionDelay: isHero ? "700ms" : "400ms" }}
        />
        {/* Median Ball (Solid) */}
        <div
          className="absolute rounded-full bg-ink-mute transition-all duration-500"
          style={{
            left: `calc(${medianPct}% - 3px)`,
            width: "6px",
            height: "6px",
            opacity: revealed ? 1 : 0,
            transform: revealed ? "scale(1)" : "scale(0)",
            transitionDelay: isHero ? "1000ms" : "700ms",
            zIndex: 1,
          }}
        />
        {/* Artist Ball (Solid with cut) */}
        <div
          className="absolute rounded-full border-[3px] border-paper bg-accent transition-all duration-1000 ease-out"
          style={{
            left: revealed ? `calc(${artistPct}% - 8px)` : `calc(${medianPct}% - 8px)`,
            width: "16px",
            height: "16px",
            opacity: revealed ? 1 : 0,
            zIndex: 10,
            transitionDelay: isHero ? "900ms" : "600ms",
          }}
        />
      </div>

      {/* Context text — only on non-hero cards (hero has the headline instead) */}
      {!isHero && (
        <p
          className="font-serif italic text-base sm:text-lg text-ink-soft mt-6 max-w-xl transition-all duration-700 delay-1000"
          style={{
            opacity: revealed ? 1 : 0,
            transform: revealed ? "translateY(0)" : "translateY(8px)",
          }}
        >
          <HighlightedText text={contextClean} />
        </p>
      )}
    </>
  );

  return (
    <div ref={ref} className={`max-w-4xl mx-auto ${twPadding[index] || twPadding[2]}`}>
      {isHero && topWord ? (
        <div className="grid md:grid-cols-[1fr_280px] gap-8 md:gap-12 items-center">
          <div className={align === "right" ? "text-right" : "text-left"}>
            {cardContent}
          </div>
          <div
            className="flex justify-center md:justify-end transition-all duration-1000 ease-out"
            style={{
              opacity: revealed ? 1 : 0,
              transform: revealed ? "translateY(0) scale(1)" : "translateY(16px) scale(0.95)",
              transitionDelay: isHero ? "600ms" : "0ms",
            }}
          >
            <VocalSignatureBox word={topWord[0]} count={topWord[1]} songCount={songCount ?? 0} />
          </div>
        </div>
      ) : (
        <div className={align === "right" ? "text-right" : "text-left"}>
          {cardContent}
        </div>
      )}
    </div>
  );
}

// ── Animation C: The Ink Bleed ───────────────────────────────────────────────

function InkBleedCard({
  stat,
  index,
  isHero,
  artistName,
  align = "left",
  topWord,
  songCount,
  motifQuote,
}: {
  stat: RankedStat;
  index: number;
  isHero?: boolean;
  artistName?: string;
  align?: Align;
  topWord?: [string, number];
  songCount?: number;
  motifQuote?: { word: string; quote: string; song_title: string } | null;
}) {
  const { ref, revealed } = useScrollReveal(0.15);
  // Hero number is the percentile (impressive side)
  const displayPct = stat.isHigh
    ? Math.round(stat.percentile)
    : Math.round(100 - stat.percentile);
  const formatted = stat.def.format(stat.value);

  const medianPct = 50;
  const artistPct = Math.max(3, Math.min(97, stat.percentile));

  const contextCopy = stat.isHigh
    ? stat.def.highCopy("They", Math.round(stat.percentile))
    : stat.def.lowCopy("They", Math.round(stat.percentile));
  const contextClean = contextCopy
    .replace("They", "")
    .replace(/^\s*/, "")
    .replace(/^./, (c) => c.toUpperCase());

  const heroCopy = artistName
    ? (stat.isHigh
        ? stat.def.highCopy(titleCase(artistName), Math.round(stat.percentile))
        : stat.def.lowCopy(titleCase(artistName), Math.round(stat.percentile)))
    : "";

  const ibPadding = ["py-12 sm:py-20", "py-16 sm:py-22", "py-12 sm:py-16"];
  const ibFontSize = ["clamp(8rem, 30vw, 16rem)", "clamp(5.5rem, 22vw, 12rem)", "clamp(4rem, 16vw, 9rem)"];

  const cardContent = (
    <>
      {/* Hero headline — only on first card */}
      {isHero && (
        <h3
          className="font-serif italic text-2xl sm:text-3xl lg:text-4xl text-ink leading-relaxed max-w-4xl mb-12 sm:mb-16 transition-all duration-1200 ease-out"
          style={{
            opacity: revealed ? 1 : 0,
            transform: revealed ? "translateY(0)" : "translateY(16px)",
          }}
        >
          &ldquo;{heroCopy}&rdquo;
        </h3>
      )}

      {/* Ghost watermark — the percentile */}
      <div
        className="transition-all ease-out select-none"
        style={{
          transitionDuration: "1800ms",
          fontSize: ibFontSize[index] || ibFontSize[2],
          lineHeight: 0.85,
          fontFamily: "var(--font-serif), Georgia, serif",
          fontFeatureSettings: '"tnum", "lnum"',
          letterSpacing: "-0.03em",
          color: "var(--ink)",
          opacity: revealed ? 1 : 0.06,
          transform: revealed ? "scale(1)" : "scale(1.15)",
          transformOrigin: "left center",
          transitionDelay: isHero ? "400ms" : "0ms",
        }}
      >
        {displayPct}%
      </div>

      {/* Label */}
      <div
        className="smallcaps text-ink-mute mt-4 transition-all duration-1000"
        style={{
          opacity: revealed ? 1 : 0,
          transform: revealed ? "translateY(0)" : "translateY(12px)",
          transitionDelay: isHero ? "700ms" : "300ms",
        }}
      >
        {ROMAN[index]}. {typeof stat.def.label === 'function' ? stat.def.label(stat.isHigh) : stat.def.label}
      </div>

      {/* Actual stat value — smaller */}
      <div
        className="font-serif text-xl sm:text-2xl text-ink-soft mt-1 transition-all duration-1000"
        style={{
          opacity: revealed ? 1 : 0,
          transform: revealed ? "translateY(0)" : "translateY(12px)",
          transitionDelay: isHero ? "900ms" : "500ms",
        }}
      >
        {formatted} {stat.def.unit}
      </div>

      {/* Comparison line */}
      <div className={`relative w-full max-w-md h-6 mt-8 flex items-center ${align === "right" ? "ml-auto" : ""}`}>
        {/* The Line */}
        <div
          className="absolute left-0 h-[1px] bg-rule-strong transition-all duration-1000 ease-out"
          style={{ width: revealed ? "100%" : "0%", transitionDelay: isHero ? "900ms" : "500ms" }}
        />
        {/* Median Ball (Solid) */}
        <div
          className="absolute rounded-full bg-ink-mute transition-all duration-700"
          style={{
            left: `calc(${medianPct}% - 2px)`,
            width: "4px",
            height: "4px",
            opacity: revealed ? 1 : 0,
            transform: revealed ? "scale(1)" : "scale(0)",
            transitionDelay: isHero ? "1200ms" : "800ms",
            zIndex: 1,
          }}
        />
        {/* Artist Ball (Solid with cut) */}
        <div
          className="absolute rounded-full bg-accent border-[3px] border-paper transition-all duration-1000 ease-out"
          style={{
            left: revealed ? `calc(${artistPct}% - 7px)` : `calc(${medianPct}% - 7px)`,
            width: "14px",
            height: "14px",
            opacity: revealed ? 1 : 0,
            zIndex: 10,
            transitionDelay: isHero ? "1200ms" : "800ms",
          }}
        />
      </div>

      {/* Context — only on non-hero cards */}
      {!isHero && (
        <p
          className="font-serif italic text-base sm:text-lg text-ink-soft mt-5 max-w-lg transition-all duration-1000 delay-1200"
          style={{
            opacity: revealed ? 1 : 0,
            transform: revealed ? "translateY(0)" : "translateY(10px)",
          }}
        >
          {contextClean}
        </p>
      )}
    </>
  );

  return (
    <div
      ref={ref}
      className={`relative max-w-4xl mx-auto overflow-hidden ${ibPadding[index] || ibPadding[2]}`}
    >
      {isHero && topWord ? (
        <div className="grid md:grid-cols-[1fr_280px] gap-8 md:gap-12 items-center">
          <div className={align === "right" ? "text-right" : "text-left"}>
            {cardContent}
          </div>
          <div
            className="flex justify-center md:justify-end transition-all duration-1000 ease-out"
            style={{
              opacity: revealed ? 1 : 0,
              transform: revealed ? "translateY(0) scale(1)" : "translateY(16px) scale(0.95)",
              transitionDelay: isHero ? "600ms" : "0ms",
            }}
          >
            <VocalSignatureBox word={topWord[0]} count={topWord[1]} songCount={songCount ?? 0} quote={motifQuote} />
          </div>
        </div>
      ) : (
        <div className={align === "right" ? "text-right" : "text-left"}>
          {cardContent}
        </div>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

type AnimMode = "typewriter" | "inkbleed";

type Props = {
  artistName: string;
  stats: ArtistStats;
  topFreqNoun: [string, number] | null;
};

export function ArtistStory({ artistName, stats, topFreqNoun }: Props) {
  const [mode, setMode] = useState<AnimMode>("typewriter");
  const top3 = rankStats(stats);
  const ALIGNS: Align[] = ["left", "right", "left"];

  if (top3.length === 0) return null;

  const Card = mode === "typewriter" ? TypewriterCard : InkBleedCard;
  
  const bestWord = stats.motif_quote?.word || topFreqNoun?.[0] || stats.top_words_no_stop?.[0]?.[0] || "";
  const bestWordCount = stats.top_words_no_stop?.find(w => w[0] === bestWord)?.[1] || topFreqNoun?.[1] || stats.top_words_no_stop?.[0]?.[1] || 0;

  return (
    <div className="mt-16 mb-20">
      {/* Mode toggle — hidden for now, sticking with Typewriter */}
      {/*
      <div className="flex justify-center gap-2 mb-8">
        <button
          type="button"
          onClick={() => setMode("typewriter")}
          className={`text-[0.65rem] uppercase tracking-[0.18em] px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
            mode === "typewriter"
              ? "border-accent text-accent bg-accent/5"
              : "border-rule-strong text-ink-mute hover:text-ink"
          }`}
        >
          A · Typewriter
        </button>
        <button
          type="button"
          onClick={() => setMode("inkbleed")}
          className={`text-[0.65rem] uppercase tracking-[0.18em] px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
            mode === "inkbleed"
              ? "border-accent text-accent bg-accent/5"
              : "border-rule-strong text-ink-mute hover:text-ink"
          }`}
        >
          C · Ink Bleed
        </button>
      </div>
      */}

      {/* Top 3 stat cards — first one is the hero with headline baked in */}
      <div className="divide-y divide-rule">
        {top3.map((stat, i) => (
          <Card
            key={`${mode}-${stat.def.key}`}
            stat={stat}
            index={i}
            isHero={i === 0}
            artistName={i === 0 ? artistName : undefined}
            align={ALIGNS[i]}
            topWord={[bestWord, bestWordCount]}
            songCount={stats.song_count}
            motifQuote={stats.motif_quote}
          />
        ))}
      </div>
    </div>
  );
}


// Keep the old export for backward compatibility with any existing INDUSTRY_AVG references
export const INDUSTRY_AVG = {
  wordsPerSong: 243,
  wordVariety: 0.41,
  chorusShare: 0.29,
  repetition: 0.31,
};
