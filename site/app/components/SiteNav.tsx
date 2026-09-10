import Link from "next/link";

export default function SiteNav() {
  return (
    <nav aria-label="Primary" className="sticky top-0 z-40 border-b border-[#dedbd3]/90 bg-[#f8f7f3]/88 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] max-w-6xl items-center px-4 sm:px-6">
        <Link href="/" aria-label="NYC Events home" className="group inline-flex items-center gap-2.5 text-[#173c35]">
          <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#173c35] shadow-[0_5px_14px_rgba(23,60,53,0.16)] transition-transform duration-300 group-hover:-translate-y-0.5" aria-hidden="true">
            <svg viewBox="0 0 32 32" className="h-5 w-5" fill="none">
              <path d="M8.5 14.5h15M11 9v5M21 9v5M9.5 11.5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-10a2 2 0 0 1 2-2Z" stroke="#F7F4EC" strokeWidth="1.8" strokeLinecap="round"/>
              <circle cx="19.8" cy="20.2" r="2.2" fill="#D47A56"/>
            </svg>
          </span>
          <span className="text-[15px] font-semibold tracking-[-0.025em] sm:text-[16px]">NYC Events</span>
        </Link>
      </div>
    </nav>
  );
}
