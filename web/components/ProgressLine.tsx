type Props = {
  done: number;
  total: number;
  current?: string;
  label?: string; // e.g. "Filing"
};

/**
 * Editorial progress indicator:
 *  - serif label ("Filing")  ........  small-caps count "07 / 20"
 *  - hairline track underneath, oxblood overlay grows left-to-right
 *  - italic caption with the current song title
 *
 * Calm, no spinner. Pulses subtly when active.
 */
export function ProgressLine({ done, total, current, label = "Working" }: Props) {
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div className="mt-10 max-w-2xl mx-auto">
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-serif text-xl italic text-ink">{label}…</span>
        <span className="smallcaps tabular-nums text-ink-mute">
          {String(done).padStart(2, "0")}
          <span className="mx-1 text-rule-strong">/</span>
          {String(total).padStart(2, "0")}
        </span>
      </div>

      <div
        className="relative mt-3 h-px bg-rule-strong overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
      >
        <div
          className="absolute inset-y-0 left-0 bg-accent"
          style={{
            width: `${pct}%`,
            transition: "width 0.35s cubic-bezier(.4, 0, .2, 1)",
            height: "2px",
            top: "-0.5px",
          }}
        />
      </div>

      <p
        className="mt-3 text-[0.78rem] italic text-ink-mute truncate"
        style={{
          // subtle breathing pulse — quiet, paper-aware
          animation: "fadePulse 2.4s ease-in-out infinite",
        }}
      >
        {current ? `“${current}”` : "—"}
      </p>

      <style>{`
        @keyframes fadePulse {
          0%, 100% { opacity: 0.55; }
          50%      { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
