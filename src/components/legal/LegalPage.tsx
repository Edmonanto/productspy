import Link from "next/link";
import { ArrowLeft, Zap } from "lucide-react";
import { SITE } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-zinc-800 px-4 sm:px-8 py-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-zinc-500 text-sm">
        <Link href="/" className="flex items-center gap-2 py-2 -my-2">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
            <Zap size={12} className="text-white" />
          </div>
          <span className="text-zinc-500 font-medium">{SITE.name}</span>
          <span>© 2026</span>
        </Link>
        <div className="flex gap-6">
          <Link href="/privacy" className="inline-block py-3 -my-3 hover:text-zinc-300 transition-colors">Privacy</Link>
          <Link href="/terms" className="inline-block py-3 -my-3 hover:text-zinc-300 transition-colors">Terms</Link>
          <Link href="/contact" className="inline-block py-3 -my-3 hover:text-zinc-300 transition-colors">Contact</Link>
        </div>
      </div>
    </footer>
  );
}

export default function LegalPage({ title, children, showUpdated = true }: { title: string; children: React.ReactNode; showUpdated?: boolean }) {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col">
      <nav className="border-b border-zinc-800/60">
        <div className="flex items-center justify-between px-4 sm:px-8 py-4 max-w-7xl mx-auto">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-white text-lg tracking-tight">ProductSpy</span>
          </Link>
          <Link href="/" className="max-md:min-h-[44px] flex items-center gap-1.5 text-zinc-400 hover:text-white text-sm">
            <ArrowLeft size={14} /> Back to home
          </Link>
        </div>
      </nav>
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-8 py-12 sm:py-16">
        <h1 className={`text-3xl sm:text-4xl font-bold ${showUpdated ? "mb-2" : "mb-6"}`}>{title}</h1>
        {showUpdated && <p className="text-zinc-500 text-sm mb-10">Last updated {SITE.updated}</p>}
        <div className="space-y-8 text-zinc-300 text-sm leading-relaxed [&_h2]:text-white [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5 [&_a]:text-violet-400 [&_a:hover]:text-violet-300">
          {children}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
