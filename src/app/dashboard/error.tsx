"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

/** Any crash inside the dashboard shows this instead of a blank page. */
export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="p-6 max-w-lg mx-auto mt-16 text-center space-y-3">
      <AlertTriangle className="mx-auto text-amber-400" />
      <h2 className="text-white font-semibold">This page couldn&apos;t load</h2>
      <p className="text-zinc-400 text-sm">Something went wrong showing this data. Try again — if it keeps happening, the service may be updating.</p>
      <div className="flex justify-center gap-2">
        <button onClick={reset} className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm hover:bg-violet-500">Try again</button>
        <Link href="/dashboard/winners" className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 text-sm hover:bg-zinc-700">Back to winners</Link>
      </div>
    </div>
  );
}
