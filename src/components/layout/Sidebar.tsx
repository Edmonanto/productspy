"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  TrendingUp, Bookmark, Search, LayoutDashboard,
  CreditCard, Settings, Zap, LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Overview" },
  { href: "/dashboard/trending", icon: TrendingUp, label: "Trending" },
  { href: "/dashboard/search", icon: Search, label: "Search" },
  { href: "/dashboard/watchlist", icon: Bookmark, label: "Watchlist" },
];

const BOTTOM_ITEMS = [
  { href: "/dashboard/billing", icon: CreditCard, label: "Billing" },
  { href: "/dashboard/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { signOut } = useAuth();

  return (
    <aside className="flex flex-col w-60 min-h-screen bg-zinc-900 border-r border-zinc-800 px-3 py-5">
      {/* Logo */}
      <div className="flex items-center gap-2 px-3 mb-8">
        <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center">
          <Zap size={16} className="text-white" />
        </div>
        <span className="font-bold text-white text-lg tracking-tight">ProductSpy</span>
        <span className="text-[10px] text-violet-400 font-semibold bg-violet-500/10 px-1.5 py-0.5 rounded ml-auto">AI</span>
      </div>

      {/* Main nav */}
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
              pathname === href
                ? "bg-violet-600/20 text-violet-400 border border-violet-600/30"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="space-y-1 border-t border-zinc-800 pt-4 mt-4">
        {BOTTOM_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
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
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-red-400 hover:bg-zinc-800 w-full transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
