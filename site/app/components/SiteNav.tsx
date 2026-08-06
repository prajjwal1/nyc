"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
const links = [["/", "Home"], ["/events", "Events"], ["/communities", "Communities"], ["/map", "Map"], ["/saved", "Saved"]];
export default function SiteNav() {
  const path = usePathname();
  return <nav className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#f8f3e8]/95 backdrop-blur" aria-label="Primary">
    <div className="mx-auto max-w-7xl px-4 py-2.5 sm:flex sm:items-center sm:gap-5 sm:px-6 sm:py-3">
      <Link href="/" className="block font-serif text-xl font-bold tracking-tight text-[#173c35] sm:mr-auto">City Kin</Link>
      <div className="-mx-1 mt-2 flex items-center gap-5 overflow-x-auto px-1 pb-0.5 sm:mx-0 sm:mt-0 sm:overflow-visible sm:px-0 sm:pb-0">
        {links.map(([href,label]) => <Link key={href} href={href} className={`shrink-0 text-sm font-medium ${path === href || (href !== "/" && path.startsWith(href)) ? "text-[#bd4f34]" : "text-[#52645e] hover:text-[#173c35]"}`}>{label}</Link>)}
      </div>
    </div>
  </nav>;
}
