import type { Metadata } from "next";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Masthead } from "@/components/Masthead";
import { Colophon } from "@/components/Colophon";
import { SITE_URL } from "@/lib/site";

const serif = Fraunces({
  variable: "--font-serif",
  subsets: ["latin", "latin-ext"], // latin-ext for š, č, ž, đ
  axes: ["opsz", "SOFT"],
  display: "swap",
});

const sans = Inter({
  variable: "--font-sans",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

const DESCRIPTION =
  "A quarterly statistical review of popular lyrics. We count every word, " +
  "rhyme and chorus to read songs and artists as data. In Issue 01: The " +
  "Monsters of Sarajevo, on Jala Brat & Buba Corelli's album GODZILLA.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "LyricStats · lyric statistics for songs and artists",
    template: "%s · LyricStats",
  },
  description: DESCRIPTION,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    siteName: "LyricStats",
    type: "website",
    url: "/",
    title: "LyricStats · lyric statistics for songs and artists",
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
  },
  robots: {
    index: true,
    follow: true,
  },
};

// Tells Google the site's brand name and logo (site-name display, knowledge
// of the lyricstats.dev ↔ LyricStats pairing in search results).
const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "LyricStats",
      alternateName: "lyricstats.dev",
      description: DESCRIPTION,
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: "LyricStats",
      url: SITE_URL,
      logo: `${SITE_URL}/apple-icon.png`,
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${serif.variable} ${sans.variable} ${mono.variable} h-full`}
    >
      <body className="min-h-full flex flex-col paper-grain">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
        <Masthead />
        <main className="flex-1 w-full">{children}</main>
        <Colophon />
      </body>
    </html>
  );
}
