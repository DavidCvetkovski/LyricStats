"use client";

import { useState } from "react";

type Entry = [string, number];

export function WordTable({
  title,
  rows,
  max = 10,
  motifWord,
}: {
  title: string;
  rows: Entry[];
  max?: number;
  motifWord?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const top = rows[0]?.[1] ?? 1;

  return (
    <section>
      <header className="mb-4 flex items-baseline justify-between">
        <h3 className="display text-2xl sm:text-3xl">{title}</h3>
        <span className="smallcaps text-ink-mute opacity-0 select-none pointer-events-none">{rows.length} words</span>
      </header>
      <ol className="border-t border-rule-strong">
        {rows.map(([word, n], i) => {
          const isHidden = !expanded && i >= max;
          const indexOffset = i - max;
          // Stagger the reveal transition, but collapse immediately.
          const delay = !isHidden && indexOffset > 0 ? Math.min(200, indexOffset * 30) : 0;
          return (
            <li
              key={word}
              style={{
                maxHeight: isHidden ? "0px" : "44px",
                opacity: isHidden ? 0 : 1,
                transform: isHidden ? "translateY(8px)" : "translateY(0px)",
                paddingTop: isHidden ? "0px" : "8px",
                paddingBottom: isHidden ? "0px" : "8px",
                borderBottomColor: isHidden ? "transparent" : "",
                pointerEvents: isHidden ? "none" : "auto",
                transitionDelay: `${delay}ms`,
              }}
              className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 border-b border-rule overflow-hidden transition-all duration-500 ease-out"
            >
              <span className="figure text-base tabular-nums text-ink-mute">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="relative">
                <span
                  className={`font-serif text-xl ${word === motifWord ? "text-[#B4995F] italic font-medium" : "text-ink"}`}
                  style={{ fontFamily: "var(--font-serif), Georgia, serif" }}
                >
                  {word}
                </span>
                <span
                  aria-hidden
                  className={`block absolute -bottom-0.5 left-0 h-px ${word === motifWord ? "bg-[#B4995F]" : "bg-accent"}`}
                  style={{ width: `${(n / top) * 100}%`, opacity: 0.3 }}
                />
              </span>
              <span className="figure text-ink tabular-nums text-base">{n}</span>
            </li>
          );
        })}
      </ol>
      {rows.length > max && (
        <div className="mt-4 text-left">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-[0.72rem] uppercase tracking-[0.18em] text-ink-mute hover:text-accent transition-colors underline decoration-rule-strong underline-offset-4 hover:decoration-accent cursor-pointer"
          >
            {expanded ? "Show less" : `Show all ${rows.length} words`}
          </button>
        </div>
      )}
    </section>
  );
}
