import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { requestCode, verifyCode } from "@/api/auth";
import { useAuth } from "@/hooks/useAuth";
import { Shield, Lock, Activity, FileCheck } from "lucide-react";

type Step = "email" | "code";

const trustSignals = [
  { icon: Shield,     text: "Policy-enforced agent control" },
  { icon: Lock,       text: "Zero-trust tool authorization" },
  { icon: Activity,   text: "Real-time audit trail" },
  { icon: FileCheck,  text: "Compliance-ready reporting" },
];

export function LoginPage() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleRequestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await requestCode(email);
      setStep("code");
    } catch {
      setError("Email not found. Contact your administrator.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await verifyCode(email, code);
      login({ email: data.email, role: data.role as "admin" | "analyst" | "auditor", token: data.token });
      navigate("/overview");
    } catch {
      setError("Invalid or expired code. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel — dark, brand, trust signals */}
      <div
        className="hidden lg:flex lg:w-[52%] flex-col justify-between p-12 relative overflow-hidden noise"
        style={{ background: "#0B0E17" }}
      >
        {/* Background mesh */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 20% 30%, rgba(59,91,219,0.18) 0%, transparent 55%), " +
              "radial-gradient(ellipse at 80% 70%, rgba(83,74,183,0.12) 0%, transparent 50%)",
          }}
          aria-hidden
        />

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10 animate-fade-up" style={{ animationDelay: "0ms" }}>
          <div
            className="w-9 h-9 bg-ac-primary rounded-[9px] flex items-center justify-center"
            style={{ boxShadow: "0 0 20px rgba(59,91,219,0.5)" }}
          >
            <div className="w-[14px] h-[14px] bg-white/90 rounded-[3px]" />
          </div>
          <span className="text-white text-[17px] font-semibold tracking-[-0.01em] font-display">AIControl</span>
        </div>

        {/* Main copy */}
        <div className="relative z-10">
          <p
            className="text-[11px] font-medium uppercase tracking-[0.12em] text-ac-primary-lt mb-4 animate-fade-up"
            style={{ animationDelay: "80ms" }}
          >
            Enterprise AI Governance
          </p>
          <h1
            className="text-[38px] leading-[1.1] font-bold text-white mb-6 animate-fade-up"
            style={{ animationDelay: "140ms" }}
          >
            Every AI action,<br />
            accounted for.
          </h1>
          <p
            className="text-white/50 text-[15px] leading-relaxed mb-10 animate-fade-up"
            style={{ animationDelay: "200ms" }}
          >
            Intercept, review, and enforce policies across<br />
            your entire AI agent fleet in real time.
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

        {/* Bottom label */}
        <p className="text-white/20 text-[11px] relative z-10 animate-fade-up" style={{ animationDelay: "600ms" }}>
          Trusted by enterprise AI teams
        </p>
      </div>

      {/* Right panel — white, form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-[360px] animate-fade-up" style={{ animationDelay: "100ms" }}>
          {/* Mobile-only logo */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <div className="w-7 h-7 bg-ac-night rounded-[7px] flex items-center justify-center">
              <div className="w-[11px] h-[11px] bg-ac-primary rounded-[2px]" />
            </div>
            <span className="text-[15px] font-semibold tracking-[-0.01em] text-ac-text-primary font-display">
              AIControl
            </span>
          </div>

          {step === "email" ? (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-1">
                Sign in
              </h2>
              <p className="text-[14px] text-ac-text-muted mb-8">
                Enter your work email to receive a one-time code.
              </p>
              <form onSubmit={handleRequestCode} className="space-y-4">
                <div>
                  <label className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Work email
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                {error && (
                  <p className="text-xs text-ac-deny bg-ac-deny-bg rounded-md px-3 py-2">{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-[#3251C5] active:bg-[#2B48B0] transition-colors disabled:opacity-50 shadow-sm"
                >
                  {loading ? "Sending…" : "Continue"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-1">
                Check your email
              </h2>
              <p className="text-[14px] text-ac-text-muted mb-8">
                A 6-digit code was sent to{" "}
                <span className="font-medium text-ac-text-primary">{email}</span>.
              </p>
              <form onSubmit={handleVerifyCode} className="space-y-4">
                <div>
                  <label className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    One-time code
                  </label>
                  <input
                    type="text"
                    required
                    value={code}
                    maxLength={6}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="000000"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm font-mono text-center tracking-[0.25em] outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                {error && (
                  <p className="text-xs text-ac-deny bg-ac-deny-bg rounded-md px-3 py-2">{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-[#3251C5] active:bg-[#2B48B0] transition-colors disabled:opacity-50 shadow-sm"
                >
                  {loading ? "Verifying…" : "Sign in"}
                </button>
                <button
                  type="button"
                  onClick={() => setStep("email")}
                  className="w-full text-sm text-ac-text-muted hover:text-ac-text-primary transition-colors"
                >
                  Use a different email
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
