"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: Array<[string, string]> = [
  ["/", "Feed"],
  ["/events", "Events"],
  ["/communities", "Communities"],
  ["/saved", "Saved"],
];

export default function SiteNav() {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#fffdf8]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="mr-auto font-editorial text-[18px] font-bold tracking-tight text-[#173c35]">
          NYC Events
        </Link>
        <div className="flex items-center gap-4 overflow-x-auto sm:gap-6">
          {links.map(([href, label]) => {
            const active = path === href || (href !== "/" && path.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 border-b-2 py-3 text-[13px] font-medium transition-colors ${
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
