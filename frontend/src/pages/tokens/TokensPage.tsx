import { useState } from "react";
import { CreateTokenDialog } from "./CreateTokenDialog";
import { Plus, Info } from "lucide-react";

export function TokensPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createdCount, setCreatedCount] = useState(0);

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

      <div className="bg-ac-card border border-ac-border rounded-[10px] p-5 flex items-start gap-3">
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

      <CreateTokenDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={() => setCreatedCount((c) => c + 1)}
      />
    </div>
  );
}
