"use client";

import Link from "next/link";
import useSWR from "swr";
import { usersApi, Me } from "@/lib/api";
import Topbar from "@/components/layout/Topbar";
import { useAuth } from "@/context/AuthContext";
import { LogOut, ExternalLink } from "lucide-react";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-zinc-800 last:border-0">
      <span className="text-sm text-zinc-500">{label}</span>
      <span className="text-sm text-zinc-200 text-right break-words min-w-0">{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { signOut } = useAuth();
  const { data: me, isLoading } = useSWR<Me>("me", usersApi.me);

  const quota = me?.quota;
  const remaining =
    quota == null ? "—"
      : quota.remaining === "unlimited" ? "Unlimited"
      : `${quota.remaining} of ${quota.limit} left today`;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Settings" />

      <div className="p-4 sm:p-6 max-w-2xl w-full space-y-6">
        {/* Only values the API actually returns are shown here. Nothing on
            this page is a placeholder control that does nothing. */}
        <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold text-sm mb-2">Account</h2>
          {isLoading ? (
            <div className="space-y-3 animate-pulse">
              <div className="h-4 bg-zinc-800 rounded w-2/3" />
              <div className="h-4 bg-zinc-800 rounded w-1/2" />
            </div>
          ) : (
            <>
              <Row label="Name" value={me?.name || "—"} />
              <Row label="Email" value={me?.email || "—"} />
            </>
          )}
        </section>

        <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold text-sm mb-2">Plan</h2>
          <Row label="Current plan" value={<span className="capitalize">{me?.subscription.plan ?? "—"}</span>} />
          <Row label="Status" value={<span className="capitalize">{me?.subscription.status ?? "—"}</span>} />
          <Row label="Search quota" value={remaining} />
          <Link
            href="/dashboard/billing"
            className="mt-4 inline-flex items-center gap-1.5 text-sm text-violet-400 hover:text-violet-300 transition-colors"
          >
            Manage billing <ExternalLink size={13} />
          </Link>
        </section>

        <section className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold text-sm mb-3">Session</h2>
          <button
            onClick={signOut}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-700 text-sm text-zinc-300 hover:text-red-400 hover:border-red-500/40 transition-colors"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </section>
      </div>
    </div>
  );
}
