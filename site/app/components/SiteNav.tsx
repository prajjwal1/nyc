"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: Array<[string, string]> = [
  ["/", "Feed"],
  ["/events", "All events"],
  ["/communities", "Communities"],
  ["/saved", "Saved"],
];

export default function SiteNav() {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#f8f3e8]/90 backdrop-blur supports-[backdrop-filter]:bg-[#f8f3e8]/80">
      <div className="mx-auto flex max-w-5xl items-center gap-5 px-4 py-2.5 sm:px-6 sm:py-3">
        <Link href="/" className="mr-auto font-editorial text-[18px] font-bold tracking-tight text-[#173c35]">
          NYC Events
        </Link>
        <div className="flex items-center gap-1 overflow-x-auto">
          {links.map(([href, label]) => {
            const active = path === href || (href !== "/" && path.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 rounded-full px-3 py-1.5 text-[13px] font-medium transition ${
                  active ? "bg-[#173c35] text-white" : "text-[#52645e] hover:bg-white hover:text-[#173c35]"
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
