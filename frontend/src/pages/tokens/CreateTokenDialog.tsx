import { useState } from "react";
import { createToken } from "@/api/tokens";
import type { CreateTokenResponse } from "@/api/tokens";
import { Copy, CheckCircle } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function CreateTokenDialog({ open, onClose, onCreated }: Props) {
  const [description, setDescription] = useState("");
  const [role, setRole] = useState<"agent" | "admin">("agent");
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<CreateTokenResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const token = await createToken(role, description);
      setResult(token);
      onCreated();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Token creation failed");
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
    setDescription("");
    setRole("agent");
    setResult(null);
    setCopied(false);
    setError("");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-md p-6 shadow-xl">
        {!result ? (
          <>
            <h3 className="text-[16px] font-semibold text-ac-text-primary mb-4">
              Create API Token
            </h3>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">
                  Description *
                </label>
                <input
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. lending-agent-prod"
                  className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
                />
              </div>
              <div>
                <label className="text-[12px] text-ac-text-muted block mb-1">
                  Role
                </label>
                <select
                  value={role}
                  onChange={(e) =>
                    setRole(e.target.value as "agent" | "admin")
                  }
                  className="w-full border border-ac-border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20"
                >
                  <option value="agent">agent</option>
                  <option value="admin">admin</option>
                </select>
              </div>
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
                  disabled={creating}
                  className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Create token"}
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle size={16} className="text-ac-allow" />
              <h3 className="text-[16px] font-semibold text-ac-text-primary">
                Token created
              </h3>
            </div>
            <p className="text-sm text-ac-text-muted mb-3">
              Copy this token now. It will not be shown again.
            </p>
            <div className="bg-gray-50 border border-ac-border rounded-lg px-3 py-2.5 flex items-center gap-2 mb-4">
              <code className="text-[12px] font-mono text-ac-text-primary flex-1 truncate">
                {result.token}
              </code>
              <button
                onClick={handleCopy}
                className="text-ac-text-muted hover:text-ac-primary shrink-0"
              >
                {copied ? (
                  <CheckCircle size={14} className="text-ac-allow" />
                ) : (
                  <Copy size={14} />
                )}
              </button>
            </div>
            <div className="text-[12px] text-ac-text-muted space-y-0.5 mb-4">
              <p>
                Role: <span className="font-mono">{result.role}</span>
              </p>
              <p>Description: {result.description}</p>
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
