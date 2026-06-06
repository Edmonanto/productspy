import { cn, scoreBg, scoreColor, scoreLabel } from "@/lib/utils";

interface Props {
  score: number;
  size?: "sm" | "lg";
}

export default function ScoreBadge({ score, size = "sm" }: Props) {
  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 border rounded-full font-bold",
      scoreBg(score),
      size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-4 py-1.5 text-sm"
    )}>
      <span className={scoreColor(score)}>{score}</span>
      <span className="text-zinc-400">{scoreLabel(score)}</span>
    </div>
  );
}
