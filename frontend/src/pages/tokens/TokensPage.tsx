import { useState, useEffect } from "react";
import { CreateTokenDialog } from "./CreateTokenDialog";
import { listTokens } from "@/api/tokenList";
import type { TokenListItem } from "@/api/tokenList";
import { Plus, Info } from "lucide-react";

export function TokensPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createdCount, setCreatedCount] = useState(0);
  const [tokens, setTokens] = useState<TokenListItem[]>([]);
  const [activeOnly, setActiveOnly] = useState(true);
  const [tokensLoading, setTokensLoading] = useState(true);

  useEffect(() => {
    setTokensLoading(true);
    listTokens(activeOnly).then(setTokens).finally(() => setTokensLoading(false));
  }, [activeOnly, createdCount]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5 animate-fade-up">
        <div>
          <h2 className="text-[18px] font-semibold text-ac-text-primary">
            API tokens
          </h2>
          <p className="text-sm text-ac-text-muted mt-0.5">
            Manage agent authentication tokens
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="flex items-center gap-1.5 bg-ac-primary text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-ac-primary/90"
        >
          <Plus size={14} /> New token
        </button>
      </div>

      <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card p-5 flex items-start gap-3">
        <Info size={16} className="text-ac-text-muted shrink-0 mt-0.5" />
        <div>
          <p className="text-[13px] font-medium text-ac-text-primary mb-1">
            Tokens are shown once
          </p>
          <p className="text-[13px] text-ac-text-muted">
            For security, the full token value is only displayed at creation
            time and cannot be retrieved afterwards. Store tokens securely
            immediately after creating them. To rotate a token, create a new one
            — existing tokens on an agent are automatically revoked.
          </p>
          {createdCount > 0 && (
            <p className="text-[12px] text-ac-allow mt-2">
              {createdCount} token{createdCount !== 1 ? "s" : ""} created this
              session.
            </p>
          )}
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-semibold text-ac-text-primary">
            Issued tokens
          </h3>
          <label className="flex items-center gap-2 text-[12px] text-ac-text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="rounded"
            />
            Active only
          </label>
        </div>

        <div className="bg-ac-card border border-ac-border rounded-lg shadow-ac-card overflow-hidden">
          <div
            className="grid gap-3 px-4 py-2.5 text-[11px] font-medium text-ac-text-muted uppercase tracking-wide border-b border-ac-border bg-gray-50"
            style={{ gridTemplateColumns: "1fr 80px 160px 80px 140px" }}
          >
            <div>Description</div>
            <div>Role</div>
            <div>Agent</div>
            <div>Status</div>
            <div>Created</div>
          </div>

          {tokensLoading && (
            <div className="h-10 bg-gray-50 animate-pulse m-4 rounded" />
          )}

          {!tokensLoading && tokens.length === 0 && (
            <div className="text-center text-sm text-ac-text-muted py-8">
              No tokens found.
            </div>
          )}

          {tokens.map((t) => (
            <div
              key={t.id}
              className="grid gap-3 px-4 py-2.5 text-[13px] border-b border-gray-50"
              style={{ gridTemplateColumns: "1fr 80px 160px 80px 140px" }}
            >
              <div>
                <p className="font-medium text-ac-text-primary truncate">
                  {t.description ?? "—"}
                </p>
                <p className="font-mono text-[10px] text-ac-text-muted">
                  {t.id.slice(0, 8)}…
                </p>
              </div>
              <div className="flex items-center">
                <span className="text-[11px] font-mono bg-gray-100 px-1.5 py-0.5 rounded">
                  {t.role}
                </span>
              </div>
              <div className="flex items-center text-[12px] text-ac-text-muted truncate">
                {t.agent_name ?? "—"}
              </div>
              <div className="flex items-center">
                {t.revoked ? (
                  <span className="text-[11px] text-red-500 font-medium">
                    Revoked
                  </span>
                ) : (
                  <span className="text-[11px] text-ac-allow font-medium">
                    Active
                  </span>
                )}
              </div>
              <div className="flex items-center text-[12px] text-ac-text-muted">
                {t.created_at
                  ? new Date(t.created_at).toLocaleDateString()
                  : "—"}
              </div>
            </div>
          ))}
        </div>
      </div>

      <CreateTokenDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={() => setCreatedCount((c) => c + 1)}
      />
    </div>
  );
}
