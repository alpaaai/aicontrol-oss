import { cn } from "@/lib/utils";

type Decision = "allow" | "deny" | "review";

interface DecisionBadgeProps {
  decision: Decision;
  className?: string;
}

const styles: Record<Decision, string> = {
  allow:  "bg-ac-allow-bg text-ac-allow border border-ac-allow/25",
  deny:   "bg-ac-deny-bg text-ac-deny border border-ac-deny/25",
  review: "bg-ac-review-bg text-ac-review border border-ac-review/25",
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
