import type { Metadata } from "next";
import Link from "next/link";
import { issues, latestIssue } from "@/lib/issues";

export const metadata: Metadata = {
  title: "The issues",
  description: "The LyricStats Review, issue by issue. Essays on music, the words inside it, and the stories the numbers tell.",
  alternates: { canonical: "/issues" },
  openGraph: {
    title: "The issues · LyricStats",
    description: "Explore every edition of the LyricStats Review.",
    url: "/issues",
  },
};

function SecondLifeCover() {
  return (
    <div className="relative flex min-h-[29rem] flex-col overflow-hidden bg-accent px-7 py-6 text-paper sm:min-h-[35rem] sm:px-9 sm:py-8" aria-hidden="true">
      <div className="flex items-baseline justify-between border-b border-paper/40 pb-4">
        <span className="font-serif italic text-xl">The Review</span>
        <span className="text-[.65rem] tracking-[.2em]">NO. 02</span>
      </div>
      <p className="mt-8 text-[.6rem] uppercase tracking-[.2em] text-paper/70 sm:mt-10">The second life</p>
      <p className="display mt-4 max-w-[16rem] text-[2.6rem] leading-[1.03] sm:text-[3.3rem]">The hit that<br/>wouldn’t stay<br/>in <em>2012.</em></p>
      <div className="relative mt-auto pt-9">
        <div className="absolute right-0 top-3 flex h-16 w-16 items-center justify-center rounded-full border border-paper/40 font-serif text-4xl transition-transform duration-300 group-hover:rotate-[-25deg] motion-reduce:transition-none sm:h-20 sm:w-20" aria-hidden="true">↗</div>
        <p className="figure text-[clamp(4rem,13vw,8rem)] leading-none tracking-[-.06em] text-paper/85">20<span className="italic text-paper">26</span></p>
        <p className="mt-5 border-t border-paper/40 pt-4 text-[.6rem] uppercase tracking-[.16em] text-paper/80">A familiar song. Another summer.</p>
      </div>
    </div>
  );
}

function MonstersCover() {
  return (
    <div className="relative flex min-h-[29rem] flex-col overflow-hidden border border-rule-strong bg-paper-soft px-7 py-6 sm:min-h-[35rem] sm:px-9 sm:py-8" aria-hidden="true">
      <div className="flex items-baseline justify-between border-b border-rule-strong pb-4">
        <span className="font-serif italic text-xl">The Review</span>
        <span className="text-[.65rem] tracking-[.2em]">NO. 01</span>
      </div>
      <p className="mt-8 text-[.6rem] uppercase tracking-[.2em] text-ink-soft sm:mt-10">Jala Brat &amp; Buba Corelli</p>
      <p className="display mt-4 text-[2.6rem] leading-[1.03] sm:text-[3.3rem]">The Monsters<br/>of <em className="text-accent">Sarajevo.</em></p>
      <div className="relative mt-auto pt-10">
        <p className="figure text-[clamp(3.5rem,9vw,6rem)] leading-none tracking-[-.05em] text-accent">180,713</p>
        <div className="mt-4 flex items-center gap-3"><span className="h-px flex-1 bg-rule-strong"/><span className="font-serif italic text-xl">words inside the monster</span></div>
        <p className="mt-8 border-t border-rule-strong pt-4 text-[.6rem] uppercase tracking-[.16em] text-ink-soft">GODZILLA &amp; the catalogue behind it.</p>
      </div>
    </div>
  );
}

export default function IssuesPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pb-24 sm:pt-16">
      <header className="border-b border-rule-strong pb-8 sm:pb-10">
        <p className="smallcaps">The LyricStats Review</p>
        <div className="mt-5 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <h1 className="display text-[clamp(3.5rem,9vw,6.5rem)]">The issues<span className="text-accent">.</span></h1>
          <p className="max-w-[23rem] font-serif text-lg italic leading-relaxed text-ink-soft sm:pb-1 sm:text-xl">Music, read a little closer.<br/>Every edition, from the beginning.</p>
        </div>
      </header>

      <div className="flex items-baseline justify-between py-5 text-[.65rem] uppercase tracking-[.16em] text-ink-mute">
        <p>{issues.length} issues · 2026</p>
        <p>Newest first</p>
      </div>

      <ol className="grid grid-cols-1 gap-x-10 gap-y-12 md:grid-cols-2 lg:gap-x-16">
        {issues.map((issue) => (
          <li key={issue.id} className="min-w-0">
            <Link
              href={issue.href}
              prefetch={false}
              aria-labelledby={`issue-${issue.id}-title`}
              aria-describedby={`issue-${issue.id}-details`}
              className="group block outline-offset-8"
            >
              <div className="transition-transform duration-300 ease-out group-hover:-translate-y-1 motion-reduce:transform-none motion-reduce:transition-none">
                {issue.id === "02" ? <SecondLifeCover/> : <MonstersCover/>}
              </div>
              <div id={`issue-${issue.id}-details`} className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2 text-[.6rem] uppercase tracking-[.14em] text-ink-mute">
                <span className="text-ink">Issue {issue.id}</span>
                <span aria-hidden="true">·</span>
                <span>{issue.dateLabel}</span>
                {issue.id === latestIssue.id && <span className="ml-auto border border-accent/35 px-2 py-1 text-accent">Latest issue</span>}
              </div>
              <h2 id={`issue-${issue.id}-title`} className="display mt-4 text-3xl leading-[1.1] transition-colors group-hover:text-accent sm:text-4xl">{issue.title}</h2>
              <p className="mt-3 max-w-[28rem] font-serif text-lg leading-relaxed text-ink-soft">{issue.subtitle}</p>
              <div className="mt-6 flex items-center justify-between border-b border-rule-strong pb-4 text-[.65rem] uppercase tracking-[.16em] text-accent">
                <span>Read issue {issue.id}</span>
                <span className="text-xl transition-transform group-hover:translate-x-1 motion-reduce:transform-none" aria-hidden="true">→</span>
              </div>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
