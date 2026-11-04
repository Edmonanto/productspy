import Link from "next/link";
import { Zap } from "lucide-react";
import { SiteFooter } from "@/components/legal/LegalPage";
import TrackLanding from "@/components/landing/TrackLanding";
import { LANDING_COPY, type Lang } from "@/content/landing-copy";

/** Header + footer for the public SEO pages. */
export default function PublicShell({ lang, children }: { lang: Lang; children: React.ReactNode }) {
  const t = LANDING_COPY[lang];
  const signup = `/signup${lang === "en" ? "" : `?lang=${lang}`}`;
  return (
    <div lang={lang} className="min-h-screen bg-zinc-950 text-white overflow-x-hidden">
      <TrackLanding lang={lang} countView={false} />
      <nav data-track="nav" className="sticky top-0 z-50 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/60">
        <div className="flex items-center justify-between px-4 sm:px-8 py-3.5 max-w-6xl mx-auto">
          <Link href={t.home} className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <span className="font-bold text-white text-base sm:text-lg tracking-tight">ProductSpy</span>
            <span className="text-[10px] text-violet-400 font-bold bg-violet-500/10 border border-violet-500/20 px-1.5 py-0.5 rounded">PRO</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-5">
            <Link href={`${t.home === "/" ? "" : t.home}#pricing`} className="hidden sm:inline text-zinc-400 hover:text-white text-sm">{t.nav.pricing}</Link>
            <Link href="/login" className="text-zinc-400 hover:text-white text-xs sm:text-sm px-2 py-2">{t.nav.signIn}</Link>
            <Link href={signup} className="inline-flex items-center min-h-[40px] whitespace-nowrap bg-violet-600 hover:bg-violet-500 text-white text-xs sm:text-sm font-semibold px-3 sm:px-4 rounded-lg">{t.nav.start}</Link>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">{children}</main>
      <SiteFooter lang={lang} />
    </div>
  );
}
