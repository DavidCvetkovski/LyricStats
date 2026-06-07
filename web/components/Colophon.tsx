export function Colophon() {
  return (
    <footer className="mt-24 border-t border-rule-strong">
      <div className="mx-auto max-w-6xl px-6 py-10 grid gap-6 sm:grid-cols-3 text-[0.78rem] text-ink-mute">
        <div>
          <p className="smallcaps text-ink mb-2">Colophon</p>
          <p>
            Set in Fraunces &amp; Inter. Rendered in digital ink on a screen near you.
          </p>
        </div>
        <div>
          <p className="smallcaps text-ink mb-2">Method</p>
          <p>
            Counting the beats and the syllables, separating the poetry from the noise.
          </p>
        </div>
        <div>
          <p className="smallcaps text-ink mb-2">Rights</p>
          <p>
            Free to read, share, and enjoy. No part of this publication may be sold.
          </p>
        </div>
      </div>
    </footer>
  );
}
