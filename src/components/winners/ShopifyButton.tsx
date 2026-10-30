"use client";

import { useState } from "react";
import { Check, ShoppingBag } from "lucide-react";
import { winnersApi } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * "Add to Shopify": downloads the product as a Shopify import file (draft
 * product: title, description, price, cost, photo), then shows where to
 * upload it. A direct store connection can replace this later.
 */
export default function ShopifyButton({ productId, variant = "card" }: { productId: string; variant?: "card" | "page" }) {
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");

  async function go() {
    setState("busy");
    try {
      await winnersApi.shopifyCsv(productId);
      setState("done");
    } catch {
      setState("error");
    }
  }

  const page = variant === "page";
  return (
    <span className="relative inline-flex">
      <button onClick={go} disabled={state === "busy"}
              title="Download a Shopify import file for this product (added as a draft)"
              className={cn(page
                ? "flex items-center gap-1.5 text-xs rounded-lg px-3 py-2 min-h-[40px] border text-emerald-300 border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20"
                : "flex items-center gap-1 px-2.5 py-2 md:py-1.5 max-md:min-h-[44px] rounded-md text-emerald-300 hover:text-emerald-200 hover:bg-emerald-500/10",
                state === "busy" && "opacity-60")}>
        {state === "done" ? <Check size={page ? 13 : 12} /> : <ShoppingBag size={page ? 13 : 12} />}
        {state === "busy" ? "Preparing…" : state === "done" ? "File downloaded" : "Add to Shopify"}
      </button>
      {(state === "done" || state === "error") && (
        <span role="status"
              className="absolute z-20 top-full mt-2 left-0 w-72 rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-xs text-zinc-300 shadow-xl">
          {state === "error" ? "Couldn't prepare the file. Try again in a moment." : (
            <>
              <b className="text-white">Last step in Shopify:</b> Products → <b>Import</b> → upload the file you just
              downloaded. It arrives as a <b>draft</b> with title, description, price and photo, so check it before publishing.{" "}
              <a href="https://admin.shopify.com/products?selectedView=all" target="_blank" rel="noreferrer"
                 className="text-emerald-300 underline">Open Shopify</a>
            </>
          )}
          <button onClick={() => setState("idle")} className="block mt-2 text-zinc-500 hover:text-white">Close</button>
        </span>
      )}
    </span>
  );
}
