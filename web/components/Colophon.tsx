export function Colophon() {
  return (
    <footer className="mt-24 border-t border-rule-strong">
      <div className="mx-auto max-w-6xl px-6 py-10 grid gap-6 sm:grid-cols-3 text-[0.78rem] text-ink-mute">
        <div>
          <p className="smallcaps text-ink mb-2">Colophon</p>
          <p>
            Set in Fraunces &amp; Inter. Printed digitally on a paper of
            warm linen.
          </p>
        </div>
        <div>
          <p className="smallcaps text-ink mb-2">Method</p>
          <p>
            Lyrics retrieved via Genius. Statistics computed in Python and
            served fresh.
          </p>
        </div>
        <div>
          <p className="smallcaps text-ink mb-2">Reading</p>
          <p>
            Source-available under <span className="italic">PolyForm Noncommercial</span>.
            No part may be sold without express permission.
          </p>
        </div>
      </div>
    </footer>
  );
}
