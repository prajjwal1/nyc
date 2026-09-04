"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: Array<[string, string]> = [
  ["/", "Calendar"],
];

export default function SiteNav() {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#fffdf8]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-2 px-3 sm:gap-4 sm:px-6">
        <Link href="/" aria-label="NYC Events home" className="mr-auto shrink-0 font-editorial text-[17px] font-bold tracking-tight text-[#173c35] sm:text-[18px]">
          <span className="sm:hidden">NYC</span>
          <span className="hidden sm:inline">NYC Events</span>
        </Link>
        <div className="flex min-w-0 items-center gap-3 sm:gap-6">
          {links.map(([href, label]) => {
            const active = path === href || (href !== "/" && path.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 border-b-2 py-3 text-[12px] font-medium transition-colors sm:text-[13px] ${
                  active ? "border-[#173c35] text-[#173c35]" : "border-transparent text-[#66716c] hover:text-[#173c35]"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
