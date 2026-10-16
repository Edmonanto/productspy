"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { quotesApi } from "@/lib/api";

interface Props {
  productId: string;
  productTitle: string;
  initialQuantity: number;
  open: boolean;
  onClose: () => void;
}

export default function QuoteForm({ productId, productTitle, initialQuantity, open, onClose }: Props) {
  const [quantity, setQuantity] = useState(initialQuantity);
  const [country, setCountry] = useState("");
  const [target, setTarget] = useState("");
  const [notes, setNotes] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (open) {
      setQuantity(initialQuantity);
      setSent(false);
      setError(null);
    }
  }, [open, initialQuantity]);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError(null);
    try {
      await quotesApi.create({
        product_id: productId,
        quantity,
        destination_country: country,
        target_price_usd: target ? parseFloat(target) : null,
        notes,
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the request");
    } finally {
      setSending(false);
    }
  };

  const input =
    "mt-1 w-full bg-zinc-800 border border-zinc-700 focus:border-violet-500 rounded-lg px-3 py-2 text-white text-sm outline-none";

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="quote-title"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="quote-title" className="text-white font-semibold">Request a quote</h2>
            <p className="text-zinc-500 text-xs mt-0.5 line-clamp-2">{productTitle}</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-zinc-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        {sent ? (
          <div className="space-y-3">
            <p className="text-emerald-400 text-sm">
              Request sent. We&apos;ll reply with the unit price and shipping to {country}.
            </p>
            <Link href="/dashboard/quotes" className="block text-center bg-zinc-800 hover:bg-zinc-700 text-white text-sm py-2.5 rounded-lg">
              View my quotes
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="text-zinc-500 text-xs">Quantity</span>
              <input
                type="number" min={1} step={1} required value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                className={input}
              />
            </label>
            <label className="block">
              <span className="text-zinc-500 text-xs">Ship to (country)</span>
              <input
                required minLength={2} maxLength={56} value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="e.g. United States"
                className={input}
              />
            </label>
            <label className="block">
              <span className="text-zinc-500 text-xs">Target unit price (optional)</span>
              <input
                type="number" min={0} step="0.01" value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="$"
                className={input}
              />
            </label>
            <label className="block">
              <span className="text-zinc-500 text-xs">Notes (optional)</span>
              <textarea
                rows={3} maxLength={2000} value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Variant, colour, packaging, custom logo…"
                className={input}
              />
            </label>
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <button
              type="submit" disabled={sending}
              className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-60 text-white text-sm font-semibold py-2.5 rounded-lg"
            >
              {sending ? "Sending…" : "Send request"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
