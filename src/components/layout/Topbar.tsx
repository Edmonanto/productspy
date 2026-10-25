"use client";

import Link from "next/link";
import useSWR from "swr";
import { Menu } from "lucide-react";
import { usersApi, Me } from "@/lib/api";
import { OPEN_SIDEBAR_EVENT } from "./Sidebar";

export default function Topbar({ title }: { title: string }) {
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const initial = (me?.name ?? me?.email ?? "U")[0].toUpperCase();

  return (
    // Sticky on phones so the menu is always one tap away.
    <header className="sticky top-0 z-30 h-14 flex items-center justify-between gap-3 px-2 md:px-4 lg:px-6 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
      <div className="flex items-center gap-1 min-w-0">
        <button
          onClick={() => window.dispatchEvent(new Event(OPEN_SIDEBAR_EVENT))}
          aria-label="Open menu"
          className="lg:hidden p-2.5 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-800"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-white font-semibold text-base truncate pl-1 lg:pl-0">{title}</h1>
      </div>

      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* Avatar */}
        <Link href="/dashboard/settings" aria-label="Account settings"
              className="w-11 h-11 flex items-center justify-center rounded-full -mr-1">
          <span className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
            {initial}
          </span>
        </Link>
      </div>
    </header>
  );
}
