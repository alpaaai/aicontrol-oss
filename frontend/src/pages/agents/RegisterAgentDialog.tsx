import { useState } from "react";
import { createAgent } from "@/api/agents";
import { createToken } from "@/api/tokens";
import type { CreateTokenResponse } from "@/api/tokens";
import { Copy, CheckCircle } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onRegistered: () => void;
}

export function RegisterAgentDialog({ open, onClose, onRegistered }: Props) {
  const [name, setName] = useState("");
  const [owner, setOwner] = useState("");
  const [framework, setFramework] = useState("");
  const [approvedTools, setApprovedTools] = useState("");
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<CreateTokenResponse | null>(null);
  const [agentId, setAgentId] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const tools = approvedTools
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const agent = await createAgent({
        name,
        owner,
        framework: framework || undefined,
        approved_tools: tools,
      });
      const token = await createToken("agent", `agent:${agent.name}`, agent.id);
      setAgentId(agent.id);
      setResult(token);
      onRegistered();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Agent registration failed");
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = () => {
    if (result) {
      navigator.clipboard.writeText(result.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDone = () => {
    setName("");
    setOwner("");
    setFramework("");
    setApprovedTools("");
    setResult(null);
    setAgentId("");
    setCopied(false);
    setError("");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-surface-card rounded-[12px] border border-ac-hairline w-full max-w-md p-6 shadow-xl">
        {!result ? (
          <>
            <h3 className="text-[16px] font-semibold text-ac-ink mb-4">
              Register new agent
            </h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="text-[12px] text-ac-muted block mb-1">
                  Name *
                </label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. lending-underwriter"
                  className="w-full border border-ac-hairline rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary-soft"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-muted block mb-1">
                  Owner *
                </label>
                <input
                  required
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  placeholder="e.g. risk-team"
                  className="w-full border border-ac-hairline rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary-soft"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-muted block mb-1">
                  Framework
                </label>
                <input
                  value={framework}
                  onChange={(e) => setFramework(e.target.value)}
                  placeholder="e.g. langgraph"
                  className="w-full border border-ac-hairline rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary-soft"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-muted block mb-1">
                  Approved tools
                </label>
                <input
                  value={approvedTools}
                  onChange={(e) => setApprovedTools(e.target.value)}
                  placeholder="comma-separated, e.g. get_account, list_transactions"
                  className="w-full border border-ac-hairline rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary-soft"
                />
              </div>
              {error && <p className="text-xs text-ac-decision-deny">{error}</p>}
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 border border-ac-hairline rounded-lg py-2 text-sm text-ac-muted hover:bg-ac-surface-sunk"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
                >
                  {creating ? "Registering…" : "Register agent"}
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle size={16} className="text-ac-decision-allow" />
              <h3 className="text-[16px] font-semibold text-ac-ink">
                Agent registered
              </h3>
            </div>
            <p className="text-sm text-ac-muted mb-3">
              Copy this token now. It will not be shown again.
            </p>
            <div className="bg-gray-50 border border-ac-hairline rounded-lg px-3 py-2.5 flex items-center gap-2 mb-4">
              <code className="text-[12px] font-mono text-ac-ink flex-1 truncate">
                {result.token}
              </code>
              <button
                onClick={handleCopy}
                className="text-ac-muted hover:text-ac-primary shrink-0"
              >
                {copied ? (
                  <CheckCircle size={14} className="text-ac-decision-allow" />
                ) : (
                  <Copy size={14} />
                )}
              </button>
            </div>
            <div className="text-[12px] text-ac-muted space-y-0.5 mb-4">
              <p>
                Agent ID: <span className="font-mono">{agentId}</span>
              </p>
              <p>
                Role: <span className="font-mono">{result.role}</span>
              </p>
            </div>
            <button
              onClick={handleDone}
              className="w-full bg-ac-primary text-white rounded-lg py-2 text-sm font-medium"
            >
              Done
            </button>
          </>
        )}
      </div>
    </div>
  );
}
