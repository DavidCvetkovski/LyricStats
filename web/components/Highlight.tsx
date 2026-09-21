/** The typed text, where it occurs in a suggestion, set in medium weight. */
export function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  if (!q) return <>{text}</>;
  const at = text.toLowerCase().indexOf(q.toLowerCase());
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <b className="font-semibold">{text.slice(at, at + q.length)}</b>
      {text.slice(at + q.length)}
    </>
  );
}
