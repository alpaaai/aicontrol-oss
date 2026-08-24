import { apiClient } from "./client";

// The scope fields carry a camelCase alias on the wire (see PolicyResponse in
// app/routers/policies.py) -- the same contract GET /agents/{id}/policies
// established. Everything else on the `policies` table stays snake_case.
export interface Policy {
  id: string;
  name: string;
  description: string | null;
  condition: Record<string, unknown>;
  severity: string | null;
  active: boolean | null;
  compliance_frameworks: string[] | null;
  created_by: string | null;
  priority: number;
  library: boolean;
  category: string | null;
  cedar_text?: string | null;
  principalType?: "agent" | "group" | null;
  principalId?: string | null;
  actionTool?: string | null;
  resourceSystem?: string | null;
  effect?: "deny" | "review" | null;
}

// The API speaks snake_case because that is what the `policies` columns are
// called. PolicyScope is camelCase, the TypeScript convention. This is the one
// place the conversion happens -- every component consumes PolicyScope, never
// a raw API object.
export type PolicyScope = {
  id: string;
  principalType: "agent" | "group" | null;
  principalId: string | null;
  actionTool: string | null;
  resourceSystem: string | null;
  effect: "deny" | "review";
  condition: Record<string, unknown>;
};

export function toPolicyScope(policy: Policy): PolicyScope {
  return {
    id: policy.id,
    principalType: policy.principalType ?? null,
    principalId: policy.principalId ?? null,
    actionTool: policy.actionTool ?? null,
    resourceSystem: policy.resourceSystem ?? null,
    effect: policy.effect === "review" ? "review" : "deny",
    condition: policy.condition,
  };
}

// Request bodies stay snake_case: they mirror app/routers/policies.py's
// PolicyCreate/PolicyUpdate field names exactly, which never gained a
// camelCase alias (only responses did).
export interface CreatePolicyBody {
  name: string;
  description?: string;
  condition: Record<string, unknown>;
  principal_type?: string | null;
  principal_id?: string | null;
  action_tool?: string | null;
  resource_system?: string | null;
  effect: "deny" | "review";
  severity?: string;
  compliance_frameworks?: string[];
  priority?: number;
  library?: boolean;
  category?: string;
}

export interface UpdatePolicyBody extends Partial<CreatePolicyBody> {
  active?: boolean;
}

export const listPolicies = () =>
  apiClient.get<Policy[]>("/policies").then((r) => r.data);

export const listLibraryPolicies = () =>
  apiClient.get<Policy[]>("/policies/library").then((r) => r.data);

export const getPolicy = (id: string) =>
  apiClient.get<Policy>(`/policies/${id}`).then((r) => r.data);

export const createPolicy = (body: CreatePolicyBody) =>
  apiClient.post<Policy>("/policies", body).then((r) => r.data);

export const updatePolicy = (id: string, body: UpdatePolicyBody) =>
  apiClient.put<Policy>(`/policies/${id}`, body).then((r) => r.data);

export const deletePolicy = (id: string) =>
  apiClient.delete(`/policies/${id}`).then((r) => r.data);

export interface PolicyActivity {
  window: string;
  fired: number;
  calls_evaluated: number;
}

export const getPolicyActivity = (id: string, window = "7d") =>
  apiClient
    .get<PolicyActivity>(`/policies/${id}/activity`, { params: { window } })
    .then((r) => r.data);

export interface BaselineActivateResponse {
  mode: string;
  activated: string[];
}

export const activateBaseline = (mode: "standard" | "strict") =>
  apiClient
    .post<BaselineActivateResponse>("/policies/activate-baseline", { mode })
    .then((r) => r.data);

// POST /policies/nl-draft is snake_case on the wire (task 5.2's response
// envelope) -- draftToPolicyScope passes it through the same camelCase
// boundary toPolicyScope established, so DraftReview never touches a raw
// API object either.
export interface NLDraftScope {
  principal_type: "agent" | "group" | null;
  principal_id: string | null;
  action_tool: string | null;
  resource_system: string | null;
  effect: "deny" | "review";
  condition: Record<string, unknown>;
}

export interface NLDraftResponse {
  draft: NLDraftScope | null;
  sentence: string | null;
  status: "drafted" | "requires_manual_authoring";
  warnings: string[];
}

export function draftToPolicyScope(draft: NLDraftScope): PolicyScope {
  return {
    id: "draft",
    principalType: draft.principal_type,
    principalId: draft.principal_id,
    actionTool: draft.action_tool,
    resourceSystem: draft.resource_system,
    effect: draft.effect === "review" ? "review" : "deny",
    condition: draft.condition,
  };
}

export const draftPolicy = (description: string) =>
  apiClient
    .post<NLDraftResponse>("/policies/nl-draft", { description })
    .then((r) => r.data);

export interface SimulationMatch {
  audit_event_id: string;
  tool_name: string;
  decision: string;
  occurred_at: string | null;
}

export interface SimulationResult {
  eligible_events: number;
  would_deny: number | null;
  would_review: number | null;
  corpus_start: string | null;
  corpus_note: string | null;
  matches: SimulationMatch[];
}

export const simulatePolicy = (draft: NLDraftScope, windowDays = 7) =>
  apiClient
    .post<SimulationResult>("/policies/simulate", { draft, window_days: windowDays })
    .then((r) => r.data);
