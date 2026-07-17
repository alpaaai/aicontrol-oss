import { activateBaseline } from "@/api/policies";

interface Props {
  onClose: () => void;
  onDone: () => void;
}

export function BaselineActivationDialog({ onClose, onDone }: Props) {
  const handleActivate = async (mode: "standard" | "strict") => {
    try {
      await activateBaseline(mode);
    } catch {
      // Non-fatal — user can always activate manually from the Policy Library tab
    }
    sessionStorage.setItem("baseline_offered", "true");
    sessionStorage.removeItem("show_baseline_dialog");
    onDone();
  };

  const handleSkip = () => {
    sessionStorage.setItem("baseline_offered", "true");
    sessionStorage.removeItem("show_baseline_dialog");
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        data-testid="baseline-dialog"
        className="bg-ac-card rounded-[12px] border border-ac-border w-full max-w-lg p-6 shadow-xl space-y-5"
      >
        <div>
          <h3 className="text-[16px] font-semibold text-ac-text-primary">
            Activate a policy baseline
          </h3>
          <p className="text-sm text-ac-text-muted mt-1">
            Start with a curated set of governance policies derived from OWASP LLM Top 10 and
            industry research. You can adjust or deactivate any policy after activation.
          </p>
        </div>

        <div className="space-y-3">
          <div className="border border-ac-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-[14px] text-ac-text-primary">Standard</p>
                <p className="text-[12px] text-ac-text-muted mt-0.5">
                  4 policies — blocks dangerous operations: shell execution, file deletion,
                  cloud metadata access, and sensitive file reads.
                </p>
              </div>
              <button
                data-testid="baseline-standard-btn"
                type="button"
                onClick={() => handleActivate("standard")}
                className="shrink-0 ml-4 bg-ac-primary text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-ac-primary/90"
              >
                Standard
              </button>
            </div>
          </div>

          <div className="border border-ac-border rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-[14px] text-ac-text-primary">Strict</p>
                <p className="text-[12px] text-ac-text-muted mt-0.5">
                  8 policies — Standard plus data protection: wildcard query blocking,
                  large export limits, prompt injection detection, and credential pattern detection.
                </p>
              </div>
              <button
                data-testid="baseline-strict-btn"
                type="button"
                onClick={() => handleActivate("strict")}
                className="shrink-0 ml-4 border border-ac-border text-ac-text-primary text-sm font-medium px-4 py-2 rounded-lg hover:bg-ac-peacock-50"
              >
                Strict
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center pt-1">
          <p className="text-[11px] text-ac-text-muted">
            Industry packs available in the Policy Library tab after setup.
          </p>
          <button
            type="button"
            onClick={handleSkip}
            className="text-sm text-ac-text-muted hover:text-ac-text-primary"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}
