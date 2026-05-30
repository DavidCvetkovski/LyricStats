import { ReactNode } from "react";

type Props = {
  label: string;
  value: ReactNode;
  caption?: string;
  size?: "sm" | "md" | "lg";
};

export function StatFigure({ label, value, caption, size = "md" }: Props) {
  // Fluid sizes that scale from phone to desktop without overflow.
  // The browser picks the clamp middle term based on viewport width.
  const fontSize = {
    sm: "clamp(2rem, 7vw, 3rem)",
    md: "clamp(2.25rem, 8vw, 3.75rem)",
    lg: "clamp(2.5rem, 9vw, 4.5rem)",
  }[size];

  return (
    <div className="border-b border-rule pb-4 sm:pb-5 min-w-0">
      <div className="smallcaps mb-1.5 sm:mb-2">{label}</div>
      <div
        className="figure text-ink truncate"
        style={{ fontSize, lineHeight: 1 }}
      >
        {value}
      </div>
      {caption ? (
        <div className="mt-1 text-[0.7rem] sm:text-[0.78rem] italic text-ink-mute">
          {caption}
        </div>
      ) : null}
    </div>
  );
}
