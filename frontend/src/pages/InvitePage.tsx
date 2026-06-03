import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Shield, Lock, Activity, FileCheck } from "lucide-react";
import { validateMagicLink, setPassword } from "@/api/invite";
import { useAuth } from "@/hooks/useAuth";

const trustSignals = [
  { icon: Shield,     text: "Policy-enforced agent control" },
  { icon: Lock,       text: "Zero-trust tool authorization" },
  { icon: Activity,   text: "Real-time audit trail" },
  { icon: FileCheck,  text: "Compliance-ready reporting" },
];

type State =
  | { status: "loading" }
  | { status: "invalid"; message: string }
  | { status: "ready"; email: string; full_name: string }
  | { status: "submitting"; email: string; full_name: string };

export function InvitePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const { login } = useAuth();

  const [state, setState] = useState<State>({ status: "loading" });
  const [password, setPasswordValue] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (!token) {
      setState({ status: "invalid", message: "Invalid or expired invite link" });
      return;
    }
    validateMagicLink(token)
      .then(({ data }) => {
        setState({ status: "ready", email: data.email, full_name: data.full_name });
      })
      .catch(() => {
        setState({ status: "invalid", message: "Invalid or expired invite link" });
      });
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (password !== confirm) {
      setFormError("Passwords do not match");
      return;
    }
    if (state.status !== "ready") return;
    setState({ status: "submitting", email: state.email, full_name: state.full_name });
    try {
      const { data } = await setPassword(token, password);
      login({
        id: data.user.id,
        email: data.user.email,
        role: data.user.role as "admin" | "analyst" | "auditor",
        token: data.token,
      });
      navigate("/overview");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Failed to set password. The link may have expired.");
      setState({ status: "ready", email: state.email, full_name: state.full_name });
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div
        className="hidden lg:flex lg:w-[52%] flex-col justify-between p-12 relative overflow-hidden noise"
        style={{ background: "#0B0E17" }}
      >
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 20% 30%, rgba(59,91,219,0.18) 0%, transparent 55%), " +
              "radial-gradient(ellipse at 80% 70%, rgba(83,74,183,0.12) 0%, transparent 50%)",
          }}
          aria-hidden
        />

        <div className="flex items-center gap-3 relative z-10 animate-fade-up" style={{ animationDelay: "0ms" }}>
          <div
            className="w-9 h-9 bg-ac-primary rounded-[9px] flex items-center justify-center"
            style={{ boxShadow: "0 0 20px rgba(59,91,219,0.5)" }}
          >
            <div className="w-[14px] h-[14px] bg-white/90 rounded-[3px]" />
          </div>
          <span className="text-white text-[17px] font-semibold tracking-[-0.01em] font-display">AIControl</span>
        </div>

        <div className="relative z-10">
          <p
            className="text-[11px] font-medium uppercase tracking-[0.12em] text-ac-primary-lt mb-4 animate-fade-up"
            style={{ animationDelay: "80ms" }}
          >
            You&rsquo;ve been invited
          </p>
          <h1
            className="text-[38px] leading-[1.1] font-bold text-white mb-6 animate-fade-up"
            style={{ animationDelay: "140ms" }}
          >
            Welcome to<br />
            AIControl.
          </h1>
          <p
            className="text-white/50 text-[15px] leading-relaxed mb-10 animate-fade-up"
            style={{ animationDelay: "200ms" }}
          >
            Set a password to activate your account<br />
            and start governing your AI agents.
          </p>

          <div className="space-y-3">
            {trustSignals.map(({ icon: Icon, text }, i) => (
              <div
                key={text}
                className="flex items-center gap-3 animate-fade-up"
                style={{ animationDelay: `${260 + i * 60}ms` }}
              >
                <div className="w-7 h-7 rounded-md bg-white/[0.06] border border-white/[0.08] flex items-center justify-center shrink-0">
                  <Icon size={13} className="text-ac-primary-lt" />
                </div>
                <span className="text-white/60 text-[13px]">{text}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-white/20 text-[11px] relative z-10 animate-fade-up" style={{ animationDelay: "600ms" }}>
          Trusted by enterprise AI teams
        </p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-[360px] animate-fade-up" style={{ animationDelay: "100ms" }}>
          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <div className="w-7 h-7 bg-ac-night rounded-[7px] flex items-center justify-center">
              <div className="w-[11px] h-[11px] bg-ac-primary rounded-[2px]" />
            </div>
            <span className="text-[15px] font-semibold tracking-[-0.01em] text-ac-text-primary font-display">
              AIControl
            </span>
          </div>

          {state.status === "loading" && (
            <p className="text-sm text-ac-text-muted">Verifying your invite link…</p>
          )}

          {state.status === "invalid" && (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-2">Link invalid</h2>
              <p className="text-sm text-ac-deny">{state.message}</p>
              <p className="mt-4 text-sm text-ac-text-muted">
                Ask your administrator to resend the invite.
              </p>
            </>
          )}

          {(state.status === "ready" || state.status === "submitting") && (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-1">Set your password</h2>
              <p className="text-[14px] text-ac-text-muted mb-2">
                You&rsquo;re signing in as{" "}
                <span className="font-medium text-ac-text-primary">{state.email}</span>.
              </p>
              <p className="text-[13px] text-ac-text-muted mb-8">
                Choose a password to activate your account.
              </p>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="password" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPasswordValue(e.target.value)}
                    placeholder="At least 8 characters"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                <div>
                  <label htmlFor="confirm" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Confirm password
                  </label>
                  <input
                    id="confirm"
                    type="password"
                    required
                    minLength={8}
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder="Repeat your password"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                {formError && (
                  <p className="text-xs text-ac-deny bg-ac-deny-bg rounded-md px-3 py-2">{formError}</p>
                )}
                <button
                  type="submit"
                  disabled={state.status === "submitting"}
                  className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-[#3251C5] active:bg-[#2B48B0] transition-colors disabled:opacity-50 shadow-sm"
                >
                  {state.status === "submitting" ? "Setting up…" : "Set password"}
                </button>
              </form>
            </>
          )}

          <p className="mt-10 text-[11px] text-ac-text-muted/60 text-center">
            Secured by AIControl · Enterprise tier
          </p>
        </div>
      </div>
    </div>
  );
}
