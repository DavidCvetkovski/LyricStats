import Link from "next/link";

export function Masthead() {
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <header className="border-b border-rule-strong">
      <div className="mx-auto max-w-6xl px-6 pt-7 pb-7">
        <div className="grid items-end gap-y-6 sm:gap-y-4 sm:grid-cols-[1fr_auto_1fr]">
          {/* Left rail — meta */}
          <div className="hidden sm:flex flex-col text-[0.7rem] uppercase tracking-[0.18em] text-ink-mute leading-relaxed self-end">
            <span className="text-ink">Vol. I · No. 1</span>
            <span>{today}</span>
            <span className="italic normal-case tracking-normal text-[0.78rem] text-ink-soft mt-1 font-serif">
              A statistical review of popular lyrics
            </span>
          </div>

          {/* Wordmark */}
          <Link
            href="/"
            className="block text-center justify-self-center"
            aria-label="LyricStats — home"
          >
            <h1
              className="display text-ink leading-[0.88]"
              style={{
                fontSize: "clamp(3.25rem, 9vw, 6.5rem)",
                fontVariationSettings: '"opsz" 144, "SOFT" 50',
              }}
            >
              LyricStats
            </h1>
          </Link>

          {/* Right rail — nav */}
          <nav className="hidden sm:flex flex-col items-end gap-1 text-[0.72rem] uppercase tracking-[0.16em] self-end">
            <Link href="/" className="hover:text-accent transition-colors">
              Front Page
            </Link>
            <Link href="/song" className="hover:text-accent transition-colors">
              On a Song
            </Link>
            <Link href="/artist" className="hover:text-accent transition-colors">
              The Artist
            </Link>
            <span className="text-ink-mute text-[0.65rem] mt-1 normal-case tracking-normal italic font-serif">
              Established 2026
            </span>
          </nav>
        </div>

        {/* Mobile fallback — single small-caps row under the title */}
        <div className="sm:hidden mt-5 flex items-center justify-between text-[0.65rem] uppercase tracking-[0.16em] text-ink-mute">
          <span>{today}</span>
          <nav className="flex gap-3 text-ink">
            <Link href="/" className="hover:text-accent">Front</Link>
            <Link href="/song" className="hover:text-accent">Song</Link>
            <Link href="/artist" className="hover:text-accent">Artist</Link>
          </nav>
        </div>
      </div>

      {/* Double rule under masthead, like a broadsheet */}
      <div className="h-[3px] border-y border-rule-strong bg-paper"></div>
    </header>
  );
}
