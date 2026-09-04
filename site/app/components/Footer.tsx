"use client";

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-[#d8d0c1] bg-[#fffdf8]">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2">
          <div>
            <h3 className="font-editorial text-lg font-bold text-[#173c35]">NYC Events</h3>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">Explore</h4>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link href="/" className="text-[#52645e] hover:text-[#173c35] hover:underline">Calendar — choose a date</Link></li>
              <li><Link href="/events" className="text-[#52645e] hover:text-[#173c35] hover:underline">Browse every event</Link></li>
              <li><Link href="/categories/music" className="text-[#52645e] hover:text-[#173c35] hover:underline">Live music in NYC</Link></li>
              <li><Link href="/categories/free" className="text-[#52645e] hover:text-[#173c35] hover:underline">Free things to do</Link></li>
              <li><Link href="/saved" className="text-[#52645e] hover:text-[#173c35] hover:underline">Your saved</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex justify-end border-t border-[#e8e2d2] pt-6 text-xs">
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
