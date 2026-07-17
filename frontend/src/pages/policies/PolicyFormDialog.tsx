import { useState, useEffect } from "react";
import type { Policy, CreatePolicyBody } from "@/api/policies";
import { createPolicy, updatePolicy } from "@/api/policies";

interface Props {
  open: boolean;
  policy: Policy | null;
  onClose: () => void;
  onSaved: () => void;
}

export function PolicyFormDialog({ open, policy, onClose, onSaved }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ruleType, setRuleType] = useState("tool_restriction");
  const [action, setAction] = useState("deny");
  const [active, setActive] = useState(true);
  const [frameworks, setFrameworks] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (policy) {
      setName(policy.name);
      setDescription(policy.description ?? "");
      setRuleType(policy.rule_type);
      setAction(policy.action);
      setActive(policy.active ?? true);
      setFrameworks((policy.compliance_frameworks ?? []).join(", "));
    } else {
      setName("");
      setDescription("");
      setRuleType("tool_restriction");
      setAction("deny");
      setActive(true);
      setFrameworks("");
    }
    setError("");
  }, [policy, open]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body: CreatePolicyBody = {
      name,
      description: description || undefined,
      rule_type: ruleType,
      condition: {},
      action,
      compliance_frameworks: frameworks
        ? frameworks.split(",").map((t) => t.trim()).filter(Boolean)
        : [],
    };
    try {
      if (policy) await updatePolicy(policy.id, { ...body, active });
      else await createPolicy(body);
      onSaved();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-md p-6 shadow-xl">
        <h3 className="text-[16px] font-semibold text-ac-text-primary mb-4">
          {policy ? "Edit Policy" : "Create Policy"}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-[12px] text-ac-text-muted block mb-1">
              Name *
            </label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
          </div>
          <div>
            <label className="text-[12px] text-ac-text-muted block mb-1">
              Description
            </label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
          </div>
          <div>
            <label className="text-[12px] text-ac-text-muted block mb-1">
              Rule type
            </label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            >
              <option value="tool_restriction">tool_restriction</option>
              <option value="rate_limit">rate_limit</option>
              <option value="data_access">data_access</option>
            </select>
          </div>
          <div>
            <label className="text-[12px] text-ac-text-muted block mb-1">
              Action
            </label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            >
              <option value="deny">deny</option>
              <option value="review">review</option>
              <option value="allow">allow</option>
            </select>
          </div>
          <div>
            <label className="text-[12px] text-ac-text-muted block mb-1">
              Compliance frameworks (comma separated)
            </label>
            <input
              value={frameworks}
              onChange={(e) => setFrameworks(e.target.value)}
              placeholder="soc2, hipaa, eu_ai_act"
              className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
            />
          </div>
          {policy && (
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
                id="active-toggle"
                className="accent-ac-primary"
              />
              <label
                htmlFor="active-toggle"
                className="text-sm text-ac-text-primary"
              >
                Active
              </label>
            </div>
          )}
          {error && <p className="text-xs text-ac-deny">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-ac-border rounded-lg py-2 text-sm text-ac-text-muted hover:bg-ac-peacock-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
            >
              {saving ? "Saving…" : policy ? "Save changes" : "Create policy"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
