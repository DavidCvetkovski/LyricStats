/**
 * The song as a row of lines, first to last. Each mark's height is the line's
 * word count; the marks in oxblood are the line that comes back most.
 */
export function HookStrip({ lineWords, hookAt }: { lineWords: number[]; hookAt: number[] }) {
  const max = Math.max(1, ...lineWords);
  const hooks = new Set(hookAt);
  return (
    <figure>
      <div
        className="song-strip"
        role="img"
        aria-label={`${lineWords.length} lines in order; ${hooks.size} of them are the returning line`}
      >
        {lineWords.map((words, i) => (
          <span
            key={i}
            className={hooks.has(i) ? "is-hook" : undefined}
            style={{ height: `${Math.max(6, (words / max) * 100)}%` }}
            title={`Line ${i + 1}: ${words} ${words === 1 ? "word" : "words"}`}
          />
        ))}
      </div>
      <figcaption className="mt-3 flex justify-between smallcaps">
        <span>First line</span>
        <span>{lineWords.length} lines, each mark as tall as its word count</span>
        <span>Last line</span>
      </figcaption>
    </figure>
  );
}
