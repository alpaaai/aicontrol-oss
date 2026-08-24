// Deny is the only filled pill. It is the heaviest object on any screen it
// appears on, by design, and carries no hue that competes with the brand.
const VARIANT: Record<"allow" | "review" | "deny", string> = {
  allow: "bg-ac-decision-allow-soft text-ac-decision-allow",
  review: "bg-ac-decision-review-soft text-ac-decision-review",
  deny: "bg-ac-decision-deny text-ac-on-ink",
};

export function DecisionPill(props: {
  decision: "allow" | "review" | "deny";
  "data-testid"?: string;
}) {
  return (
    <span
      data-testid={props["data-testid"]}
      className={`inline-flex items-center rounded-full px-[10px] py-[3px] text-label-uc ${VARIANT[props.decision]}`}
    >
      {props.decision}
    </span>
  );
}
