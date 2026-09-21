"use client";

import Link from "next/link";
import type { ArtistStats } from "@/lib/types";
import { songPath } from "@/lib/slug";

type Props = {
  stats: ArtistStats;
  artistName: string;
};

/** Three songs from the edges of the catalogue, drifting past; each opens its reading. */
export function HighlightsShowcase({ stats, artistName }: Props) {
  const items = [
    { label: "Shortest song", title: stats.shortest_song?.title, value: `${stats.shortest_song?.words ?? 0} words` },
    {
      label: "Widest vocabulary",
      title: stats.richest_song?.title,
      value: `${stats.richest_song?.ttr ? (stats.richest_song.ttr * 100).toFixed(1) : 0}% variety`,
    },
    { label: "Longest song", title: stats.longest_song?.title, value: `${stats.longest_song?.words ?? 0} words` },
  ].filter((i): i is { label: string; title: string; value: string } => !!i.title);
  if (!items.length) return null;

  return (
    <section className="mt-20 mb-20">
      <div className="overflow-hidden bg-transparent py-8 border-y border-rule-strong mask-edges">
        <style dangerouslySetInnerHTML={{ __html: `
          @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
          .animate-marquee-slow { animation: marquee 60s linear infinite; }
          .mask-edges {
            mask-image: linear-gradient(to right, transparent, black 15%, black 85%, transparent);
            -webkit-mask-image: linear-gradient(to right, transparent, black 15%, black 85%, transparent);
          }
          @media (prefers-reduced-motion: reduce) { .animate-marquee-slow { animation: none; } }
        ` }} />
        <div className="flex whitespace-nowrap animate-marquee-slow w-max hover:[animation-play-state:paused]">
          {[1, 2].map((group) => (
            <div key={group} className="flex items-center gap-24 px-12" aria-hidden={group === 2}>
              {items.map((item) => (
                <div key={item.label} className="flex items-center gap-24">
                  <Link
                    href={songPath(artistName, item.title)}
                    prefetch={false}
                    tabIndex={group === 2 ? -1 : undefined}
                    className="group flex flex-col items-center gap-1 no-underline"
                  >
                    <span className="smallcaps tracking-widest text-[0.65rem]">{item.label}</span>
                    <span className="flex items-baseline gap-3">
                      <span className="font-serif text-2xl text-ink-soft group-hover:text-accent transition-colors">
                        {item.title}
                      </span>
                      <span className="text-ink-mute tabular-nums italic text-sm">({item.value})</span>
                    </span>
                  </Link>
                  <span className="text-ink-mute/30">|</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
