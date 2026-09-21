"use client";

import Link from "next/link";

export default function SongError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-20">
      <p className="smallcaps">
        <Link href="/song" className="hover:text-accent transition-colors">
          Section II — On a Song
        </Link>
      </p>
      <section role="alert" className="mt-12 mx-auto max-w-2xl border-l-2 border-accent pl-5 sm:pl-6">
        <p className="smallcaps text-accent mb-2">A small interruption</p>
        <h1 className="display text-3xl sm:text-4xl text-ink leading-tight">Something didn’t go through.</h1>
        <p className="mt-3 font-serif text-lg italic text-ink-soft">
          We had trouble fetching this one. The lyric service may be busy.
        </p>
        <button type="button" onClick={reset} className="pill mt-6">
          Try again
        </button>
      </section>
    </div>
  );
}
