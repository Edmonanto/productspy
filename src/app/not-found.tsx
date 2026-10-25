import Link from "next/link";
import { Zap } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center px-4 text-center space-y-5">
      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
        <Zap size={22} className="text-white" />
      </div>
      <h1 className="text-3xl font-bold">Page not found</h1>
      <p className="text-zinc-400 text-sm max-w-sm">This page doesn&apos;t exist or has moved.</p>
      <div className="flex gap-3">
        <Link href="/" className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 text-sm font-semibold px-5 py-2.5 rounded-xl">Home</Link>
        <Link href="/dashboard/winners" className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-5 py-2.5 rounded-xl">Daily Winners</Link>
      </div>
    </div>
  );
}
