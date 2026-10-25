"use client";

import { useCallback, useEffect, useMemo } from "react";
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

  const following = meta.data?.following ?? [];
  const fromUrl = params.get("market")?.toUpperCase() ?? null;

  const market = useMemo(() => {
    if (fromUrl) return fromUrl;
    const last = recallMarket();
    if (last && following.includes(last)) return last;
    return following[0] ?? null;
  }, [fromUrl, following]);

  useEffect(() => {
    if (market) rememberMarket(market);
  }, [market]);

  const setMarket = useCallback(
    (code: string) => {
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
