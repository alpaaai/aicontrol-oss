import type { PolicyScope } from "../../api/policies";
import { PolicySentence } from "./PolicySentence";
import { DecisionPill } from "./DecisionPill";

// A development surface, not a product destination -- it is not in the nav.
// The nav rule is absolute: if a destination is not built for users, it is
// not in the nav.

const REVIEW_PAYMENT: PolicyScope = {
  id: "gallery-review-payment",
  principalType: "agent",
  principalId: "claims-adjuster",
  actionTool: "release_payment",
  resourceSystem: "guidewire",
  effect: "review",
  condition: { numeric_conditions: { amount: { gt: 50000 } } },
};

const DENY_BULK: PolicyScope = {
  id: "gallery-deny-bulk",
  principalType: "agent",
  principalId: "claims-adjuster",
  actionTool: "db_query",
  resourceSystem: "guidewire",
  effect: "deny",
  condition: { numeric_conditions: { row_limit: { gt: 100 } } },
};

const ANY_SYSTEM: PolicyScope = {
  id: "gallery-any-system",
  principalType: "agent",
  principalId: "claims-adjuster",
  actionTool: "release_payment",
  resourceSystem: null,
  effect: "deny",
  condition: {},
};

export function Gallery() {
  return (
    <div className="p-8 space-y-8 bg-ac-canvas min-h-screen">
      <section>
        <h2 className="text-title-lg text-ac-ink mb-4">Policy sentence</h2>
        <div className="space-y-4">
          <PolicySentence policy={REVIEW_PAYMENT} editable data-testid="policy-sentence-review-payment" />
          <PolicySentence
            policy={REVIEW_PAYMENT}
            variant="inline"
            editable
            data-testid="policy-sentence-review-payment-inline"
          />
          <PolicySentence policy={DENY_BULK} editable data-testid="policy-sentence-deny-bulk" />
          <PolicySentence policy={ANY_SYSTEM} editable data-testid="policy-sentence-any-system" />
        </div>
      </section>

      <section>
        <h2 className="text-title-lg text-ac-ink mb-4">Decision pill</h2>
        <div className="flex gap-2">
          <DecisionPill decision="allow" data-testid="decision-pill-allow" />
          <DecisionPill decision="review" data-testid="decision-pill-review" />
          <DecisionPill decision="deny" data-testid="decision-pill-deny" />
        </div>
      </section>
    </div>
  );
}
