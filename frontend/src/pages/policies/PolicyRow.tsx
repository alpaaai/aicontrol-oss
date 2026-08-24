import { Link } from "react-router-dom";
import { toPolicyScope, type Policy } from "@/api/policies";
import { PolicySentence } from "@/components/primitives/PolicySentence";

export function PolicyRow(props: { policy: Policy }) {
  const scope = toPolicyScope(props.policy);
  return (
    <li data-testid={`policy-row-${props.policy.id}`}>
      <Link
        to={`/policies/${props.policy.id}`}
        className="block border border-ac-hairline rounded-lg p-4 bg-ac-surface-card hover:bg-ac-surface-sunk transition-colors duration-standard focus:outline focus:outline-2 focus:outline-ac-primary focus:outline-offset-2"
      >
        <PolicySentence policy={scope} variant="inline" />
      </Link>
    </li>
  );
}
