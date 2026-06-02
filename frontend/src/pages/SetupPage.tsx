import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Lock, Activity, FileCheck } from "lucide-react";
import { completeSetup } from "@/api/setup";
import { useAuth } from "@/hooks/useAuth";

// IANA timezone list (common subset)
const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "America/Honolulu",
  "America/Sao_Paulo",
  "America/Toronto",
  "America/Vancouver",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Amsterdam",
  "Europe/Stockholm",
  "Europe/Zurich",
  "Europe/Warsaw",
  "Europe/Helsinki",
  "Europe/Istanbul",
  "Europe/Moscow",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Dhaka",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Sydney",
  "Australia/Melbourne",
  "Pacific/Auckland",
];

const trustSignals = [
  { icon: Shield,     text: "Policy-enforced agent control" },
  { icon: Lock,       text: "Zero-trust tool authorization" },
  { icon: Activity,   text: "Real-time audit trail" },
  { icon: FileCheck,  text: "Compliance-ready reporting" },
];

type Step = "org" | "admin";

export function SetupPage() {
  const [step, setStep] = useState<Step>("org");
  const [orgName, setOrgName] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleOrgContinue = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setStep("admin");
  };

  const handleFinish = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await completeSetup({ full_name: fullName, email, password, org_name: orgName, timezone });
      login({ email: data.user.email, role: data.user.role as "admin" | "analyst" | "auditor", token: data.token });
      navigate("/overview");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Setup failed. Please try again.");
    } finally {
      setLoading(false);
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
            First-time setup
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
            Let&rsquo;s get your organization set up.<br />
            This only takes a minute.
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
        <div className="w-full max-w-[380px] animate-fade-up" style={{ animationDelay: "100ms" }}>
          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-8">
            {(["org", "admin"] as Step[]).map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold transition-colors ${
                    step === s
                      ? "bg-ac-primary text-white"
                      : i < (step === "admin" ? 1 : 0)
                      ? "bg-ac-primary/20 text-ac-primary"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {i + 1}
                </div>
                {i < 1 && <div className="w-8 h-px bg-gray-200" />}
              </div>
            ))}
          </div>

          {step === "org" ? (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-1">
                Set up your organization
              </h2>
              <p className="text-[14px] text-ac-text-muted mb-8">
                This information helps configure your workspace.
              </p>
              <form onSubmit={handleOrgContinue} className="space-y-4">
                <div>
                  <label htmlFor="org-name" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Organization name
                  </label>
                  <input
                    id="org-name"
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                <div>
                  <label htmlFor="timezone" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Timezone
                  </label>
                  <select
                    id="timezone"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow bg-white"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </div>
                <button
                  type="submit"
                  className="w-full bg-ac-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-[#3251C5] active:bg-[#2B48B0] transition-colors shadow-sm"
                >
                  Continue
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-[22px] font-bold text-ac-text-primary mb-1">
                Create your admin account
              </h2>
              <p className="text-[14px] text-ac-text-muted mb-8">
                This will be the root admin for <span className="font-medium text-ac-text-primary">{orgName}</span>.
              </p>
              <form onSubmit={handleFinish} className="space-y-4">
                <div>
                  <label htmlFor="full-name" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Full name
                  </label>
                  <input
                    id="full-name"
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Jane Smith"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-[12px] font-medium text-ac-text-muted mb-1.5">
                    Work email
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="jane@company.com"
                    className="w-full border border-ac-border rounded-lg px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-ac-primary/20 focus:border-ac-primary transition-shadow"
                  />
                </div>
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
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
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
                  {loading ? "Setting up…" : "Finish setup"}
                </button>
                <button
                  type="button"
                  onClick={() => setStep("org")}
                  className="w-full text-sm text-ac-text-muted hover:text-ac-text-primary transition-colors"
                >
                  Back
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
