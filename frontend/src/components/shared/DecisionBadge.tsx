import { cn } from "@/lib/utils";

type Decision = "allow" | "deny" | "review";

interface DecisionBadgeProps {
  decision: Decision;
  className?: string;
}

const styles: Record<Decision, string> = {
  allow:  "bg-ac-decision-allow-soft text-ac-decision-allow border border-ac-decision-allow/25",
  deny:   "bg-ac-decision-deny-soft text-ac-decision-deny border border-ac-decision-deny/25",
  review: "bg-ac-decision-review-soft text-ac-decision-review border border-ac-decision-review/25",
};

export function DecisionBadge({ decision, className }: DecisionBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium animate-badge-in",
        styles[decision],
        className
      )}
    >
      {decision.charAt(0).toUpperCase() + decision.slice(1)}
    </span>
  );
}
