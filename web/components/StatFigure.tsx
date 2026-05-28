import { ReactNode } from "react";

type Props = {
  label: string;
  value: ReactNode;
  caption?: string;
  size?: "sm" | "md" | "lg";
};

export function StatFigure({ label, value, caption, size = "md" }: Props) {
  const sizeClass = {
    sm: "text-4xl sm:text-5xl",
    md: "text-5xl sm:text-6xl",
    lg: "text-6xl sm:text-7xl",
  }[size];

  return (
    <div className="border-b border-rule pb-5">
      <div className="smallcaps mb-2">{label}</div>
      <div className={`figure ${sizeClass} text-ink`}>{value}</div>
      {caption ? (
        <div className="mt-1 text-[0.78rem] italic text-ink-mute">{caption}</div>
      ) : null}
    </div>
  );
}
