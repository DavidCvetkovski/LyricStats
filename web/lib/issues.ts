export type Issue = {
  id: "02" | "01";
  title: string;
  subtitle: string;
  dateLabel: string;
  href: string;
};

/** Newest first; shared by the issue shelf and the publication navigation. */
export const issues: readonly Issue[] = [
  {
    id: "02",
    title: "The hit that wouldn’t stay in 2012",
    subtitle: "Beauty and a Beat, pop’s second lives, and the songs that find another summer.",
    dateLabel: "14 September 2026",
    href: "/issues/02",
  },
  {
    id: "01",
    title: "The Monsters of Sarajevo",
    subtitle: "Jala Brat, Buba Corelli, and the dictionary inside GODZILLA.",
    dateLabel: "9 June 2026",
    href: "/issues/01",
  },
];

export const latestIssue = issues[0];
