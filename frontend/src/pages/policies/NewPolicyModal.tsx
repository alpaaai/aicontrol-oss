import { useEffect, useState } from "react";
import { NLComposer } from "./NLComposer";
import { StructuredEditor } from "./StructuredEditor";
import { PolicyPreviewCard } from "./PolicyPreviewCard";
import type { PolicyScope } from "@/api/policies";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  nlAuthoringEnabled: boolean;
}

// The single entry point for creating a policy (spec §5 point 1 / D11), now a
// modal rather than always-on inline forms. Natural language is the default
// mode when it's licensed; a free install opens straight to the structured
// editor and never sees the manual-switch link, matching the prior inline
// behavior where the editor was the only input.
export function NewPolicyModal({ open, onClose, onCreated, nlAuthoringEnabled }: Props) {
  const [mode, setMode] = useState<"nl" | "manual">(nlAuthoringEnabled ? "nl" : "manual");
  const [previewScope, setPreviewScope] = useState<PolicyScope | null>(null);

  useEffect(() => {
    if (open) {
      setMode(nlAuthoringEnabled ? "nl" : "manual");
      setPreviewScope(null);
    }
  }, [open, nlAuthoringEnabled]);

  if (!open) return null;

  const handleCreated = () => {
    setPreviewScope(null);
    onCreated();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div
        data-testid="new-policy-modal"
        className="bg-ac-surface-card rounded-[12px] border border-ac-hairline w-full max-w-3xl p-6 shadow-xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-title-md text-ac-ink">New policy</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-ac-muted hover:text-ac-ink text-title-md leading-none"
          >
            ×
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            {mode === "nl" ? (
              <NLComposer
                onCreated={handleCreated}
                onDraftChange={setPreviewScope}
                onWriteManually={() => {
                  setPreviewScope(null);
                  setMode("manual");
                }}
                showManualLink={nlAuthoringEnabled}
              />
            ) : (
              <StructuredEditor onCreated={handleCreated} onScopeChange={setPreviewScope} />
            )}
          </div>
          <PolicyPreviewCard
            policy={previewScope}
            placeholder={mode === "nl" ? "Draft a policy to preview it here." : "Fill in fields to preview the policy here."}
          />
        </div>
      </div>
    </div>
  );
}
