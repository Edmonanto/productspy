"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { usersApi, Me } from "@/lib/api";

export default function Topbar({ title }: { title: string }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const { data: me } = useSWR<Me>("me", usersApi.me);
  const initial = (me?.name ?? me?.email ?? "U")[0].toUpperCase();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) router.push(`/dashboard/search?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    // pl-16 on mobile clears the fixed hamburger button the Sidebar renders
    // at top-4 left-4, which otherwise sits on top of the title.
    <header className="h-14 flex items-center justify-between gap-3 pl-16 pr-4 md:px-6 border-b border-zinc-800 bg-zinc-950">
      <h1 className="text-white font-semibold text-base truncate">{title}</h1>

      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* Quick search — hidden on the narrowest screens, where the header
            cannot fit it. The sidebar's Search entry still reaches the page. */}
        <form onSubmit={handleSearch} className="relative hidden sm:block">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Quick search..."
            aria-label="Quick search"
            className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg pl-8 pr-3 py-1.5 w-36 lg:w-48 focus:outline-none focus:border-violet-500 placeholder-zinc-600"
          />
        </form>

        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
          {initial}
        </div>
      </div>
    </header>
  );
}
