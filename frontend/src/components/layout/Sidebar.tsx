import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  Lock, LayoutDashboard, List, BarChart2, GitBranch,
  Shield, Bot, Key, CheckSquare, Activity,
  Brain, Lightbulb, FileCheck, LogOut, Settings, CreditCard,
  Layers, ShieldCheck, ClipboardList, BarChart3, Sparkles,
  ChevronRight, HeartPulse, SlidersHorizontal,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useLicense } from "../../hooks/useLicense";
import { getSummary } from "../../api/dashboard";

const SECTION_PATHS: Record<string, string[]> = {
  activity:     ["/overview", "/audit-log", "/metrics", "/sessions", "/activity-log"],
  governance:   ["/policies", "/agents", "/tokens"],
  reviews:      ["/reviews"],
  reports:      ["/reports"],
  intelligence: ["/intelligence", "/policy-suggestions"],
  admin:        ["/health", "/settings", "/billing"],
};

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  locked?: boolean;
  badge?: number;
}

function NavItem({ to, icon, label, locked, badge }: NavItemProps) {
  if (locked) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-[7px] text-[13px] text-white/30 cursor-default opacity-50">
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
        "flex items-center gap-2.5 px-4 py-[7px] text-[13px] relative transition-all duration-150 group " +
        (isActive
          ? "bg-[#3B5BDB1A] text-[#7C9FFF] font-medium before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:bg-ac-primary before:rounded-r"
          : "text-white/55 hover:bg-white/5 hover:text-white/80 hover:translate-x-0.5")
      }
    >
      <span className="w-[14px] shrink-0 transition-transform duration-150 group-hover:scale-110">{icon}</span>
      <span>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="ml-auto bg-ac-deny-bg text-ac-deny text-[10px] font-medium px-1.5 py-0.5 rounded-full">
          {badge}
        </span>
      )}
    </NavLink>
  );
}

interface SectionHeaderProps {
  icon: React.ReactNode;
  label: string;
  isOpen: boolean;
  onClick: () => void;
}

function SectionHeader({ icon, label, isOpen, onClick }: SectionHeaderProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-4 pt-2.5 pb-1 text-[10px] font-medium uppercase tracking-[0.07em] transition-colors duration-150 ${
        isOpen ? "text-white" : "text-white/35 hover:text-white/60"
      }`}
    >
      <span className={`w-[14px] shrink-0 transition-opacity duration-150 ${isOpen ? "opacity-100" : "opacity-35"}`}>
        {icon}
      </span>
      <span>{label}</span>
      <ChevronRight
        size={10}
        strokeWidth={2}
        className={`ml-auto transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
      />
    </button>
  );
}

export function Sidebar() {
  const { user, logout } = useAuth();
  const { isEnterprise } = useLicense();
  const location = useLocation();
  const iconProps = { size: 14, strokeWidth: 1.75 };
  const [openSection, setOpenSection] = useState<string | null>(null);
  const [pendingReviews, setPendingReviews] = useState(0);

  // Auto-open section containing the active route
  useEffect(() => {
    const match = Object.entries(SECTION_PATHS).find(([, paths]) =>
      paths.some(p => location.pathname === p || location.pathname.startsWith(p + "/"))
    );
    if (match) setOpenSection(match[0]);
  }, [location.pathname]);

  useEffect(() => {
    if (!isEnterprise) return;
    const load = () => getSummary().then(d => setPendingReviews(d.pending_reviews)).catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const toggleSection = (key: string) =>
    setOpenSection(prev => (prev === key ? null : key));

  return (
    <div className="w-[224px] shrink-0 bg-ac-night flex flex-col h-screen sticky top-0 noise">
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
      <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden scrollbar-hide relative z-10">
        {/* ACTIVITY */}
        <SectionHeader
          icon={<Layers {...iconProps} />}
          label="Activity"
          isOpen={openSection === "activity"}
          onClick={() => toggleSection("activity")}
        />
        {openSection === "activity" && (
          <div className="animate-fade-up pb-1">
            <NavItem to="/overview"     icon={<LayoutDashboard {...iconProps} />} label="Dashboard" />
            <NavItem to="/audit-log"    icon={<List {...iconProps} />}            label="Agent activity" />
            <NavItem to="/metrics"      icon={<BarChart2 {...iconProps} />}       label="Decision metrics" />
            <NavItem to="/activity-log" icon={<Activity {...iconProps} />}        label="Activity audit" />
            <NavItem to="/sessions"     icon={<GitBranch {...iconProps} />}       label="Sessions" locked />
          </div>
        )}

        {/* GOVERNANCE */}
        <SectionHeader
          icon={<ShieldCheck {...iconProps} />}
          label="Governance"
          isOpen={openSection === "governance"}
          onClick={() => toggleSection("governance")}
        />
        {openSection === "governance" && (
          <div className="animate-fade-up pb-1">
            <NavItem to="/policies" icon={<Shield {...iconProps} />} label="Policies" />
            <NavItem to="/agents"   icon={<Bot {...iconProps} />}    label="Agents" />
            <NavItem to="/tokens"   icon={<Key {...iconProps} />}    label="API tokens" />
          </div>
        )}

        {/* MANUAL REVIEWS */}
        <SectionHeader
          icon={<ClipboardList {...iconProps} />}
          label="Manual Reviews"
          isOpen={openSection === "reviews"}
          onClick={() => toggleSection("reviews")}
        />
        {openSection === "reviews" && (
          <div className="animate-fade-up pb-1">
            <NavItem
              to="/reviews"
              icon={<CheckSquare {...iconProps} />}
              label="Review queue"
              locked={!isEnterprise}
              badge={isEnterprise ? pendingReviews : undefined}
            />
          </div>
        )}

        {/* REPORTS */}
        <SectionHeader
          icon={<BarChart3 {...iconProps} />}
          label="Reports"
          isOpen={openSection === "reports"}
          onClick={() => toggleSection("reports")}
        />
        {openSection === "reports" && (
          <div className="animate-fade-up pb-1">
            <NavItem to="/reports" icon={<FileCheck {...iconProps} />} label="Compliance" locked={!isEnterprise} />
          </div>
        )}

        {/* INTELLIGENCE */}
        <SectionHeader
          icon={<Sparkles {...iconProps} />}
          label="Intelligence"
          isOpen={openSection === "intelligence"}
          onClick={() => toggleSection("intelligence")}
        />
        {openSection === "intelligence" && (
          <div className="animate-fade-up pb-1">
            <NavItem to="/intelligence"       icon={<Brain {...iconProps} />}     label="Threat summaries" locked={!isEnterprise} />
            <NavItem to="/policy-suggestions" icon={<Lightbulb {...iconProps} />} label="Policy insights"  locked={!isEnterprise} />
          </div>
        )}

        {/* ADMIN */}
        <SectionHeader
          icon={<SlidersHorizontal {...iconProps} />}
          label="Admin"
          isOpen={openSection === "admin"}
          onClick={() => toggleSection("admin")}
        />
        {openSection === "admin" && (
          <div className="animate-fade-up pb-1">
            <NavItem to="/health"   icon={<HeartPulse {...iconProps} />} label="System health" />
            <NavItem to="/settings" icon={<Settings {...iconProps} />}   label="Settings" />
            <NavItem to="/billing"  icon={<CreditCard {...iconProps} />} label="Subscription" />
          </div>
        )}
      </nav>

      {/* User row */}
      <div className="border-t border-white/[0.07] px-4 py-3">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-full bg-ac-primary flex items-center justify-center text-[10px] font-semibold text-white shrink-0"
            style={{ boxShadow: "0 0 8px rgba(59,91,219,0.4)" }}
          >
            {user?.email?.[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[12px] text-white/50 truncate">{user?.email}</p>
            <p className="text-[10px] text-white/25">{user?.role}</p>
          </div>
          <button
            data-testid="logout-btn"
            onClick={logout}
            className="text-white/30 hover:text-white/70 transition-colors duration-150 shrink-0"
            title="Logout"
          >
            <LogOut size={14} strokeWidth={1.75} />
          </button>
        </div>
      </div>
    </div>
  );
}
