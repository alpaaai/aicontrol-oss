import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  Lock, LayoutDashboard, List, BarChart2, GitBranch,
  Shield, Bot, Key, CheckSquare, Activity, HeartPulse,
  Brain, Lightbulb, FileCheck, LogOut, Settings, CreditCard,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useLicense } from "../../hooks/useLicense";
import { getSummary } from "../../api/dashboard";

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  locked?: boolean;
  badge?: number;
  delay?: number;
}

function NavItem({ to, icon, label, locked, badge, delay = 0 }: NavItemProps) {
  if (locked) {
    return (
      <div
        className="flex items-center gap-2.5 px-4 py-[7px] text-[13px] text-white/30 cursor-default opacity-50 animate-slide-in-left"
        style={{ animationDelay: `${delay}ms` }}
      >
        <span className="text-white/25 w-[14px] shrink-0">{icon}</span>
        <span>{label}</span>
        <Lock className="w-2.5 h-2.5 ml-auto text-white/20" />
      </div>
    );
  }
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        "flex items-center gap-2.5 px-4 py-[7px] text-[13px] relative transition-all duration-150 animate-slide-in-left group " +
        (isActive
          ? "bg-[#3B5BDB1A] text-[#7C9FFF] font-medium before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:bg-ac-primary before:rounded-r"
          : "text-white/55 hover:bg-white/5 hover:text-white/80 hover:translate-x-0.5")
      }
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="w-[14px] shrink-0 transition-transform duration-150 group-hover:scale-110">{icon}</span>
      <span>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="ml-auto bg-ac-deny-bg text-ac-deny text-[10px] font-medium px-1.5 py-0.5 rounded-full animate-badge-in">
          {badge}
        </span>
      )}
    </NavLink>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="px-4 pt-2.5 pb-1 text-[10px] font-medium uppercase tracking-[0.07em] text-white/30">
      {label}
    </p>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();
  const { isEnterprise } = useLicense();
  const iconProps = { size: 14, strokeWidth: 1.75 };
  const [pendingReviews, setPendingReviews] = useState(0);

  useEffect(() => {
    if (!isEnterprise) return;
    const load = () => getSummary().then(d => setPendingReviews(d.pending_reviews)).catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-[224px] shrink-0 bg-ac-night flex flex-col h-screen sticky top-0 noise overflow-hidden">
      {/* Subtle radial glow behind logo area */}
      <div
        className="pointer-events-none absolute top-0 left-0 w-[200px] h-[120px] opacity-20"
        style={{ background: "radial-gradient(ellipse at 30% 20%, #3B5BDB 0%, transparent 70%)" }}
        aria-hidden
      />

      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-white/[0.07] relative z-10">
        <div
          className="w-[26px] h-[26px] bg-ac-primary rounded-[6px] flex items-center justify-center shrink-0"
          style={{ boxShadow: "0 0 12px rgba(59,91,219,0.55), 0 0 4px rgba(59,91,219,0.3)" }}
        >
          <div className="w-[10px] h-[10px] bg-white/90 rounded-[2px]" />
        </div>
        <span className="text-[13.5px] font-semibold tracking-[-0.01em] text-white font-display">AIControl</span>
        <span className="ml-auto text-[10px] text-white/30">v2</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto scrollbar-hide relative z-10">
        <SectionLabel label="Activity" />
        <NavItem to="/overview"   icon={<LayoutDashboard {...iconProps} />} label="Overview"   delay={40} />
        <NavItem to="/audit-log"  icon={<List {...iconProps} />}            label="Audit Log"  delay={60} />
        <NavItem to="/metrics"    icon={<BarChart2 {...iconProps} />}        label="Metrics"    delay={80} />
        <NavItem to="/sessions"   icon={<GitBranch {...iconProps} />}        label="Sessions"   locked delay={100} />

        <SectionLabel label="Governance" />
        <NavItem to="/policies"   icon={<Shield {...iconProps} />}           label="Policies"   delay={120} />
        <NavItem to="/agents"     icon={<Bot {...iconProps} />}              label="Agents"     delay={140} />
        <NavItem to="/tokens"     icon={<Key {...iconProps} />}              label="API Tokens" delay={160} />

        <SectionLabel label="Reviews" />
        <NavItem to="/reviews" icon={<CheckSquare {...iconProps} />} label="Review Queue"
          locked={!isEnterprise} badge={isEnterprise ? pendingReviews : undefined} delay={180} />

        <SectionLabel label="System" />
        <NavItem to="/health"       icon={<HeartPulse {...iconProps} />}     label="Health"     locked={!isEnterprise} delay={200} />
        <NavItem to="/activity-log" icon={<Activity {...iconProps} />}       label="Activity Log" delay={220} />
        <NavItem to="/billing"      icon={<CreditCard {...iconProps} />}     label="Billing"    delay={235} />

        <SectionLabel label="Intelligence" />
        <NavItem to="/intelligence"       icon={<Brain {...iconProps} />}       label="Threat Summaries"   locked={!isEnterprise} delay={240} />
        <NavItem to="/policy-suggestions" icon={<Lightbulb {...iconProps} />}   label="Policy Suggestions" locked={!isEnterprise} delay={260} />

        <SectionLabel label="Reports" />
        <NavItem to="/reports" icon={<FileCheck {...iconProps} />} label="Compliance" locked={!isEnterprise} delay={280} />
      </nav>

      {/* Settings */}
      <NavLink
        to="/settings"
        className={({ isActive }) =>
          `flex items-center gap-2.5 px-4 py-[7px] text-[13px] transition-all duration-150 border-t border-white/[0.07] relative z-10 group ` +
          (isActive ? 'text-[#7C9FFF]' : 'text-white/40 hover:text-white/60 hover:translate-x-0.5')
        }
      >
        <Settings size={14} strokeWidth={1.75} className="transition-transform duration-150 group-hover:rotate-45" />
        Settings
      </NavLink>

      {/* User row */}
      <div className="border-t border-white/[0.07] px-4 py-3 relative z-10">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-ac-primary flex items-center justify-center text-[10px] font-semibold text-white shrink-0"
            style={{ boxShadow: "0 0 8px rgba(59,91,219,0.4)" }}>
            {user?.email?.[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="min-w-0">
            <p className="text-[12px] text-white/50 truncate">{user?.email}</p>
            <p className="text-[10px] text-white/25">{user?.role}</p>
          </div>
          <button
            data-testid="logout-btn"
            onClick={logout}
            className="ml-auto text-white/20 hover:text-white/50 transition-colors"
          >
            <LogOut size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
