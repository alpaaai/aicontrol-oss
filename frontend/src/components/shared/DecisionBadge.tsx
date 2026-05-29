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

export function DecisionBadge({ decision, className }: DecisionBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium animate-badge-in",
        styles[decision],
        className
      )}
    >
      {decision === "deny" ? (
        <span className="w-1.5 h-1.5 rounded-full bg-ac-deny animate-pulse-dot" />
      ) : (
        <span className={cn(
          "w-1.5 h-1.5 rounded-full",
          decision === "allow" ? "bg-ac-allow" : "bg-ac-review"
        )} />
      )}
      {decision.charAt(0).toUpperCase() + decision.slice(1)}
    </span>
  );
}
