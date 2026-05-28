type Entry = [string, number];

export function WordTable({
  title,
  rows,
  max = 15,
}: {
  title: string;
  rows: Entry[];
  max?: number;
}) {
  const visible = rows.slice(0, max);
  const top = visible[0]?.[1] ?? 1;

  return (
    <section>
      <header className="mb-4 flex items-baseline justify-between">
        <h3 className="display text-2xl sm:text-3xl">{title}</h3>
        <span className="smallcaps">{visible.length} words</span>
      </header>
      <ol className="border-t border-rule-strong">
        {visible.map(([word, n], i) => (
          <li
            key={word}
            className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 border-b border-rule py-2"
          >
            <span className="figure text-ink-mute text-base tabular-nums">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="relative">
              <span
                className="font-serif text-xl text-ink"
                style={{ fontFamily: "var(--font-serif), Georgia, serif" }}
              >
                {word}
              </span>
              <span
                aria-hidden
                className="block absolute -bottom-0.5 left-0 h-px bg-accent"
                style={{ width: `${(n / top) * 100}%`, opacity: 0.3 }}
              />
            </span>
            <span className="figure text-ink tabular-nums text-base">{n}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
