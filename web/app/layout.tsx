import type { Metadata } from "next";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Masthead } from "@/components/Masthead";
import { Colophon } from "@/components/Colophon";

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

export const metadata: Metadata = {
  title: "LyricStats — a quarterly of words",
  description: "Stats for lyrics, per song and per artist.",
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
        <Masthead />
        <main className="flex-1 w-full">{children}</main>
        <Colophon />
      </body>
    </html>
  );
}
