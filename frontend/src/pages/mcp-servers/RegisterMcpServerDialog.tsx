import { useState } from "react";
import { createMcpServer } from "@/api/mcpServers";

interface Props {
  open: boolean;
  onClose: () => void;
  onRegistered: () => void;
}

function isValidUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function RegisterMcpServerDialog({ open, onClose, onRegistered }: Props) {
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [approvedTools, setApprovedTools] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const reset = () => {
    setName("");
    setBaseUrl("");
    setApprovedTools("");
    setError("");
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidUrl(baseUrl)) {
      setError("Base URL must be a valid http(s) URL");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const tools = approvedTools
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await createMcpServer({ name, base_url: baseUrl, approved_tools: tools });
      onRegistered();
      handleClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "MCP server registration failed");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-surface-card rounded-[12px] border border-ac-hairline w-full max-w-md p-6 shadow-xl">
        <h3 className="text-[16px] font-semibold text-ac-ink mb-4">
          Register new MCP server
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
              placeholder="e.g. lending-crm"
              className="w-full border border-ac-hairline rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ac-primary-soft"
            />
          </div>
          <div>
            <label className="text-[12px] text-ac-muted block mb-1">
              Base URL *
            </label>
            <input
              required
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://crm.internal.example.com/mcp"
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
              onClick={handleClose}
              className="flex-1 border border-ac-hairline rounded-lg py-2 text-sm text-ac-muted hover:bg-ac-surface-sunk"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating}
              className="flex-1 bg-ac-primary text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
            >
              {creating ? "Registering…" : "Register server"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
