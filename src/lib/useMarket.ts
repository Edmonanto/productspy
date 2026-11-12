"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { winnersApi } from "@/lib/api";
import { recallMarket, rememberMarket } from "@/lib/utils";

/** Selected market: ?market= in the URL, else last used, else first followed. */
export function useMarket() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const meta = useSWR("winner-markets", winnersApi.markets);

  const following = useMemo(() => meta.data?.following ?? [], [meta.data]);
  const fromUrl = params.get("market")?.toUpperCase() ?? null;
  // Switch the moment a market is clicked, not when the URL update lands —
  // otherwise the button feels dead for a beat.
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => { if (pending && fromUrl === pending) setPending(null); }, [fromUrl, pending]);

  const market = useMemo(() => {
    if (pending) return pending;
    if (fromUrl) return fromUrl;
    const last = recallMarket();
    if (last && following.includes(last)) return last;
    return following[0] ?? null;
  }, [pending, fromUrl, following]);

  useEffect(() => {
    if (market) rememberMarket(market);
  }, [market]);

  const setMarket = useCallback(
    (code: string) => {
      setPending(code);
      rememberMarket(code);
      const q = new URLSearchParams(params.toString());
      q.set("market", code);
      q.delete("date");
      router.replace(`${pathname}?${q.toString()}`);
    },
    [params, pathname, router]
  );

  return { market, setMarket, meta };
}
