"use client";

import { useEffect, useState } from "react";
import { Check, Download, ExternalLink, ShoppingBag, X } from "lucide-react";
import { winnersApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const STEPS: { title: string; body: React.ReactNode }[] = [
  { title: "Open your Shopify admin", body: <>Go to <b>Products</b> in the left menu.</> },
  { title: "Click “Import”", body: <>Top right of the Products page, then <b>Add file</b> and pick the file you just downloaded (it&apos;s in your Downloads folder).</> },
  { title: "Upload and import", body: <>Click <b>Upload and preview</b>, then <b>Import products</b>. Leave “Overwrite products” unticked.</> },
  { title: "Check the draft, then publish", body: <>The product arrives as a <b>Draft</b> with title, description, price, cost and photo. Review the text and price, connect your supplier, then set it to <b>Active</b>.</> },
];

/**
 * "Add to Shopify": downloads the product as a Shopify import file (draft
 * product: title, description, price, cost, photo), then walks the user
 * through the import in a dialog. A direct store connection can replace this.
 */
export default function ShopifyButton({ productId, variant = "card" }: { productId: string; variant?: "card" | "page" | "tile" }) {
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [file, setFile] = useState<string>("");

  async function go(e?: React.MouseEvent) {
    e?.preventDefault();
    e?.stopPropagation();
    setState("busy");
    try {
      setFile(await winnersApi.shopifyCsv(productId));
      setState("done");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    if (state !== "done" && state !== "error") return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setState("idle");
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state]);

  const size = variant === "card" ? 12 : 13;
  const style = {
    page: "flex items-center gap-1.5 text-xs rounded-lg px-3 py-2 min-h-[40px] border text-emerald-300 border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20",
    card: "flex items-center gap-1 px-2.5 py-2 md:py-1.5 max-md:min-h-[44px] rounded-md text-emerald-300 hover:text-emerald-200 hover:bg-emerald-500/10",
    tile: "w-full flex items-center justify-center gap-1.5 text-xs font-medium py-2 min-h-[40px] text-emerald-300 hover:text-emerald-200 hover:bg-emerald-500/10 border-t border-zinc-800",
  }[variant];

  return (
    <>
      <button onClick={go} disabled={state === "busy"} title="Add this product to your Shopify store (as a draft)"
              className={cn(style, state === "busy" && "opacity-60")}>
        <ShoppingBag size={size} /> {state === "busy" ? "Preparing…" : "Add to Shopify"}
      </button>

      {(state === "done" || state === "error") && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
             onClick={() => setState("idle")}>
          <div role="dialog" aria-modal="true" aria-labelledby="shopify-title" onClick={(e) => e.stopPropagation()}
               className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl text-left">
            <div className="flex items-start justify-between gap-3 p-5 pb-3">
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-300 flex items-center justify-center">
                  <ShoppingBag size={20} />
                </span>
                <div>
                  <h2 id="shopify-title" className="text-white font-semibold">
                    {state === "error" ? "Couldn't prepare the file" : "Add it to your Shopify store"}
                  </h2>
                  <p className="text-xs text-zinc-400">
                    {state === "error" ? "Please try again in a moment." : "About 30 seconds, in 4 steps"}
                  </p>
                </div>
              </div>
              <button onClick={() => setState("idle")} aria-label="Close" className="p-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800">
                <X size={16} />
              </button>
            </div>

            {state === "done" && (
              <>
                <div className="mx-5 mb-4 flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-xs text-emerald-200">
                  <Check size={14} className="shrink-0" />
                  <span className="min-w-0">Downloaded <b className="break-all">{file}</b></span>
                </div>
                <ol className="px-5 space-y-3">
                  {STEPS.map((s, i) => (
                    <li key={s.title} className="flex gap-3">
                      <span className="shrink-0 w-6 h-6 rounded-full bg-violet-600 text-white text-xs font-bold flex items-center justify-center">{i + 1}</span>
                      <div className="text-sm">
                        <div className="text-white font-medium">{s.title}</div>
                        <div className="text-zinc-400 text-xs leading-relaxed mt-0.5">{s.body}</div>
                      </div>
                    </li>
                  ))}
                </ol>
              </>
            )}

            <div className="flex flex-wrap gap-2 p-5">
              {state === "done" && (
                <a href="https://admin.shopify.com/products" target="_blank" rel="noreferrer"
                   className="flex-1 whitespace-nowrap inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold text-sm px-4 py-2.5">
                  Open Shopify Products <ExternalLink size={14} />
                </a>
              )}
              <button onClick={() => go()}
                      className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-700 text-zinc-300 hover:text-white hover:border-zinc-500 text-sm px-4 py-2.5">
                <Download size={14} /> {state === "error" ? "Try again" : "Download again"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
