"use client";

import { ArtistStats } from "@/lib/types";

type Props = {
  stats: ArtistStats;
  artistName: string; // Not used currently, but kept for signature
};

export function HighlightsShowcase({ stats }: Props) {
  // Extract the data
  const longestTitle = stats.longest_song?.title || "Unknown";
  const longestWords = stats.longest_song?.words || 0;
  
  const shortestTitle = stats.shortest_song?.title || "Unknown";
  const shortestWords = stats.shortest_song?.words || 0;

  const richestTitle = stats.richest_song?.title || "Unknown";
  const richestVocab = stats.richest_song?.ttr ? (stats.richest_song.ttr * 100).toFixed(1) : 0;

  return (
    <section className="mt-20 mb-20">
      <div className="overflow-hidden bg-transparent py-8 border-y border-rule-strong animate-in fade-in duration-1000">
        <style dangerouslySetInnerHTML={{__html: `
          @keyframes marquee {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
          }
          .animate-marquee-slow {
            animation: marquee 60s linear infinite;
          }
        `}} />
        <div className="flex whitespace-nowrap animate-marquee-slow w-max hover:[animation-play-state:paused] mask-edges">
          {[1, 2, 3].map((group) => (
            <div key={group} className="flex items-center gap-24 px-12">
              <AiryItem label="Shortest Song" title={shortestTitle} value={`${shortestWords} words`} />
              <span className="text-ink-mute/30">|</span>
              <AiryItem label="Widest Vocab" title={richestTitle} value={`${richestVocab}% variety`} />
              <span className="text-ink-mute/30">|</span>
              <AiryItem label="Longest Song" title={longestTitle} value={`${longestWords} words`} />
              <span className="text-ink-mute/30">|</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function AiryItem({ label, title, value }: { label: string; title: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-1 cursor-default">
      <span className="smallcaps text-ink-mute tracking-widest text-[0.65rem]">{label}</span>
      <div className="flex items-baseline gap-3">
        <span className="font-serif text-2xl text-ink-soft">{title}</span>
        <span className="text-ink-mute tabular-nums italic text-sm">({value})</span>
      </div>
    </div>
  );
}
