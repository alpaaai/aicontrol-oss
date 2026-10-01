import { useState } from "react";
import { activateBaseline } from "@/api/policies";
import { CheckCircle } from "lucide-react";

interface Props {
  onClose: () => void;
}

export function BaselineDialog({ onClose }: Props) {
  const [activating, setActivating] = useState<"standard" | "strict" | null>(null);
  const [activated, setActivated] = useState<string[] | null>(null);
  const [error, setError] = useState("");

  const handleActivate = async (mode: "standard" | "strict") => {
    setActivating(mode);
    setError("");
    try {
      const result = await activateBaseline(mode);
      setActivated(result.activated);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Failed to activate baseline policies");
    } finally {
      setActivating(null);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-ac-surface-card rounded-[12px] border border-ac-hairline w-full max-w-md p-6 shadow-xl">
        {activated ? (
          <>
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle size={16} className="text-ac-decision-allow" />
              <h3 className="text-[16px] font-semibold text-ac-ink">
                {activated.length} policies activated
              </h3>
            </div>
            <ul className="text-[12px] text-ac-muted space-y-0.5 mb-4 font-mono">
              {activated.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
            <button
              onClick={onClose}
              className="w-full bg-ac-primary text-white rounded-lg py-2 text-sm font-medium"
            >
              Done
            </button>
          </>
        ) : (
          <>
            <h3 className="text-[16px] font-semibold text-ac-ink mb-2">
              Activate a starting policy set
            </h3>
            <p className="text-sm text-ac-muted mb-4">
              Get governance running immediately with a curated set of policies.
              You can add or remove policies any time.
            </p>
            <div className="space-y-2 mb-2">
              <button
                onClick={() => handleActivate("standard")}
                disabled={activating !== null}
                aria-label="Standard"
                className="w-full text-left border border-ac-hairline rounded-lg px-3 py-2.5 hover:bg-ac-surface-sunk disabled:opacity-50"
              >
                <div className="text-sm font-medium text-ac-ink">
                  {activating === "standard" ? "Activating…" : "Standard"}
                </div>
                <div className="text-[12px] text-ac-muted">
                  Blocks shell execution, file deletion, cloud metadata access, sensitive file reads
                </div>
              </button>
              <button
                onClick={() => handleActivate("strict")}
                disabled={activating !== null}
                aria-label="Strict"
                className="w-full text-left border border-ac-hairline rounded-lg px-3 py-2.5 hover:bg-ac-surface-sunk disabled:opacity-50"
              >
                <div className="text-sm font-medium text-ac-ink">
                  {activating === "strict" ? "Activating…" : "Strict"}
                </div>
                <div className="text-[12px] text-ac-muted">
                  Standard, plus wildcard queries, large exports, prompt injection patterns, credential patterns
                </div>
              </button>
            </div>
            {error && <p className="text-xs text-ac-decision-deny mb-2">{error}</p>}
            <button
              onClick={onClose}
              disabled={activating !== null}
              className="w-full border border-ac-hairline rounded-lg py-2 text-sm text-ac-muted hover:bg-ac-surface-sunk disabled:opacity-50"
            >
              Skip for now
            </button>
          </>
        )}
      </div>
    </div>
  );
}
