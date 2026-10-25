import Link from "next/link";
import { ArrowRight, Database, MessageSquareQuote, Star } from "lucide-react";
import { DATA_SOURCES, REVIEWS, TRUSTED_BY, type Review } from "@/content/social-proof";

/** "Trusted by" strip. Real customers when there are some; otherwise the
 *  public sources the scan reads (text only — no logos, no implied endorsement). */
export function TrustedBySection() {
  if (TRUSTED_BY.length > 0) {
    return (
      <section className="max-w-5xl mx-auto px-4 sm:px-8 py-12 sm:py-14 text-center">
        <p className="text-zinc-500 text-xs font-semibold uppercase tracking-widest mb-6">
          Trusted by dropshippers and stores like
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-5">
          {TRUSTED_BY.map((t) => {
            const inner = t.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={t.logoUrl} alt={t.name} className="h-7 w-auto opacity-70 hover:opacity-100 grayscale hover:grayscale-0 transition" />
            ) : (
              <span className="text-zinc-400 hover:text-white font-semibold text-lg tracking-tight transition-colors">{t.name}</span>
            );
            return t.url ? (
              <a key={t.name} href={t.url} target="_blank" rel="noopener noreferrer">{inner}</a>
            ) : (
              <span key={t.name}>{inner}</span>
            );
          })}
        </div>
      </section>
    );
  }

  return (
    <section className="max-w-5xl mx-auto px-4 sm:px-8 py-12 sm:py-14">
      <p className="text-center text-zinc-500 text-xs font-semibold uppercase tracking-widest mb-6 flex items-center justify-center gap-2">
        <Database size={13} /> Built on the public data serious dropshippers already check by hand
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {DATA_SOURCES.map((s) => (
          <div key={s.name} className="bg-zinc-900/60 border border-zinc-800 rounded-xl px-4 py-3.5 text-center">
            <div className="text-zinc-200 font-semibold text-sm">{s.name}</div>
            <div className="text-zinc-500 text-xs mt-0.5">{s.desc}</div>
          </div>
        ))}
      </div>
      <p className="text-center text-zinc-600 text-[11px] mt-4">
        ProductSpy is independent and not affiliated with or endorsed by Meta, TikTok or AliExpress.
      </p>
    </section>
  );
}

function Stars({ n }: { n: number }) {
  return (
    <div className="flex gap-0.5" aria-label={`${n} out of 5 stars`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} size={14} className={i < n ? "text-amber-400 fill-amber-400" : "text-zinc-700"} />
      ))}
    </div>
  );
}

function ReviewCard({ r }: { r: Review }) {
  const initials = r.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <figure className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 sm:p-6 flex flex-col gap-4 hover:border-zinc-700 transition-colors">
      <Stars n={r.rating} />
      <blockquote className="text-zinc-300 text-sm leading-relaxed flex-1">&ldquo;{r.quote}&rdquo;</blockquote>
      <figcaption className="flex items-center gap-3">
        {r.avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={r.avatarUrl} alt="" className="w-9 h-9 rounded-full object-cover" />
        ) : (
          <div className="w-9 h-9 rounded-full bg-violet-600/20 border border-violet-600/30 flex items-center justify-center text-violet-300 text-xs font-bold">
            {initials}
          </div>
        )}
        <div className="min-w-0">
          <div className="text-white text-sm font-semibold truncate">{r.name}</div>
          <div className="text-zinc-500 text-xs truncate">
            {r.role}{r.market ? ` · ${r.market}` : ""} · {new Date(r.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", year: "numeric" })}
          </div>
        </div>
      </figcaption>
    </figure>
  );
}

/** Reviews. Real reviews when there are some; otherwise an early-access invite. */
export function ReviewsSection() {
  if (REVIEWS.length > 0) {
    const avg = REVIEWS.reduce((s, r) => s + r.rating, 0) / REVIEWS.length;
    return (
      <section id="reviews" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
        <div className="text-center mb-10 sm:mb-12 space-y-3">
          <h2 className="text-2xl sm:text-3xl font-bold">What dropshippers say</h2>
          <div className="flex items-center justify-center gap-2 text-sm text-zinc-400">
            <Stars n={Math.round(avg)} />
            <span>{avg.toFixed(1)} / 5 from {REVIEWS.length} review{REVIEWS.length === 1 ? "" : "s"}</span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          {REVIEWS.map((r) => <ReviewCard key={r.name + r.date} r={r} />)}
        </div>
      </section>
    );
  }

  return (
    <section id="reviews" className="max-w-5xl mx-auto px-4 sm:px-8 py-16 sm:py-20">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 sm:p-10 text-center space-y-4">
        <div className="w-11 h-11 mx-auto rounded-xl bg-violet-600/20 border border-violet-600/20 flex items-center justify-center">
          <MessageSquareQuote size={20} className="text-violet-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold">Be one of our first reviewers</h2>
        <p className="text-zinc-400 text-sm max-w-xl mx-auto leading-relaxed">
          ProductSpy Pro is new, so you won&apos;t find a wall of testimonials here yet — and we won&apos;t invent one.
          Try it free for 7 days, test a pick or two, and tell us honestly how it went. Early users help shape
          what we build next.
        </p>
        <Link href="/signup" className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-3 rounded-xl transition-colors text-sm shadow-lg shadow-violet-900/30">
          Join early access <ArrowRight size={16} />
        </Link>
      </div>
    </section>
  );
}
