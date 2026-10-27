"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bookmark, Columns3, LayoutDashboard, Trophy, Receipt,
  CreditCard, Settings, Zap, LogOut, X
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useEffect, useState } from "react";

/** The Topbar's menu button dispatches this to open the mobile drawer. */
export const OPEN_SIDEBAR_EVENT = "productspy:open-sidebar";

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Overview" },
  { href: "/dashboard/winners", icon: Trophy, label: "Daily Winners" },
  { href: "/dashboard/watchlist", icon: Bookmark, label: "Watchlist" },
  { href: "/dashboard/compare", icon: Columns3, label: "Compare" },
  { href: "/dashboard/quotes", icon: Receipt, label: "Quotes" },
];

const BOTTOM_ITEMS = [
  { href: "/dashboard/billing", icon: CreditCard, label: "Billing" },
  { href: "/dashboard/settings", icon: Settings, label: "Settings" },
];

function SidebarContent({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const { signOut } = useAuth();

  return (
    <aside className="flex flex-col w-60 h-full bg-zinc-900 border-r border-zinc-800 px-3 py-5">
      {/* Logo */}
      <div className="flex items-center gap-2 px-3 mb-8">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-900/40">
          <Zap size={16} className="text-white" />
        </div>
        <span className="font-bold text-white text-lg tracking-tight">ProductSpy</span>
        <span className="text-[10px] text-violet-400 font-semibold bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 rounded ml-auto">PRO</span>
        {onClose && (
          <button onClick={onClose} aria-label="Close menu" className="text-zinc-500 hover:text-white ml-1 p-2 -mr-2">
            <X size={16} />
          </button>
        )}
      </div>

      {/* Main nav */}
      <nav className="flex-1 space-y-0.5">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            onClick={onClose}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
              // Nested pages (/dashboard/winners/[id]) keep their section lit.
              (href === "/dashboard" ? pathname === href : pathname.startsWith(href))
                ? "bg-violet-600/20 text-violet-400 border border-violet-600/30 shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="space-y-0.5 border-t border-zinc-800 pt-4 mt-4">
        {BOTTOM_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            onClick={onClose}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
              pathname === href
                ? "bg-violet-600/20 text-violet-400"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
        <button
          onClick={signOut}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-red-400 hover:bg-zinc-800 w-full transition-all"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const open = () => setMobileOpen(true);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setMobileOpen(false);
    window.addEventListener(OPEN_SIDEBAR_EVENT, open);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener(OPEN_SIDEBAR_EVENT, open);
      window.removeEventListener("keydown", esc);
    };
  }, []);

  // Close the drawer after navigating, and stop the page scrolling behind it.
  useEffect(() => setMobileOpen(false), [pathname]);
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div className={cn(
        "lg:hidden fixed inset-y-0 left-0 z-50 transition-[transform,visibility] duration-300 max-w-[85vw]",
        mobileOpen ? "translate-x-0 visible" : "-translate-x-full invisible"
      )} role="dialog" aria-modal={mobileOpen} aria-label="Menu">
        <SidebarContent onClose={() => setMobileOpen(false)} />
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex min-h-screen sticky top-0 h-screen">
        <SidebarContent />
      </div>
    </>
  );
}
