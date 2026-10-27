import { Breakdown } from "@/lib/api";
import { cn, PILLAR_LABEL, PILLAR_MAX } from "@/lib/utils";

interface Props {
  breakdown: Breakdown;
  compact?: boolean;
}

export default function PillarBars({ breakdown, compact = false }: Props) {
  const keys = Object.keys(PILLAR_MAX) as (keyof typeof PILLAR_MAX)[];
  return (
    <div className={cn("space-y-1.5", compact && "space-y-1")}>
      {keys.map((k) => {
        const max = PILLAR_MAX[k];
        const raw = breakdown?.[k];
        const known = raw !== null && raw !== undefined;
        const val = known ? raw : 0;
        const ratio = val / max;
        return (
          <div key={k} className="flex items-center gap-2">
            <span className={cn("text-zinc-400 shrink-0", compact ? "w-[6.5rem] text-[11px]" : "w-28 text-xs")}>
              {PILLAR_LABEL[k]}
            </span>
            <div
              className={cn("flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden", !known && "opacity-50")}
              title={known ? undefined : "No data for this signal yet — left out of the score"}
            >
              <div
                className={cn(
                  "h-full rounded-full",
                  ratio >= 0.75 ? "bg-emerald-400" : ratio >= 0.5 ? "bg-amber-400" : "bg-zinc-500"
                )}
                style={{ width: `${Math.min(100, ratio * 100)}%` }}
              />
            </div>
            <span className={cn("text-zinc-300 tabular-nums text-right shrink-0", compact ? "w-12 text-[11px]" : "w-14 text-xs")}>
              {known ? `${Math.round(val)}/${max}` : "no data"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
