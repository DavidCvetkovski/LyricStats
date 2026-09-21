import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-20">
      <p className="smallcaps">
        <Link href="/song" className="hover:text-accent transition-colors">
          Section II — On a Song
        </Link>
      </p>
      <section className="mt-12 mx-auto max-w-2xl border-l-2 border-accent pl-5 sm:pl-6">
        <p className="smallcaps text-accent mb-2">Not in the archive</p>
        <h1 className="display text-3xl sm:text-4xl text-ink leading-tight">We couldn’t find that song.</h1>
        <p className="mt-3 font-serif text-lg italic text-ink-soft">
          None of our sources has its words under this artist and title. It may be filed under
          another spelling, or without the “feat.”.
        </p>
        <Link href="/song" className="pill mt-6">
          Search again →
        </Link>
      </section>
    </div>
  );
}
