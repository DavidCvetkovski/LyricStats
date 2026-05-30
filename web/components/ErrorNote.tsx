import type { FriendlyError } from "@/lib/errors";

/**
 * Editorial error block — italic headline, hairline rule, oxblood detail,
 * small-caps suggestion. Calm and explanatory, not alarming.
 */
export function ErrorNote({
  err,
  onRetry,
}: {
  err: FriendlyError;
  onRetry?: () => void;
}) {
  return (
    <section
      role="alert"
      className="mt-12 mx-auto max-w-2xl border-l-2 border-accent pl-5 sm:pl-6"
    >
      <p className="smallcaps text-accent mb-2">A small interruption</p>
      <h3 className="display text-3xl sm:text-4xl text-ink leading-tight">
        {err.headline}
      </h3>
      <p className="mt-3 font-serif text-lg italic text-ink-soft">{err.detail}</p>
      {err.suggestion && (
        <p className="mt-3 text-[0.85rem] text-ink-mute">{err.suggestion}</p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 text-[0.72rem] uppercase tracking-[0.18em] text-ink hover:text-accent transition-colors underline decoration-rule-strong underline-offset-4 hover:decoration-accent"
        >
          Try again
        </button>
      )}
    </section>
  );
}
