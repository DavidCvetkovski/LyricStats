export function PullQuote({
  children,
  cite,
}: {
  children: React.ReactNode;
  cite?: string;
}) {
  return (
    <figure className="my-12 mx-auto max-w-2xl text-center">
      <span aria-hidden className="block text-accent text-5xl leading-none mb-2">“</span>
      <blockquote
        className="display text-3xl sm:text-4xl text-ink italic"
        style={{ lineHeight: 1.15 }}
      >
        {children}
      </blockquote>
      {cite ? (
        <figcaption className="smallcaps mt-5">— {cite}</figcaption>
      ) : null}
    </figure>
  );
}
