import Link from "next/link";

export default function SiteNav() {
  return (
    <nav aria-label="Primary" className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#fffdf8]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-2 px-3 sm:gap-4 sm:px-6">
        <Link href="/" aria-label="NYC Events home" className="shrink-0 py-3 font-editorial text-[17px] font-bold tracking-tight text-[#173c35] sm:text-[18px]">
          <span className="sm:hidden">NYC</span>
          <span className="hidden sm:inline">NYC Events</span>
        </Link>
      </div>
    </nav>
  );
}
