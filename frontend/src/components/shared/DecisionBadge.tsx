import { cn } from "@/lib/utils";

type Decision = "allow" | "deny" | "review";

interface DecisionBadgeProps {
  decision: Decision;
  className?: string;
}

const styles: Record<Decision, string> = {
  allow:  "bg-ac-allow-bg text-ac-allow border border-green-200",
  deny:   "bg-ac-deny-bg text-ac-deny border border-red-200",
  review: "bg-ac-review-bg text-ac-review border border-amber-200",
};

const dots: Record<Decision, string> = {
  allow:  "bg-ac-allow",
  deny:   "bg-ac-deny",
  review: "bg-ac-review",
};

export function DecisionBadge({ decision, className }: DecisionBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium",
        styles[decision],
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", dots[decision])} />
      {decision.charAt(0).toUpperCase() + decision.slice(1)}
    </span>
  );
}
