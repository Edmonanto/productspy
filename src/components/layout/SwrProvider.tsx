"use client";

import { useMemo } from "react";
import { SWRConfig, type Cache } from "swr";
import { useAuth } from "@/context/AuthContext";

/** Keys worth remembering between visits: they change at most a few times a day. */
const PERSIST = /winners|winner-|evidence|watchlist|report/;
const MAX_BYTES = 1_500_000;
const PREFIX = "ps.swr.";

export function clearSwrStorage() {
  try {
    Object.keys(localStorage).filter((k) => k.startsWith(PREFIX)).forEach((k) => localStorage.removeItem(k));
  } catch { /* storage blocked */ }
}

/** SWR cache that survives reloads, per user: the dashboard paints instantly from the
 *  last visit, then refreshes in the background. */
function persistentCache(userId: string): () => Cache {
  return () => {
    const key = PREFIX + userId;
    const map = new Map<string, unknown>();
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "[]") as [string, unknown][];
      for (const [k, data] of saved) map.set(k, { data });
    } catch { /* ignore */ }
    const save = () => {
      try {
        const rows: [string, unknown][] = [];
        map.forEach((v, k) => {
          const data = (v as { data?: unknown })?.data;
          if (data !== undefined && PERSIST.test(k)) rows.push([k, data]);
        });
        const json = JSON.stringify(rows);
        if (json.length < MAX_BYTES) localStorage.setItem(key, json);
      } catch { /* quota or blocked */ }
    };
    window.addEventListener("beforeunload", save);
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") save(); });
    return map as Cache;
  };
}

export default function SwrProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const provider = useMemo(() => (user ? persistentCache(user.id) : undefined), [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <SWRConfig key={user?.id ?? "anon"} value={{
      ...(provider ? { provider } : {}),
      revalidateOnFocus: false,     // picks change daily; don't refetch on every tab switch
      dedupingInterval: 60_000,
      keepPreviousData: true,       // switching market keeps the old grid until the new one lands
      errorRetryCount: 3,
    }}>
      {children}
    </SWRConfig>
  );
}
