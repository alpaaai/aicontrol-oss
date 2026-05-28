import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { requestCode, verifyCode } from "@/api/auth";
import { useAuth } from "@/hooks/useAuth";

type Step = "email" | "code";

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
    <div className="min-h-screen bg-ac-surface flex items-center justify-center">
      <div className="bg-ac-card border border-ac-border rounded-[12px] p-8 w-full max-w-sm shadow-sm">
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-7 h-7 bg-ac-night rounded-[7px] flex items-center justify-center">
            <div className="w-[11px] h-[11px] bg-ac-primary rounded-[2px]" />
          </div>
          <span className="text-[15px] font-semibold tracking-[-0.01em] text-ac-text-primary">
            AIControl
          </span>
        </div>

        {step === "email" ? (
          <>
            <h2 className="text-[18px] font-semibold tracking-[-0.02em] mb-1 text-ac-text-primary">
              Sign in
            </h2>
            <p className="text-sm text-ac-text-muted mb-6">
              Enter your email to receive a one-time code.
            </p>
            <form onSubmit={handleRequestCode} className="space-y-4">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full border border-ac-border rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary"
              />
              {error && <p className="text-xs text-ac-deny">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-ac-primary/90 transition-colors disabled:opacity-50"
              >
                {loading ? "Sending..." : "Send code"}
              </button>
            </form>
          </>
        ) : (
          <>
            <h2 className="text-[18px] font-semibold tracking-[-0.02em] mb-1 text-ac-text-primary">
              Check your email
            </h2>
            <p className="text-sm text-ac-text-muted mb-6">
              A 6-digit code was sent to <strong>{email}</strong>.
            </p>
            <form onSubmit={handleVerifyCode} className="space-y-4">
              <input
                type="text"
                required
                value={code}
                maxLength={6}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                className="w-full border border-ac-border rounded-lg px-3 py-2.5 text-sm font-mono text-center tracking-[0.2em] outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary"
              />
              {error && <p className="text-xs text-ac-deny">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-ac-primary/90 transition-colors disabled:opacity-50"
              >
                {loading ? "Verifying..." : "Sign in"}
              </button>
              <button
                type="button"
                onClick={() => setStep("email")}
                className="w-full text-sm text-ac-text-muted hover:text-ac-text-primary"
              >
                Use a different email
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
