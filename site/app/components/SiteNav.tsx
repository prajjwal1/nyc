"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
const links = [["/", "Home"], ["/events", "Events"], ["/communities", "Communities"], ["/map", "Map"], ["/saved", "Saved"]];
export default function SiteNav() {
  const path = usePathname();
  return <nav className="sticky top-0 z-40 border-b border-[#d8d0c1] bg-[#f8f3e8]/95 backdrop-blur" aria-label="Primary">
    <div className="mx-auto flex max-w-7xl items-center gap-5 px-4 py-3 sm:px-6">
      <Link href="/" className="mr-auto font-serif text-xl font-bold tracking-tight text-[#173c35]">City Kin</Link>
      {links.map(([href,label]) => <Link key={href} href={href} className={`text-sm font-medium ${path === href || (href !== "/" && path.startsWith(href)) ? "text-[#bd4f34]" : "text-[#52645e] hover:text-[#173c35]"}`}>{label}</Link>)}
    </div>
  </nav>;
}
