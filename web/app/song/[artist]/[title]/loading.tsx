export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8 sm:pt-10 pb-20" aria-busy="true">
      <p className="smallcaps">Section II — On a Song</p>
      <div className="mt-10 sm:mt-14 text-center border-b border-rule-strong pb-12">
        <p className="smallcaps text-accent mb-5">A close reading</p>
        <p className="font-serif italic text-xl sm:text-2xl text-ink-soft">
          Fetching the words and setting the type…
        </p>
        <div className="song-loading mx-auto mt-8" />
      </div>
    </div>
  );
}
