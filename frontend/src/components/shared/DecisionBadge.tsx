import { cn } from "@/lib/utils";

type Decision = "allow" | "deny" | "review";

interface DecisionBadgeProps {
  decision: Decision;
  className?: string;
}

const styles: Record<Decision, string> = {
  allow: "bg-decision-allow/10 text-decision-allow border-decision-allow/20",
  deny: "bg-decision-deny/10 text-decision-deny border-decision-deny/20",
  review: "bg-decision-review/10 text-decision-review border-decision-review/20",
};

export function DecisionBadge({ decision, className }: DecisionBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border uppercase tracking-wide",
        styles[decision],
        className
      )}
    >
      {decision}
    </span>
  );
}
