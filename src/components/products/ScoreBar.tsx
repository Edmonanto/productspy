import { cn, scoreColor } from "@/lib/utils";

interface Props {
  label: string;
  score: number;
}

export default function ScoreBar({ label, score }: Props) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className={cn("font-bold", scoreColor(score))}>{score}</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            score >= 75 ? "bg-emerald-500" : score >= 55 ? "bg-yellow-500" : "bg-red-500"
          )}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}
