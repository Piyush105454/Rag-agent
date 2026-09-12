/**
 * app/layout.tsx
 *
 * Root layout for the RAG Knowledge Assistant.
 * Applies dark class to html element so Tailwind dark mode is always active.
 * Loads Inter font via next/font for optimised font delivery.
 * Sets global metadata for SEO and browser tab title.
 */

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Company Knowledge Assistant",
  description:
    "AI-powered retrieval assistant for company documents. Ask questions, get cited answers.",
  robots: { index: false, follow: false }, // Internal tool — no indexing
};

export const viewport: Viewport = {
  themeColor: "#0a0f1a",
  colorScheme: "dark",
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={`dark ${inter.variable}`} suppressHydrationWarning>
      <body className="min-h-screen bg-slate-950 font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
