"use client";

import Link from "next/link";

export default function Footer({ lastUpdated, totalEvents }: { lastUpdated?: string; totalEvents?: number }) {
  const updated = lastUpdated
    ? new Date(lastUpdated).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <footer className="mt-16 border-t border-[#d8d0c1] bg-[#fffdf8]">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-3">
          <div>
            <h3 className="font-editorial text-lg font-bold text-[#173c35]">NYC Events</h3>
            <p className="mt-2 max-w-[280px] text-sm leading-5 text-[#66716c]">
              A curated, continuously-updated guide to the best of NYC — built to replace Instagram scrolling.
              {totalEvents ? ` ${totalEvents} events from across the city.` : ""}
            </p>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">Explore</h4>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link href="/" className="text-[#52645e] hover:text-[#173c35] hover:underline">Calendar — choose a date</Link></li>
              <li><Link href="/communities" className="text-[#52645e] hover:text-[#173c35] hover:underline">Communities you can join</Link></li>
              <li><Link href="/events" className="text-[#52645e] hover:text-[#173c35] hover:underline">Browse every event</Link></li>
              <li><Link href="/saved" className="text-[#52645e] hover:text-[#173c35] hover:underline">Your saved</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">About the guide</h4>
            <ul className="mt-3 space-y-1.5 text-xs leading-5 text-[#66716c]">
              <li>Sources: Instagram, Luma, Eventbrite, Substack, The Skint, Dice, museums & more</li>
              <li>Ranking: cross-source verification, your follow graph, social & proximity signals</li>
              <li>Personalization: 100% localStorage — private to your browser</li>
              {updated && <li>Last scrape: {updated}</li>}
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-[#e8e2d2] pt-6 text-xs text-[#8b918e]">
          <span>Built for Williamsburg, works across NYC. Open-source on GitHub.</span>
          <a
            href="https://github.com/prajjwal1/nyc"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-[#52645e] hover:text-[#173c35]"
          >
            github.com/prajjwal1/nyc ↗
          </a>
        </div>
      </div>
    </footer>
  );
}
