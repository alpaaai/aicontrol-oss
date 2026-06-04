import { useState, useEffect } from "react";
import { X } from "lucide-react";
import type { Policy, CreatePolicyBody } from "@/api/policies";
import { createPolicy, updatePolicy } from "@/api/policies";
import {
  type ConditionType,
  type ConditionFormState,
  CONDITION_TYPE_LABELS,
  conditionTypeFromRuleType,
  ruleTypeFromConditionType,
  conditionToFormState,
  formStateToCondition,
  defaultFormState,
  MATCH_EXAMPLES,
  evaluateMatch,
} from "./condition-form";
import { ToolDenylistForm } from "./condition-form/ToolDenylistForm";
import { ParameterMatchForm } from "./condition-form/ParameterMatchForm";
import { RateLimitForm } from "./condition-form/RateLimitForm";
import { ToolPatternForm } from "./condition-form/ToolPatternForm";
import { NumericConditionsForm } from "./condition-form/NumericConditionsForm";

type EditorMode = "form" | "json";

interface Props {
  open: boolean;
  policy: Policy | null;
  onClose: () => void;
  onSaved: () => void;
}

const inputCls =
  "w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 bg-white";

const CONDITION_TYPES: ConditionType[] = [
  "tool_denylist",
  "parameter_match",
  "rate_limit",
  "tool_pattern",
  "numeric_conditions",
];

function SubForm({
  conditionType,
  formState,
  onChange,
}: {
  conditionType: ConditionType;
  formState: ConditionFormState;
  onChange: (s: ConditionFormState) => void;
}) {
  if (formState.type !== conditionType) return null;
  switch (conditionType) {
    case "tool_denylist":
      return (
        <ToolDenylistForm
          data={(formState as Extract<ConditionFormState, { type: "tool_denylist" }>).data}
          onChange={(d) => onChange({ type: "tool_denylist", data: d })}
        />
      );
    case "parameter_match":
      return (
        <ParameterMatchForm
          data={(formState as Extract<ConditionFormState, { type: "parameter_match" }>).data}
          onChange={(d) => onChange({ type: "parameter_match", data: d })}
        />
      );
    case "rate_limit":
      return (
        <RateLimitForm
          data={(formState as Extract<ConditionFormState, { type: "rate_limit" }>).data}
          onChange={(d) => onChange({ type: "rate_limit", data: d })}
        />
      );
    case "tool_pattern":
      return (
        <ToolPatternForm
          data={(formState as Extract<ConditionFormState, { type: "tool_pattern" }>).data}
          onChange={(d) => onChange({ type: "tool_pattern", data: d })}
        />
      );
    case "numeric_conditions":
      return (
        <NumericConditionsForm
          data={(formState as Extract<ConditionFormState, { type: "numeric_conditions" }>).data}
          onChange={(d) => onChange({ type: "numeric_conditions", data: d })}
        />
      );
  }
}

function MatchPreview({
  conditionType,
  formState,
}: {
  conditionType: ConditionType;
  formState: ConditionFormState;
}) {
  const examples = MATCH_EXAMPLES[conditionType];
  return (
    <div data-testid="match-preview" className="mt-4 border border-ac-border rounded-lg p-3 bg-ac-surface">
      <p className="text-[11px] text-ac-text-muted font-medium mb-2">
        Match preview
      </p>
      <div className="space-y-1">
        {examples.map((sample) => {
          const matches = evaluateMatch(formState, sample);
          return (
            <div key={sample.label} className="flex items-center gap-2 text-[12px]">
              <span className={matches ? "text-ac-deny font-medium" : "text-ac-allow"}>
                {matches ? "✓" : "✗"}
              </span>
              <span className="font-mono text-ac-text-primary">{sample.label}</span>
              {matches && (
                <span className="text-[10px] text-ac-deny bg-ac-deny-bg px-1.5 py-0.5 rounded">
                  action applied
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PolicyEditor({ open, policy, onClose, onSaved }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [action, setAction] = useState<"deny" | "review" | "allow">("deny");
  const [priority, setPriority] = useState(100);
  const [active, setActive] = useState(true);
  const [mode, setMode] = useState<EditorMode>("form");
  const [conditionType, setConditionType] = useState<ConditionType>("tool_denylist");
  const [formState, setFormState] = useState<ConditionFormState>(
    defaultFormState("tool_denylist")
  );
  const [jsonText, setJsonText] = useState("{}");
  const [jsonError, setJsonError] = useState("");
  const [unknownConditionType, setUnknownConditionType] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    if (policy) {
      setName(policy.name);
      setDescription(policy.description ?? "");
      setAction(policy.action as "deny" | "review" | "allow");
      setPriority(policy.priority ?? 100);
      setActive(policy.active ?? true);

      const detectedType = conditionTypeFromRuleType(policy.rule_type);
      if (detectedType) {
        setConditionType(detectedType);
        const parsed = conditionToFormState(policy.rule_type, policy.condition);
        setFormState(parsed ?? defaultFormState(detectedType));
        setUnknownConditionType(false);
      } else {
        setUnknownConditionType(true);
      }
      setJsonText(JSON.stringify(policy.condition, null, 2));
    } else {
      setName("");
      setDescription("");
      setAction("deny");
      setPriority(100);
      setActive(true);
      setConditionType("tool_denylist");
      setFormState(defaultFormState("tool_denylist"));
      setJsonText(JSON.stringify(formStateToCondition(defaultFormState("tool_denylist")), null, 2));
      setUnknownConditionType(false);
    }
    setMode("form");
    setJsonError("");
    setError("");
  }, [policy, open]);

  // Keep JSON panel in sync with form state
  useEffect(() => {
    if (mode === "form") {
      setJsonText(JSON.stringify(formStateToCondition(formState), null, 2));
    }
  }, [formState, mode]);

  const switchToForm = () => {
    try {
      const parsed = JSON.parse(jsonText) as Record<string, unknown>;
      const detectedType = CONDITION_TYPES.find((t) =>
        Object.keys(parsed).some((k) =>
          k === "blocked_tools" ? t === "tool_denylist" :
          k === "parameter_match" ? t === "parameter_match" :
          k === "rate_limit" ? t === "rate_limit" :
          k === "tool_name_contains" ? t === "tool_pattern" :
          k === "numeric_conditions" ? t === "numeric_conditions" : false
        )
      );
      if (!detectedType) {
        setUnknownConditionType(true);
        setMode("form");
        return;
      }
      const hydrated = conditionToFormState(detectedType, parsed);
      if (!hydrated) {
        setUnknownConditionType(true);
        setMode("form");
        return;
      }
      setConditionType(detectedType);
      setFormState(hydrated);
      setUnknownConditionType(false);
      setJsonError("");
      setMode("form");
    } catch {
      setJsonError("Cannot switch — fix JSON parse errors first.");
    }
  };

  const handleConditionTypeChange = (newType: ConditionType) => {
    setConditionType(newType);
    setFormState(defaultFormState(newType));
    setUnknownConditionType(false);
  };

  const buildCondition = (): Record<string, unknown> => {
    if (mode === "json") {
      try {
        return JSON.parse(jsonText);
      } catch {
        return {};
      }
    }
    return formStateToCondition(formState);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body: CreatePolicyBody = {
      name,
      description: description || undefined,
      rule_type: ruleTypeFromConditionType(conditionType),
      condition: buildCondition(),
      action,
      priority,
    };
    try {
      if (policy) await updatePolicy(policy.id, { ...body, active });
      else await createPolicy(body);
      onSaved();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  const isFormMode = mode === "form";

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Slide-over panel */}
      <div
        data-testid="policy-editor-panel"
        className="w-[860px] bg-white h-full flex flex-col shadow-2xl border-l border-ac-border animate-fade-up"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-ac-border space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[17px] font-semibold text-ac-text-primary">
              {policy ? "Edit policy" : "Create policy"}
            </h2>
            <div className="flex items-center gap-3">
              {/* Form / JSON toggle */}
              <div className="flex rounded-lg border border-ac-border overflow-hidden text-[12px]">
                <button
                  type="button"
                  onClick={() => (isFormMode ? null : switchToForm())}
                  className={`px-3 py-1.5 transition-colors ${
                    isFormMode
                      ? "bg-ac-primary text-white"
                      : "text-ac-text-muted hover:bg-gray-50"
                  }`}
                >
                  Form
                </button>
                <button
                  type="button"
                  onClick={() => setMode("json")}
                  className={`px-3 py-1.5 transition-colors ${
                    !isFormMode
                      ? "bg-ac-primary text-white"
                      : "text-ac-text-muted hover:bg-gray-50"
                  }`}
                >
                  JSON
                </button>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="text-ac-text-muted hover:text-ac-text-primary"
                aria-label="Close editor"
              >
                <X size={18} />
              </button>
            </div>
          </div>
          <input
            data-testid="policy-name-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Policy name"
            className="text-sm text-ac-text-primary bg-transparent outline-none border-b border-transparent hover:border-ac-border focus:border-ac-primary transition-colors w-72"
          />
        </div>

        {/* Body */}
        <form onSubmit={handleSave} className="flex-1 overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            {/* Metadata fields — always visible */}
            <div className="px-6 py-4 space-y-3 border-b border-ac-border">
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">Description</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className={inputCls}
                  placeholder="What does this policy enforce?"
                />
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-[12px] text-ac-text-muted block mb-1">Action</label>
                  <select
                    value={action}
                    onChange={(e) => setAction(e.target.value as typeof action)}
                    className={inputCls}
                  >
                    <option value="deny">deny</option>
                    <option value="review">review</option>
                    <option value="allow">allow</option>
                  </select>
                </div>
                <div className="w-28">
                  <label className="text-[12px] text-ac-text-muted block mb-1">
                    Priority
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={priority}
                    onChange={(e) => setPriority(Number(e.target.value) || 100)}
                    className={inputCls}
                    title="Lower number = evaluated first"
                  />
                </div>
                {policy && (
                  <div className="flex items-end pb-2">
                    <label className="flex items-center gap-2 text-sm text-ac-text-primary cursor-pointer">
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={(e) => setActive(e.target.checked)}
                        className="accent-ac-primary"
                      />
                      Active
                    </label>
                  </div>
                )}
              </div>
            </div>

            {/* Condition section */}
            <div className="px-6 py-4">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1">
                  <label className="text-[12px] text-ac-text-muted block mb-1">
                    Condition type
                  </label>
                  <select
                    data-testid="condition-type-select"
                    value={conditionType}
                    onChange={(e) => handleConditionTypeChange(e.target.value as ConditionType)}
                    disabled={!isFormMode}
                    className={inputCls}
                  >
                    {CONDITION_TYPES.map((ct) => (
                      <option key={ct} value={ct}>
                        {CONDITION_TYPE_LABELS[ct]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {isFormMode ? (
                <>
                  {unknownConditionType ? (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-sm text-yellow-800">
                      This policy uses a condition type not supported by the form builder
                      (<code className="font-mono text-xs">{Object.keys(buildCondition())[0] ?? "unknown"}</code>).
                      Edit it in JSON mode.
                    </div>
                  ) : (
                    <SubForm
                      conditionType={conditionType}
                      formState={formState}
                      onChange={setFormState}
                    />
                  )}

                  {!unknownConditionType && (
                    <MatchPreview conditionType={conditionType} formState={formState} />
                  )}

                  {/* Read-only JSON panel in form mode */}
                  <div className="mt-4">
                    <p className="text-[11px] text-ac-text-muted mb-1 font-medium">
                      Condition JSON (live preview)
                    </p>
                    <pre
                      data-testid="json-panel"
                      className="bg-ac-night text-green-400 text-[11px] font-mono rounded-lg p-4 overflow-x-auto whitespace-pre-wrap"
                    >
                      {jsonText}
                    </pre>
                  </div>
                </>
              ) : (
                <>
                  {/* Editable JSON mode */}
                  <div>
                    <p className="text-[12px] text-ac-text-muted mb-1">
                      Edit the condition JSON directly. Switch back to Form to use the form builder.
                    </p>
                    <textarea
                      data-testid="json-textarea"
                      value={jsonText}
                      onChange={(e) => {
                        setJsonText(e.target.value);
                        try {
                          JSON.parse(e.target.value);
                          setJsonError("");
                        } catch {
                          setJsonError("Invalid JSON");
                        }
                      }}
                      rows={16}
                      className="w-full font-mono text-[12px] bg-ac-night text-green-400 rounded-lg p-4 outline-none border border-transparent focus:border-ac-primary resize-none"
                      spellCheck={false}
                    />
                    <p
                      className={`text-[11px] mt-1 ${
                        jsonError ? "text-ac-deny" : "text-ac-allow"
                      }`}
                    >
                      {jsonError || "✓ Valid JSON"}
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-ac-border bg-white flex items-center justify-between">
            {error && <p className="text-xs text-ac-deny">{error}</p>}
            {!error && <span />}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm border border-ac-border rounded-lg text-ac-text-muted hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !!jsonError}
                className="px-4 py-2 text-sm bg-ac-primary text-white rounded-lg font-medium disabled:opacity-50 hover:bg-ac-primary/90"
              >
                {saving ? "Saving…" : "Save policy"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
