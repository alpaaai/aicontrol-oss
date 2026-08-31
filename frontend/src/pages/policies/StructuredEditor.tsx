import { useEffect, useState } from "react";
import { createPolicy, type PolicyScope } from "@/api/policies";
import { Button } from "@/components/primitives/Button";

const NUMERIC_OPS: Record<string, string> = { gt: ">", gte: "≥", lt: "<", lte: "≤", eq: "=" };

// The structured editor edits the four scope columns plus a simple numeric
// condition -- not the old twelve-field rule_type form, which no longer maps
// to anything Cedar understands. On a free install this is the only input
// (D11), opened directly in the New Policy modal; on a paid install it's one
// tap away from the NL composer via "Write policy manually." Every keystroke
// is mirrored out via onScopeChange so the modal's side card can preview it
// live, before anything is created.
export function StructuredEditor(props: { onCreated?: () => void; onScopeChange?: (scope: PolicyScope | null) => void }) {
  const [name, setName] = useState("");
  const [principalId, setPrincipalId] = useState("");
  const [actionTool, setActionTool] = useState("");
  const [resourceSystem, setResourceSystem] = useState("");
  const [effect, setEffect] = useState<"deny" | "review">("deny");
  const [conditionField, setConditionField] = useState("");
  const [conditionOp, setConditionOp] = useState<keyof typeof NUMERIC_OPS>("gt");
  const [conditionValue, setConditionValue] = useState("");

  const reset = () => {
    setName("");
    setPrincipalId("");
    setActionTool("");
    setResourceSystem("");
    setEffect("deny");
    setConditionField("");
    setConditionValue("");
  };

  const buildCondition = () =>
    conditionField.trim() && conditionValue.trim()
      ? { numeric_conditions: { [conditionField.trim()]: { [conditionOp]: Number(conditionValue) } } }
      : {};

  useEffect(() => {
    const isEmpty = !name.trim() && !principalId.trim() && !actionTool.trim() && !resourceSystem.trim() && !conditionField.trim();
    props.onScopeChange?.(
      isEmpty
        ? null
        : {
            id: "draft",
            principalType: principalId.trim() ? "agent" : null,
            principalId: principalId.trim() || null,
            actionTool: actionTool.trim() || null,
            resourceSystem: resourceSystem.trim() || null,
            effect,
            condition: buildCondition(),
          },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, principalId, actionTool, resourceSystem, effect, conditionField, conditionOp, conditionValue]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      await createPolicy({
        name: name.trim(),
        condition: buildCondition(),
        principal_type: principalId.trim() ? "agent" : null,
        principal_id: principalId.trim() || null,
        action_tool: actionTool.trim() || null,
        resource_system: resourceSystem.trim() || null,
        effect,
      });
      reset();
      props.onCreated?.();
    } catch {
      // Validation errors surface from the API; the form keeps its values so
      // the founder can correct and resubmit rather than losing the draft.
    }
  };

  const inputClass =
    "w-full h-9 rounded-md border border-ac-hairline-strong bg-ac-canvas-soft px-3 text-body-sm text-ac-ink " +
    "placeholder:text-ac-muted focus:outline focus:outline-2 focus:outline-ac-primary focus:outline-offset-2";

  return (
    <div data-testid="structured-editor">
      <h2 className="text-title-sm text-ac-ink mb-4">Build a policy</h2>
      <div className="space-y-3">
        <input className={inputClass} placeholder="Policy name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className={inputClass} placeholder="Agent (blank = every agent)" value={principalId} onChange={(e) => setPrincipalId(e.target.value)} />
        <input className={inputClass} placeholder="Tool (blank = any tool)" value={actionTool} onChange={(e) => setActionTool(e.target.value)} />
        <input className={inputClass} placeholder="System (blank = anywhere)" value={resourceSystem} onChange={(e) => setResourceSystem(e.target.value)} />
        <select className={inputClass} value={effect} onChange={(e) => setEffect(e.target.value as "deny" | "review")}>
          <option value="deny">Deny</option>
          <option value="review">Send for approval</option>
        </select>
        <div className="flex gap-2">
          <input className={inputClass} placeholder="Condition field" value={conditionField} onChange={(e) => setConditionField(e.target.value)} />
          <select className={inputClass + " w-20"} value={conditionOp} onChange={(e) => setConditionOp(e.target.value as keyof typeof NUMERIC_OPS)}>
            {Object.entries(NUMERIC_OPS).map(([op, symbol]) => (
              <option key={op} value={op}>{symbol}</option>
            ))}
          </select>
          <input className={inputClass} placeholder="Value" value={conditionValue} onChange={(e) => setConditionValue(e.target.value)} />
        </div>
        <Button label="Create policy" pendingLabel="Creating…" doneLabel="Created" onClick={handleCreate} />
      </div>
    </div>
  );
}
