const HEADER = /^\[[^\]]+\]$/;

/**
 * The text, folded away until asked for. Lines are numbered the way the
 * reading counts them (blank lines and [section] headers set aside), so the
 * returning line can be marked in the same oxblood as on the strip.
 */
export function Lyrics({ lyrics, hookAt, lines }: { lyrics: string; hookAt: number[]; lines: number }) {
  const hooks = new Set(hookAt);
  let index = 0;
  const rows = lyrics
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((raw, k) => {
      const line = raw.trim();
      if (!line) return <div key={k} className="h-5" aria-hidden />;
      if (HEADER.test(line)) {
        return (
          <div key={k} className="smallcaps text-accent mt-6 mb-2">
            {line.slice(1, -1)}
          </div>
        );
      }
      const i = index++;
      return (
        <div key={k} className={hooks.has(i) ? "song-hook-line" : undefined}>
          {line}
        </div>
      );
    });

  return (
    <details className="song-text">
      <summary className="smallcaps cursor-pointer select-none">
        Read the whole text · {lines} lines
      </summary>
      <div translate="no" className="mx-auto mt-8 max-w-3xl font-serif text-lg leading-[1.7] text-ink-soft break-words">
        {rows}
      </div>
    </details>
  );
}
