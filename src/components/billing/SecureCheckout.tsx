import { CreditCard, Lock, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/** Payment methods we accept, named as text badges (no third-party logo artwork). */
const METHODS = ["Visa", "Mastercard", "American Express", "PayPal"] as const;

/** Trust panel under the payment-provider toggle: what's accepted, who processes it, and that
 *  card numbers never touch our servers (Stripe Checkout and PayPal are hosted by them). */
export default function SecureCheckout({ provider, className }: { provider: "stripe" | "paypal"; className?: string }) {
  return (
    <div className={cn("rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3", className)}>
      <div className="flex items-center gap-2 shrink-0">
        <span className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center">
          <Lock size={14} className="text-emerald-400" aria-hidden />
        </span>
        <div className="leading-tight">
          <div className="text-white text-sm font-semibold">Secure checkout</div>
          <div className="text-zinc-500 text-[11px]">256-bit SSL encryption</div>
        </div>
      </div>
      <ul className="flex flex-wrap gap-1.5 sm:ml-2" aria-label="Accepted payment methods">
        {METHODS.map((m) => (
          <li key={m}
              className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-tight",
                (provider === "paypal") === (m === "PayPal")
                  ? "border-zinc-600 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 bg-zinc-900 text-zinc-500")}>
            {m !== "PayPal" && <CreditCard size={11} aria-hidden />}{m}
          </li>
        ))}
      </ul>
      <p className="text-zinc-500 text-[11px] sm:ml-auto sm:max-w-xs flex items-start gap-1.5">
        <ShieldCheck size={12} className="text-emerald-400 shrink-0 mt-px" aria-hidden />
        <span>
          Processed by {provider === "paypal" ? "PayPal" : "Stripe"} on their own secure page.
          We never see or store your card details.
        </span>
      </p>
    </div>
  );
}
