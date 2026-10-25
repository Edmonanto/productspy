"use client";

import useSWR from "swr";
import { usersApi, Me } from "@/lib/api";

export default function Topbar({ title }: { title: string }) {
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const initial = (me?.name ?? me?.email ?? "U")[0].toUpperCase();

  return (
    // pl-16 on mobile clears the fixed hamburger button the Sidebar renders
    // at top-4 left-4, which otherwise sits on top of the title.
    <header className="h-14 flex items-center justify-between gap-3 pl-16 pr-4 md:px-6 border-b border-zinc-800 bg-zinc-950">
      <h1 className="text-white font-semibold text-base truncate">{title}</h1>

      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
          {initial}
        </div>
      </div>
    </header>
  );
}
