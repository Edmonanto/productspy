import { cn, EVIDENCE_KIND } from "@/lib/utils";

/** A numbered report section with an anchor for the section nav. */
export function Section({
  id, n, title, subtitle, children, className, actions,
}: {
  id: string; n: number; title: string; subtitle?: string; children: React.ReactNode;
  className?: string; actions?: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`}
             className={cn("bg-zinc-900 border border-zinc-800 rounded-xl p-4 md:p-5 space-y-4 scroll-mt-28 break-inside-avoid", className)}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 id={`${id}-h`} className="text-white font-semibold flex items-baseline gap-2">
            <span className="text-zinc-500 text-xs tabular-nums">{String(n).padStart(2, "0")}</span>
            {title}
          </h3>
          {subtitle && <p className="text-zinc-500 text-xs mt-0.5">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function KindTag({ kind }: { kind: string }) {
  const k = EVIDENCE_KIND[kind] ?? { label: kind, tone: "text-zinc-400 bg-zinc-800" };
  return <span className={cn("text-[10px] font-medium rounded px-1.5 py-0.5 shrink-0", k.tone)}>{k.label}</span>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-zinc-500 text-sm">{children}</p>;
}

export function Bullets({ items, icon }: { items: string[]; icon?: React.ReactNode }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((t) => (
        <li key={t} className="flex gap-2 text-sm text-zinc-300">
          {icon ?? <span className="text-zinc-600 mt-0.5">•</span>}
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}
