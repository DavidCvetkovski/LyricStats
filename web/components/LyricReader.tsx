"use client";

import { useMemo, useState } from "react";
import { lyricLines } from "@/lib/songExperience";

export function LyricReader({ lyrics }: { lyrics: string }) {
  const [highlight, setHighlight] = useState(false);
  const lines = useMemo(() => lyricLines(lyrics), [lyrics]);
  return (
    <section className="mt-16 border-t border-rule-strong pt-10">
      <header className="text-center mb-8">
        <p className="smallcaps mb-2">The Text</p>
        <h3 className="display text-3xl sm:text-4xl">Read between the lines.</h3>
        <button type="button" className="pill pill-ghost mt-6" aria-pressed={highlight}
          onClick={() => setHighlight((value) => !value)}>
          {highlight ? "Hide repeated lines" : "Highlight repeated lines"}
        </button>
        <p className="mt-3 text-sm font-serif italic text-ink-mute">
          Matches ignore case and outer spaces; punctuation stays significant.
        </p>
      </header>
      <div className="font-serif text-lg leading-[1.7] whitespace-pre-wrap break-words text-ink-soft max-w-3xl mx-auto">
        {lines.map((line, i) => (
          <div key={i} className={line.heading ? "smallcaps text-accent mt-6 mb-2" : "min-h-[1.7em]"}>
            {highlight && line.repeated ? <mark className="bg-highlight text-ink px-0.5">{line.text}</mark> : line.text || "\u00a0"}
          </div>
        ))}
      </div>
    </section>
  );
}
