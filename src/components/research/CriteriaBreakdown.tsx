import { Criterion } from "@/lib/api";
import { cn, CriterionKey, PILLAR_LABEL, PILLAR_MAX } from "@/lib/utils";
import { KindTag } from "./Section";

/** The eight criteria: points, coverage, and every piece of evidence behind them. */
export default function CriteriaBreakdown({
  criteria, comments, only,
}: {
  criteria: Partial<Record<CriterionKey, Criterion>>;
  comments?: Partial<Record<CriterionKey, string>>;
  only?: CriterionKey[];
}) {
  const keys = (only ?? (Object.keys(PILLAR_MAX) as CriterionKey[]));
  return (
    <div className={cn("grid gap-3", !only && "md:grid-cols-2")}>
      {keys.map((k) => {
        const c = criteria[k];
        const max = c?.max ?? PILLAR_MAX[k];
        const known = !!c?.known && c.score != null;
        const ratio = known ? (c!.score as number) / max : 0;
        return (
          <div key={k} className="bg-zinc-800/40 border border-zinc-800 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-200 text-sm font-medium">{PILLAR_LABEL[k]}</span>
              <span className={cn("text-xs tabular-nums", known ? "text-zinc-300" : "text-zinc-500")}>
                {known ? `${Math.round(c!.score as number)}/${Math.round(max)}` : "no data"}
              </span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden" aria-hidden>
              <div className={cn("h-full rounded-full", ratio >= 0.7 ? "bg-emerald-400" : ratio >= 0.45 ? "bg-amber-400" : "bg-zinc-500")}
                   style={{ width: `${Math.min(100, ratio * 100)}%` }} />
            </div>
            {known && c!.coverage < 1 && (
              <div className="text-[11px] text-zinc-500">
                Based on {Math.round(c!.coverage * 100)}% of this criterion&apos;s signals
              </div>
            )}
            {c?.evidence?.length ? (
              <ul className="space-y-1.5">
                {c.evidence.map((e) => (
                  <li key={e.text} className="flex items-start gap-2 text-xs text-zinc-300 leading-relaxed">
                    <KindTag kind={e.kind} />
                    <span>{e.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-zinc-500">
                No data yet — left out of the score rather than counted as zero.
              </p>
            )}
            {comments?.[k] && (
              <p className="text-xs text-violet-200/90 border-t border-zinc-800 pt-2">
                <KindTag kind="ai" /> <span className="ml-1">{comments[k]}</span>
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
