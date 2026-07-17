import { useState, useEffect, useRef, useCallback } from "react";
import { Play, RefreshCw, Leaf, ChevronRight } from "lucide-react";
import {
  getDemoStatus,
  seedDemo,
  resetDemo,
  runIntercept,
  type InterceptResponse,
} from "@/api/demo";
import { apiClient } from "@/api/client";
import {
  INDUSTRIES,
  getScenariosForIndustry,
  type DemoScenario,
} from "@/data/demoScenarios";

type Decision = "allow" | "deny" | "review";

interface LogEntry {
  timestamp: string;
  step: number;
  tool_name: string;
  decision?: Decision;
  reason?: string;
  audit_event_id?: string;
  duration_ms?: number;
  pending: boolean;
  slack_message?: string;
  policyLine?: string;
}

interface SummaryRow {
  step: number;
  tool: string;
  decision: Decision;
  reason: string;
  ms: number;
}

const DECISION_COLOR: Record<Decision, string> = {
  allow: "text-green-600",
  deny: "text-red-600",
  review: "text-amber-600",
};

const DECISION_BG: Record<Decision, string> = {
  allow: "bg-green-50 border-green-200",
  deny: "bg-red-50 border-red-200",
  review: "bg-amber-50 border-amber-200",
};

const STORAGE_KEY = "aicontrol_demo_state";

function formatTime(d: Date): string {
  return d.toLocaleTimeString("en-US", { hour12: false });
}

export function DemoPage() {
  // Load persisted state once on mount via lazy initializer
  const [_saved] = useState<Record<string, unknown>>(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  });

  const [seeded, setSeeded] = useState(false);
  const [demoToken, setDemoToken] = useState<string | null>(null);
  const [seedLoading, setSeedLoading] = useState(false);
  const [seedBadge, setSeedBadge] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);

  const [industry, setIndustry] = useState<string>((_saved.industry as string) ?? "");
  const [scenarioName, setScenarioName] = useState<string>((_saved.scenarioName as string) ?? "");
  const [scenario, setScenario] = useState<DemoScenario | null>(
    (_saved.scenario as DemoScenario | null) ?? null
  );

  // running is never restored as true — in-flight calls cannot survive navigation
  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>((_saved.sessionId as string) ?? null);
  const [currentStep, setCurrentStep] = useState<number>((_saved.currentStep as number) ?? 0);
  const [callInFlight, setCallInFlight] = useState(false);
  const [denyPause, setDenyPause] = useState(false);
  const [completed, setCompleted] = useState<boolean>((_saved.completed as boolean) ?? false);

  const [log, setLog] = useState<LogEntry[]>((_saved.log as LogEntry[]) ?? []);
  const [summary, setSummary] = useState<SummaryRow[]>((_saved.summary as SummaryRow[]) ?? []);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Custom tool call state
  const [showCustomPrompt, setShowCustomPrompt] = useState<boolean>((_saved.showCustomPrompt as boolean) ?? false);
  const [showCustomForm, setShowCustomForm] = useState<boolean>((_saved.showCustomForm as boolean) ?? false);
  const [customStep, setCustomStep] = useState<"policy" | "tool">(
    (_saved.customStep as "policy" | "tool") ?? "policy"
  );
  const [customPolicyName, setCustomPolicyName] = useState<string>((_saved.customPolicyName as string) ?? "");
  const [customRuleType, setCustomRuleType] = useState<string>((_saved.customRuleType as string) ?? "tool_denylist");
  const [customCondition, setCustomCondition] = useState<string>(
    (_saved.customCondition as string) ?? '{"blocked_tools": ["my_tool"]}'
  );
  const [customPolicySaved, setCustomPolicySaved] = useState<boolean>((_saved.customPolicySaved as boolean) ?? false);
  const [customToolName, setCustomToolName] = useState<string>((_saved.customToolName as string) ?? "");
  const [customToolParams, setCustomToolParams] = useState<string>(
    (_saved.customToolParams as string) ?? '{"param": "value"}'
  );
  const [customToolLabel, setCustomToolLabel] = useState<string>((_saved.customToolLabel as string) ?? "");
  const [customRunning, setCustomRunning] = useState(false);

  // Persist demo state to sessionStorage so navigating away and back restores it
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        industry, scenarioName, scenario,
        log, summary, completed, currentStep, sessionId,
        showCustomPrompt, showCustomForm, customStep, customPolicySaved,
        customPolicyName, customRuleType, customCondition,
        customToolName, customToolParams, customToolLabel,
      }));
    } catch { /* quota exceeded — silently skip */ }
  }, [
    industry, scenarioName, scenario,
    log, summary, completed, currentStep, sessionId,
    showCustomPrompt, showCustomForm, customStep, customPolicySaved,
    customPolicyName, customRuleType, customCondition,
    customToolName, customToolParams, customToolLabel,
  ]);

  // Load status on mount; if already seeded but no token in env, re-issue silently
  useEffect(() => {
    getDemoStatus()
      .then(async (s) => {
        setSeeded(s.seeded);
        if (s.demo_token) {
          setDemoToken(s.demo_token);
          setSeedBadge(true);
        } else if (s.seeded) {
          try {
            const resp = await seedDemo();
            setDemoToken(resp.demo_token);
            setSeedBadge(true);
          } catch { /* silent */ }
        }
      })
      .catch(() => {});
  }, []);

  // Scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const handleSeed = async () => {
    setSeedLoading(true);
    try {
      const resp = await seedDemo();
      setSeeded(true);
      setDemoToken(resp.demo_token);
      setSeedBadge(true);
    } catch {
    } finally {
      setSeedLoading(false);
    }
  };

  const handleReset = async () => {
    setResetLoading(true);
    try {
      await resetDemo();
      setSeeded(true);
      setSeedBadge(true);
      setRunning(false);
      setCompleted(false);
      setCurrentStep(0);
      setLog([]);
      setSummary([]);
      setShowCustomPrompt(false);
      setShowCustomForm(false);
      setCustomPolicySaved(false);
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
    } finally {
      setResetLoading(false);
    }
  };

  const handleRun = () => {
    if (!scenario || !demoToken) return;
    setRunning(true);
    setCompleted(false);
    setCurrentStep(0);
    setLog([]);
    setSummary([]);
    setShowCustomPrompt(false);
    setShowCustomForm(false);
    setCustomPolicySaved(false);
    setSessionId(crypto.randomUUID());
  };

  const handleCallNextTool = useCallback(async () => {
    if (!scenario || !demoToken || !sessionId || callInFlight || denyPause) return;

    const call = scenario.tool_calls[currentStep];
    const stepNum = currentStep + 1;
    setCallInFlight(true);

    const pendingEntry: LogEntry = {
      timestamp: formatTime(new Date()),
      step: stepNum,
      tool_name: call.tool_name,
      pending: true,
    };
    setLog((prev) => [...prev, pendingEntry]);

    const start = performance.now();
    let result: InterceptResponse;
    try {
      result = await runIntercept(demoToken, {
        session_id: sessionId,
        agent_id: scenario.agent_id,
        agent_name: scenario.agent_name,
        tool_name: call.tool_name,
        tool_parameters: call.tool_parameters,
        sequence_number: stepNum,
      });
    } catch {
      setCallInFlight(false);
      return;
    }
    const durationMs = Math.round(performance.now() - start);
    const decision = result.decision;

    const updatedEntry: LogEntry = {
      timestamp: pendingEntry.timestamp,
      step: stepNum,
      tool_name: call.tool_name,
      decision,
      reason: result.reason,
      audit_event_id: result.audit_event_id,
      duration_ms: durationMs,
      pending: false,
      slack_message:
        decision === "review"
          ? `Routed to reviewer via Slack — ${result.reason || "requires human approval"}`
          : undefined,
    };
    setLog((prev) => [...prev.slice(0, -1), updatedEntry]);

    setSummary((prev) => [
      ...prev,
      {
        step: stepNum,
        tool: call.tool_name,
        decision,
        reason: result.reason || "—",
        ms: durationMs,
      },
    ]);

    const isLast = stepNum === scenario.tool_calls.length;

    if (decision === "deny") {
      setDenyPause(true);
      setTimeout(() => {
        setDenyPause(false);
        setCallInFlight(false);
        if (isLast) {
          setCompleted(true);
          setRunning(false);
          setShowCustomPrompt(true);
        } else {
          setCurrentStep((s) => s + 1);
        }
      }, 1000);
    } else {
      setCallInFlight(false);
      if (isLast) {
        setCompleted(true);
        setRunning(false);
        setShowCustomPrompt(true);
      } else {
        setCurrentStep((s) => s + 1);
      }
    }
  }, [scenario, demoToken, sessionId, currentStep, callInFlight, denyPause]);

  const handleSavePolicy = async () => {
    let condition: Record<string, unknown>;
    try {
      condition = JSON.parse(customCondition);
    } catch {
      alert("Invalid JSON in condition");
      return;
    }
    await apiClient.post("/policies", {
      name: customPolicyName,
      rule_type: customRuleType,
      condition,
      action: "deny",
      severity: "high",
      active: true,
    });
    setCustomPolicySaved(true);
    setCustomStep("tool");
  };

  const handleCustomRun = async () => {
    if (!demoToken || !sessionId) return;
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(customToolParams);
    } catch {
      alert("Invalid JSON in parameters");
      return;
    }
    setCustomRunning(true);
    const stepNum = (scenario?.tool_calls.length ?? 0) + summary.filter((r) => r.step > (scenario?.tool_calls.length ?? 0)).length + 1;

    const pendingEntry: LogEntry = {
      timestamp: formatTime(new Date()),
      step: stepNum,
      tool_name: customToolName,
      pending: true,
    };
    setLog((prev) => [...prev, pendingEntry]);

    const start = performance.now();
    let result: InterceptResponse;
    try {
      result = await runIntercept(demoToken, {
        session_id: sessionId,
        agent_id: scenario?.agent_id ?? "",
        agent_name: scenario?.agent_name ?? "demo-agent",
        tool_name: customToolName,
        tool_parameters: params,
        sequence_number: stepNum,
      });
    } catch {
      setCustomRunning(false);
      return;
    }
    const durationMs = Math.round(performance.now() - start);
    const decision = result.decision;

    const policyLine = customPolicyName
      ? `[${customPolicyName}] enforced at runtime. No restart. No deployment.`
      : undefined;

    const updatedEntry: LogEntry = {
      timestamp: pendingEntry.timestamp,
      step: stepNum,
      tool_name: customToolName,
      decision,
      reason: result.reason,
      audit_event_id: result.audit_event_id,
      duration_ms: durationMs,
      pending: false,
    };
    const extraEntries: LogEntry[] = policyLine
      ? [{ timestamp: formatTime(new Date()), step: -1, tool_name: "", pending: false, policyLine }]
      : [];
    setLog((prev) => [...prev.slice(0, -1), updatedEntry, ...extraEntries]);

    setSummary((prev) => [
      ...prev,
      {
        step: stepNum,
        tool: customToolName,
        decision,
        reason: result.reason || "—",
        ms: durationMs,
      },
    ]);
    setCustomRunning(false);
  };

  const scenariosForIndustry = industry ? getScenariosForIndustry(industry) : [];
  const canRun = seeded && !!scenario && !!demoToken;

  return (
    <div className="flex flex-col h-full min-h-0 p-6 gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Demo Runner</h1>
          <p className="text-xs text-gray-500 mt-0.5">Live browser-based prospect demo — no terminal required</p>
        </div>
        <button
          onClick={handleReset}
          disabled={resetLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 border border-ac-border hover:border-ac-peacock-300 rounded-md transition-colors"
        >
          <RefreshCw size={12} className={resetLoading ? "animate-spin" : ""} />
          Reset
        </button>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left panel */}
        <div className="w-[40%] shrink-0 flex flex-col gap-4 overflow-y-auto">
          {/* Selectors */}
          <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4 space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Industry</label>
              <select
                disabled={running}
                value={industry}
                onChange={(e) => {
                  setIndustry(e.target.value);
                  setScenarioName("");
                  setScenario(null);
                }}
                className="w-full bg-ac-card border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 disabled:opacity-50 focus:outline-none focus:border-ac-primary"
              >
                <option value="">Select industry…</option>
                {INDUSTRIES.map((ind) => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
            </div>

            {industry && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Scenario</label>
                <select
                  disabled={running}
                  value={scenarioName}
                  onChange={(e) => {
                    const name = e.target.value;
                    setScenarioName(name);
                    setScenario(
                      scenariosForIndustry.find((s) => s.scenario_name === name) ?? null
                    );
                  }}
                  className="w-full bg-ac-card border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 disabled:opacity-50 focus:outline-none focus:border-ac-primary"
                >
                  <option value="">Select scenario…</option>
                  {scenariosForIndustry.map((s) => (
                    <option key={s.scenario_name} value={s.scenario_name}>
                      {s.scenario_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Incident headline card */}
          {scenario && (
            <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4">
              <p className="text-xs leading-relaxed text-gray-700 italic">
                {scenario.incident_headline}
              </p>
            </div>
          )}

          {/* Seed + Run */}
          <div className="flex gap-2 items-center">
            <button
              onClick={handleSeed}
              disabled={seedLoading || running}
              className="flex items-center gap-1.5 px-3 py-2 text-xs bg-ac-peacock-50 hover:bg-ac-peacock-100 border border-ac-border text-gray-700 hover:text-gray-900 rounded-md transition-colors disabled:opacity-50"
            >
              <Leaf size={12} />
              {seedLoading ? "Seeding…" : "Seed"}
            </button>
            {seedBadge && (
              <span className="text-xs text-green-600 font-medium">Seeded</span>
            )}
            <button
              onClick={handleRun}
              disabled={!canRun || running}
              className="flex items-center gap-1.5 px-4 py-2 text-xs bg-ac-primary hover:bg-ac-primary/90 text-white rounded font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ml-auto"
            >
              <Play size={12} />
              Run
            </button>
          </div>

          {/* Step-by-step runner */}
          {running && scenario && (
            <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4 space-y-3">
              <div className="text-xs text-gray-500">
                Step {currentStep + 1} of {scenario.tool_calls.length}
              </div>
              <div>
                <div className="flex items-start gap-2">
                  <ChevronRight size={14} className="text-ac-primary mt-0.5 shrink-0" />
                  <span className="text-sm text-gray-900 font-medium">
                    {scenario.tool_calls[currentStep].label}
                  </span>
                </div>
                <div className="mt-2 pl-5 space-y-1">
                  <div className="text-xs text-gray-500">
                    Tool: <span className="text-blue-600 font-mono">{scenario.tool_calls[currentStep].tool_name}</span>
                  </div>
                  <div className="text-xs text-gray-400 font-mono break-all">
                    {JSON.stringify(scenario.tool_calls[currentStep].tool_parameters, null, 2)
                      .split("\n")
                      .slice(0, 6)
                      .join("\n")}
                  </div>
                </div>
              </div>

              <div className="text-xs text-gray-600 leading-relaxed">
                {scenario.step_narratives[currentStep]}
              </div>

              {/* Show decision narrative after result arrives */}
              {log.length > 0 && !log[log.length - 1].pending && log[log.length - 1].step === currentStep + 1 && (
                <div className={`text-xs p-2 rounded border ${DECISION_BG[log[log.length - 1].decision!]}`}>
                  <span className={`font-medium ${DECISION_COLOR[log[log.length - 1].decision!]}`}>
                    {log[log.length - 1].decision?.toUpperCase()}
                  </span>{" "}
                  <span className="text-gray-700">
                    {scenario.decision_narratives[currentStep]?.[log[log.length - 1].decision!]}
                  </span>
                </div>
              )}

              <button
                onClick={handleCallNextTool}
                disabled={callInFlight || denyPause}
                className="w-full py-2 text-sm font-medium bg-ac-primary hover:bg-ac-primary/90 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {callInFlight ? "Sending…" : denyPause ? "Processing…" : log.some(e => e.step === currentStep + 1 && !e.pending) ? "Next Step →" : "Call Next Tool"}
              </button>
            </div>
          )}

          {/* Custom tool call section */}
          {completed && (
            <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-4 space-y-3">
              {!showCustomForm && showCustomPrompt && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-700">Want to add a tool call with your own policy?</p>
                  <button
                    onClick={() => setShowCustomForm(true)}
                    className="px-3 py-1.5 text-xs bg-ac-peacock-50 hover:bg-ac-peacock-100 border border-ac-border text-gray-700 hover:text-gray-900 rounded-md transition-colors"
                  >
                    Yes, show me
                  </button>
                </div>
              )}

              {showCustomForm && customStep === "policy" && (
                <div className="space-y-3">
                  <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">Step 1 — Define a Policy</div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Policy name</label>
                    <input
                      value={customPolicyName}
                      onChange={(e) => setCustomPolicyName(e.target.value)}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-ac-primary"
                      placeholder="my-custom-policy"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Rule type</label>
                    <select
                      value={customRuleType}
                      onChange={(e) => setCustomRuleType(e.target.value)}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-ac-primary"
                    >
                      <option value="tool_denylist">tool_denylist</option>
                      <option value="parameter_match">parameter_match</option>
                      <option value="http_domain_block">http_domain_block</option>
                      <option value="numeric_threshold">numeric_threshold</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Condition (JSON)</label>
                    <textarea
                      value={customCondition}
                      onChange={(e) => setCustomCondition(e.target.value)}
                      rows={4}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-xs font-mono text-gray-800 focus:outline-none focus:border-ac-primary resize-none"
                    />
                  </div>
                  <button
                    onClick={handleSavePolicy}
                    disabled={!customPolicyName}
                    className="w-full py-2 text-xs font-medium bg-ac-primary hover:bg-ac-primary/90 text-white rounded transition-colors disabled:opacity-40"
                  >
                    Save Policy
                  </button>
                </div>
              )}

              {showCustomForm && customStep === "tool" && (
                <div className="space-y-3">
                  <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">Step 2 — Add the Tool Call</div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Tool name</label>
                    <input
                      value={customToolName}
                      onChange={(e) => setCustomToolName(e.target.value)}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-ac-primary"
                      placeholder="my_tool_name"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Parameters (JSON)</label>
                    <textarea
                      value={customToolParams}
                      onChange={(e) => setCustomToolParams(e.target.value)}
                      rows={4}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-xs font-mono text-gray-800 focus:outline-none focus:border-ac-primary resize-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Expected label (display only)</label>
                    <input
                      value={customToolLabel}
                      onChange={(e) => setCustomToolLabel(e.target.value)}
                      className="w-full bg-ac-surface border border-ac-border rounded-md px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-ac-primary"
                      placeholder="e.g. Exfiltrate customer data"
                    />
                  </div>
                  <button
                    onClick={handleCustomRun}
                    disabled={!customToolName || customRunning}
                    className="w-full py-2 text-xs font-medium bg-ac-primary hover:bg-ac-primary/90 text-white rounded transition-colors disabled:opacity-40"
                  >
                    {customRunning ? "Running…" : "Add & Run"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right panel — terminal */}
        <div className="flex-1 flex flex-col min-h-0 bg-[#0F1117] border border-white/[0.08] rounded-lg overflow-hidden">
          {/* Header */}
          <div className="px-4 py-2.5 border-b border-white/[0.06] flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
            <span className="ml-2 text-xs text-white/60 font-mono">aicontrol / intercept</span>
          </div>

          {/* Log */}
          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-3">
            {log.length === 0 && (
              <div className="text-white/50 text-center mt-8">
                Select a scenario and click Run to begin.
              </div>
            )}
            {log.map((entry, i) => {
              if (entry.policyLine) {
                return (
                  <div key={i} className="text-amber-400/80 text-xs border-l-2 border-amber-600/40 pl-3 py-1">
                    {entry.policyLine}
                  </div>
                );
              }
              return (
                <div
                  key={i}
                  className={`space-y-1 ${entry.decision === "deny" ? "border-l-2 border-red-600/50 pl-3" : ""}`}
                >
                  <div className="text-white">
                    [{entry.timestamp}] Step {entry.step} — {entry.tool_name}
                  </div>
                  {entry.pending ? (
                    <div className="text-white/90 animate-pulse">  → sending…</div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        <span className="text-white">  →</span>
                        <span className={`font-bold ${DECISION_COLOR[entry.decision!]}`}>
                          {entry.decision?.toUpperCase()}
                        </span>
                        {entry.reason && (
                          <span className="text-white">| reason: {entry.reason}</span>
                        )}
                        {entry.duration_ms !== undefined && (
                          <span className="text-white/70">| {entry.duration_ms}ms</span>
                        )}
                      </div>
                      {entry.slack_message && (
                        <div className="text-amber-400/70 pl-4">⚑ {entry.slack_message}</div>
                      )}
                      {entry.audit_event_id && (
                        <div className="text-white/60 pl-4">audit_event_id: {entry.audit_event_id}</div>
                      )}
                    </>
                  )}
                </div>
              );
            })}

            {/* Summary */}
            {completed && summary.length > 0 && (
              <div className="mt-4 border-t border-white/[0.08] pt-4 space-y-3">
                <div className="text-white text-xs font-semibold uppercase tracking-wider">Session Summary</div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-white border-b border-white/[0.06]">
                      <th className="text-left pb-1 pr-3">Step</th>
                      <th className="text-left pb-1 pr-3">Tool</th>
                      <th className="text-left pb-1 pr-3">Decision</th>
                      <th className="text-left pb-1 pr-3">Reason</th>
                      <th className="text-right pb-1">ms</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.map((row) => (
                      <tr key={row.step} className="border-b border-white/[0.04]">
                        <td className="py-1 pr-3 text-white">{row.step}</td>
                        <td className="py-1 pr-3 text-cyan-400">{row.tool}</td>
                        <td className={`py-1 pr-3 font-medium ${DECISION_COLOR[row.decision]}`}>
                          {row.decision.toUpperCase()}
                        </td>
                        <td className="py-1 pr-3 text-white max-w-[200px] truncate">{row.reason}</td>
                        <td className="py-1 text-right text-white/70">{row.ms}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="text-white text-xs">
                  {["allow", "deny", "review"].map((d) => {
                    const count = summary.filter((r) => r.decision === d).length;
                    if (count === 0) return null;
                    return (
                      <span key={d} className="mr-3">
                        <span className={DECISION_COLOR[d as Decision]}>{d.charAt(0).toUpperCase() + d.slice(1)}</span>: {count}
                      </span>
                    );
                  })}
                </div>

                {scenario && (
                  <div className="text-white text-xs italic leading-relaxed">
                    {scenario.closing_line}
                  </div>
                )}
              </div>
            )}

            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
