import { cn } from "@/lib/utils";

interface Props {
  score: number;
  size?: number;
  stroke?: number;
  className?: string;
}

/** Circular 0-100 score. Green >= 70 (winner), amber 60-69 (rising), red below. */
export default function ScoreRing({ score, size = 64, stroke = 6, className }: Props) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = score >= 70 ? "#34d399" : score >= 60 ? "#fbbf24" : "#f87171";

  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#27272a" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="text-white font-bold tabular-nums" style={{ fontSize: size * 0.32 }}>
          {score}
        </span>
        {size >= 64 && <span className="text-zinc-500 text-[10px] mt-0.5">/100</span>}
      </div>
    </div>
  );
}
