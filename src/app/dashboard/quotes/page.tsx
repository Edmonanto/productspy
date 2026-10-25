"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import Topbar from "@/components/layout/Topbar";
import { quotesApi, Quote } from "@/lib/api";
import { formatPrice, timeAgo } from "@/lib/utils";

const STATUS_STYLE: Record<Quote["status"], string> = {
  open: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  quoted: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  closed: "bg-zinc-800 text-zinc-400 border-zinc-700",
};

const STATUS_LABEL: Record<Quote["status"], string> = {
  open: "Waiting for reply",
  quoted: "Quoted",
  closed: "Closed",
};

function ReplyForm({ quote, onDone }: { quote: Quote; onDone: () => void }) {
  const [unit, setUnit] = useState(quote.quoted_unit_usd?.toString() ?? "");
  const [shipping, setShipping] = useState(quote.quoted_shipping_usd?.toString() ?? "");
  const [message, setMessage] = useState(quote.reply);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (status: "quoted" | "closed") => {
    setBusy(true);
    setError(null);
    try {
      await quotesApi.reply(quote.id, {
        status,
        quoted_unit_usd: unit ? parseFloat(unit) : null,
        quoted_shipping_usd: shipping ? parseFloat(shipping) : null,
        reply: message,
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the reply");
    } finally {
      setBusy(false);
    }
  };

  const input = "w-full bg-zinc-800 border border-zinc-700 focus:border-violet-500 rounded-lg px-3 py-2 text-white text-sm outline-none";

  return (
    <div className="mt-3 pt-3 border-t border-zinc-800 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <input type="number" min={0} step="0.01" placeholder="Unit price $" value={unit} onChange={(e) => setUnit(e.target.value)} className={input} />
        <input type="number" min={0} step="0.01" placeholder="Shipping / unit $" value={shipping} onChange={(e) => setShipping(e.target.value)} className={input} />
      </div>
      <textarea rows={2} placeholder="Message to the customer" value={message} onChange={(e) => setMessage(e.target.value)} className={input} />
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <div className="flex gap-2">
        <button disabled={busy || !unit} onClick={() => send("quoted")} className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg">
          Send quote
        </button>
        <button disabled={busy} onClick={() => send("closed")} className="px-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm py-2 rounded-lg">
          Close
        </button>
      </div>
    </div>
  );
}

export default function QuotesPage() {
  const [showAll, setShowAll] = useState(false);
  const { data, isLoading, mutate } = useSWR(["quotes", showAll], () => quotesApi.list(showAll));
  const quotes = data?.quotes ?? [];
  const admin = data?.is_admin ?? false;

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Quotes" />

      <div className="p-4 sm:p-6 max-w-3xl mx-auto w-full space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-zinc-500 text-sm">
            {admin && showAll
              ? "Every customer's requests. Open ones first."
              : "Exact prices for your quantity and destination. Request one from any product page."}
          </p>
          {admin && (
            <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 text-xs">
              {[false, true].map((all) => (
                <button
                  key={String(all)}
                  onClick={() => setShowAll(all)}
                  className={`px-3 py-1.5 rounded-md ${showAll === all ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-white"}`}
                >
                  {all ? "All customers" : "Mine"}
                </button>
              ))}
            </div>
          )}
        </div>

        {isLoading && <div className="h-24 bg-zinc-900 rounded-xl animate-pulse" />}

        {!isLoading && quotes.length === 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center space-y-2">
            <p className="text-zinc-300 text-sm">No quote requests yet.</p>
            <Link href="/dashboard/trending" className="text-violet-400 hover:text-violet-300 text-sm">
              Browse products →
            </Link>
          </div>
        )}

        {quotes.map((q) => {
          const total = q.quoted_unit_usd != null
            ? (q.quoted_unit_usd + (q.quoted_shipping_usd ?? 0)) * q.quantity
            : null;
          return (
            <div key={q.id} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  {q.product_id ? (
                    <Link href={`/dashboard/winners/${q.product_id}`} className="text-white text-sm font-medium hover:text-violet-300 line-clamp-2">
                      {q.product_title || "Product"}
                    </Link>
                  ) : (
                    <p className="text-white text-sm font-medium line-clamp-2">{q.product_title || "Product"}</p>
                  )}
                  <p className="text-zinc-500 text-xs mt-1">
                    {q.quantity.toLocaleString()} units → {q.destination_country}
                    {q.target_price_usd != null && ` · target ${formatPrice(q.target_price_usd)}`}
                    {" · "}{timeAgo(q.created_at)}
                    {admin && showAll && ` · ${q.user_email}`}
                  </p>
                </div>
                <span className={`text-[11px] font-medium px-2 py-1 rounded-full border shrink-0 ${STATUS_STYLE[q.status]}`}>
                  {STATUS_LABEL[q.status]}
                </span>
              </div>

              {q.notes && <p className="text-zinc-400 text-xs mt-2 whitespace-pre-wrap">“{q.notes}”</p>}

              {q.status === "quoted" && q.quoted_unit_usd != null && (
                <div className="mt-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 text-sm">
                  <div className="flex flex-wrap gap-x-6 gap-y-1">
                    <span className="text-zinc-400">Unit <span className="text-white font-semibold">{formatPrice(q.quoted_unit_usd)}</span></span>
                    {q.quoted_shipping_usd != null && (
                      <span className="text-zinc-400">Shipping/unit <span className="text-white font-semibold">{formatPrice(q.quoted_shipping_usd)}</span></span>
                    )}
                    {total != null && (
                      <span className="text-zinc-400">Total <span className="text-emerald-300 font-semibold">{formatPrice(total)}</span></span>
                    )}
                  </div>
                  {q.reply && <p className="text-zinc-300 text-xs mt-2 whitespace-pre-wrap">{q.reply}</p>}
                </div>
              )}
              {q.status === "closed" && q.reply && (
                <p className="text-zinc-500 text-xs mt-2 whitespace-pre-wrap">{q.reply}</p>
              )}

              {admin && showAll && q.status === "open" && <ReplyForm quote={q} onDone={() => mutate()} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
