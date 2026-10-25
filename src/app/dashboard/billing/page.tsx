"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import Topbar from "@/components/layout/Topbar";
import { usersApi, billingApi, winnersApi, Me } from "@/lib/api";
import {
  CreditCard, Zap, Check, AlertTriangle,
  ExternalLink, X, Shield, RefreshCw
} from "lucide-react";
import { cn } from "@/lib/utils";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: 0,
    period: "",
    features: ["Top 3 Daily Winners a day", "1 market", "Score + reasons for each pick", "Watchlist (10 products)"],
    cta: "Current plan",
    highlight: false,
  },
  {
    id: "starter",
    name: "Starter",
    price: 29,
    period: "/mo",
    features: ["All 5–10 Daily Winners", "1 market", "Ad & video evidence", "7-day winners archive", "Unlimited watchlist"],
    cta: "Upgrade to Starter",
    highlight: false,
  },
  {
    id: "pro",
    name: "Pro",
    price: 79,
    period: "/mo",
    features: [
      "All Daily Winners",
      "3 markets",
      "Ad & video evidence + supplier links",
      "30-day archive + CSV export",
      "Priority support",
    ],
    cta: "Upgrade to Pro",
    highlight: true,
  },
  {
    id: "agency",
    name: "Agency",
    price: 199,
    period: "/mo",
    features: [
      "Everything in Pro",
      "Every market",
      "90-day winners archive",
      "Dedicated support",
    ],
    cta: "Upgrade to Agency",
    highlight: false,
  },
];

type Provider = "stripe" | "paypal";

export default function BillingPage() {
  const { data: me, isLoading } = useSWR<Me>("me", usersApi.me);
  const { data: winnerMeta } = useSWR("winner-markets", winnersApi.markets);
  const ent = winnerMeta?.entitlements;
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [provider, setProvider] = useState<Provider>("stripe");
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const currentPlan = me?.subscription.plan ?? "free";
  const trial = me?.trial;
  const inTrial = !!trial?.active;
  const [startingTrial, setStartingTrial] = useState(false);

  const handleStartTrial = async () => {
    setStartingTrial(true);
    try {
      await billingApi.startTrial();
      await mutate("me");
      await mutate("winner-markets");
      setMessage({ type: "success", text: `Your ${trial?.length_days ?? 7}-day Pro trial has started.` });
    } catch (err: any) {
      setMessage({ type: "error", text: err.message ?? "Could not start the trial" });
    } finally {
      setStartingTrial(false);
    }
  };
  const subStatus = me?.subscription.status ?? "active";
  const periodEnd = me?.subscription.current_period_end;

  const handleCheckout = async (planId: string) => {
    if (planId === currentPlan && !inTrial) return;
    setLoading(true);
    setSelectedPlan(planId);
    try {
      const res = await billingApi.checkout(planId, provider);
      window.location.href = res.checkout_url;
    } catch (err: any) {
      setMessage({ type: "error", text: err.message ?? "Checkout failed" });
      setLoading(false);
      setSelectedPlan(null);
    }
  };

  const handlePortal = async () => {
    setLoading(true);
    try {
      const res = await billingApi.portal();
      window.location.href = res.portal_url;
    } catch (err: any) {
      setMessage({ type: "error", text: "Could not open billing portal" });
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await billingApi.cancel();
      setMessage({ type: "success", text: "Subscription cancelled. You'll retain access until your current period ends." });
      setShowCancel(false);
    } catch (err: any) {
      setMessage({ type: "error", text: err.message ?? "Cancellation failed" });
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="flex flex-col min-h-full">
      <Topbar title="Billing" />

      <div className="p-4 sm:p-6 max-w-5xl mx-auto w-full space-y-8">

        {/* Status banner */}
        {message && (
          <div className={cn(
            "flex items-center gap-3 px-4 py-3 rounded-xl border text-sm",
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-red-500/10 border-red-500/30 text-red-400"
          )}>
            {message.type === "success" ? <Check size={14} /> : <AlertTriangle size={14} />}
            {message.text}
            <button onClick={() => setMessage(null)} className="ml-auto">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Free trial */}
        {inTrial && trial && (
          <div className="bg-gradient-to-r from-violet-900/40 to-indigo-900/20 border border-violet-700/40 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex-1">
              <p className="text-white font-semibold">
                Pro trial · {trial.days_left} day{trial.days_left === 1 ? "" : "s"} left
              </p>
              <p className="text-zinc-400 text-sm mt-0.5">
                Ends {trial.ends_at && new Date(trial.ends_at).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}.
                Pick a plan now to keep everything — paying by card, you&apos;re only charged when the trial ends.
              </p>
            </div>
            <div className="w-full sm:w-40 h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-violet-400 rounded-full"
                   style={{ width: `${Math.max(4, 100 - (trial.days_left / trial.length_days) * 100)}%` }} />
            </div>
          </div>
        )}
        {trial?.eligible && (
          <div className="bg-zinc-900 border border-violet-700/40 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex-1">
              <p className="text-white font-semibold">Try Pro free for {trial.length_days} days</p>
              <p className="text-zinc-400 text-sm mt-0.5">All Daily Winners in 3 markets, ad evidence and CSV export. No card needed.</p>
            </div>
            <button onClick={handleStartTrial} disabled={startingTrial}
                    className="px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold disabled:opacity-50">
              {startingTrial ? "Starting…" : "Start free trial"}
            </button>
          </div>
        )}
        {trial?.expired && currentPlan === "free" && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4 text-sm text-zinc-400">
            Your free trial has ended — you&apos;re on the Free plan (top 3 winners a day). Upgrade below to unlock the full list again.
          </div>
        )}

        {/* Current plan card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-zinc-500 text-xs font-medium mb-1">Current plan</p>
              <div className="flex items-center gap-3">
                <h2 className="text-white text-xl font-bold capitalize">{currentPlan}</h2>
                <span className={cn(
                  "text-xs font-semibold px-2.5 py-1 rounded-full capitalize",
                  subStatus === "active" ? "bg-emerald-500/15 text-emerald-400"
                  : subStatus === "trialing" ? "bg-blue-500/15 text-blue-400"
                  : subStatus === "past_due" ? "bg-red-500/15 text-red-400"
                  : "bg-zinc-700 text-zinc-400"
                )}>
                  {subStatus === "trialing" ? "Trial" : subStatus}
                </span>
              </div>
              {periodEnd && (
                <p className="text-zinc-500 text-xs mt-1">
                  {subStatus === "active" ? "Renews" : "Access until"}{" "}
                  {new Date(periodEnd).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                </p>
              )}
            </div>

            {currentPlan !== "free" && !inTrial && (
              <div className="flex items-center gap-2">
                <button
                  onClick={handlePortal}
                  disabled={loading}
                  className="flex items-center gap-1.5 text-xs px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
                >
                  <ExternalLink size={12} />
                  Manage
                </button>
                <button
                  onClick={() => setShowCancel(true)}
                  className="flex items-center gap-1.5 text-xs px-3 py-2 bg-zinc-800 hover:bg-red-900/30 text-zinc-500 hover:text-red-400 rounded-lg transition-colors"
                >
                  <X size={12} />
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* What the plan includes */}
          {ent && (
            <div className="mt-4 pt-4 border-t border-zinc-800 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              {[
                { label: "Markets", value: ent.markets >= 99 ? "All" : String(ent.markets) },
                { label: "Winners / day", value: ent.winners_per_day >= 10 ? "All (5–10)" : `Top ${ent.winners_per_day}` },
                { label: "Archive", value: ent.history_days ? `${ent.history_days} days` : "Today only" },
                { label: "Ad evidence · CSV", value: `${ent.ad_evidence ? "Yes" : "No"} · ${ent.export_csv ? "Yes" : "No"}` },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="text-zinc-500 flex items-center gap-1"><Zap size={10} className="text-violet-400" />{label}</div>
                  <div className="text-white font-semibold mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Payment provider toggle */}
        {(currentPlan === "free" || inTrial) && (
          <div className="flex items-center gap-3">
            <span className="text-zinc-500 text-sm">Pay with:</span>
            <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
              {(["stripe", "paypal"] as Provider[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={cn(
                    "px-4 py-2 text-xs font-medium capitalize transition-colors",
                    provider === p
                      ? "bg-violet-600 text-white"
                      : "bg-zinc-900 text-zinc-400 hover:text-white"
                  )}
                >
                  {p === "stripe" ? "💳 Card (Stripe)" : "🅿️ PayPal"}
                </button>
              ))}
            </div>
            <span className="text-zinc-600 text-xs flex items-center gap-1">
              <Shield size={11} />
              Secure & encrypted
            </span>
          </div>
        )}

        {/* Pricing grid */}
        <div>
          <h3 className="text-white font-semibold mb-4">Choose a plan</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {PLANS.map((plan) => {
              const isTrialPlan = inTrial && plan.id === currentPlan;
              const isCurrent = plan.id === currentPlan && !inTrial;
              const isProcessing = selectedPlan === plan.id && loading;

              return (
                <div
                  key={plan.id}
                  className={cn(
                    "rounded-xl border p-5 flex flex-col",
                    plan.highlight && !isCurrent
                      ? "border-violet-500/50 bg-violet-600/5"
                      : "border-zinc-800 bg-zinc-900",
                    isCurrent && "border-emerald-500/40 bg-emerald-500/5"
                  )}
                >
                  {isTrialPlan && (
                    <div className="mb-3">
                      <span className="bg-blue-500/20 text-blue-300 text-[10px] font-bold px-2.5 py-1 rounded-full border border-blue-500/30">
                        ON TRIAL · {trial?.days_left}d LEFT
                      </span>
                    </div>
                  )}
                  {plan.highlight && !isCurrent && !isTrialPlan && (
                    <div className="mb-3">
                      <span className="bg-violet-600 text-white text-[10px] font-bold px-2.5 py-1 rounded-full">
                        MOST POPULAR
                      </span>
                    </div>
                  )}
                  {isCurrent && (
                    <div className="mb-3">
                      <span className="bg-emerald-500/20 text-emerald-400 text-[10px] font-bold px-2.5 py-1 rounded-full border border-emerald-500/30">
                        CURRENT PLAN
                      </span>
                    </div>
                  )}

                  <p className="text-white font-bold text-base">{plan.name}</p>
                  <div className="mt-1 mb-4">
                    <span className="text-2xl font-extrabold text-white">
                      ${plan.price}
                    </span>
                    <span className="text-zinc-500 text-sm">{plan.period}</span>
                  </div>

                  <ul className="space-y-2 flex-1 mb-5">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-xs text-zinc-400">
                        <Check size={11} className="text-emerald-400 mt-0.5 shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>

                  <button
                    onClick={() => !isCurrent && plan.id !== "free" && handleCheckout(plan.id)}
                    disabled={isCurrent || plan.id === "free" || (loading && selectedPlan === plan.id)}
                    className={cn(
                      "w-full py-2.5 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-2",
                      isCurrent || plan.id === "free"
                        ? "bg-zinc-800 text-zinc-600 cursor-default"
                        : plan.highlight
                        ? "bg-violet-600 hover:bg-violet-500 text-white"
                        : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                    )}
                  >
                    {isProcessing ? (
                      <RefreshCw size={12} className="animate-spin" />
                    ) : isCurrent ? (
                      "Current plan"
                    ) : isTrialPlan ? (
                      "Keep Pro after trial"
                    ) : plan.id === "free" ? (
                      inTrial ? "After your trial" : "Included"
                    ) : (
                      plan.cta
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Trust signals */}
        <div className="flex items-center justify-center gap-8 text-zinc-600 text-xs border-t border-zinc-800 pt-6">
          {[
            { icon: Shield, text: "256-bit SSL encryption" },
            { icon: RefreshCw, text: "Cancel anytime" },
            { icon: CreditCard, text: "No hidden fees" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-2">
              <Icon size={12} />
              {text}
            </div>
          ))}
        </div>
      </div>

      {/* Cancel confirmation modal */}
      {showCancel && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-sm w-full space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
                <AlertTriangle size={18} className="text-red-400" />
              </div>
              <div>
                <p className="text-white font-semibold">Cancel subscription?</p>
                <p className="text-zinc-500 text-xs">You&apos;ll keep access until period end</p>
              </div>
            </div>
            {periodEnd && (
              <div className="bg-zinc-800 rounded-lg px-4 py-3 text-sm text-zinc-400">
                Access until{" "}
                <span className="text-white font-medium">
                  {new Date(periodEnd).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                </span>
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setShowCancel(false)}
                className="flex-1 py-2.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors"
              >
                Keep plan
              </button>
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2"
              >
                {cancelling ? <RefreshCw size={13} className="animate-spin" /> : "Yes, cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
