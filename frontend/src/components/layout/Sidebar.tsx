import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { getLicenseFeatures, type FeatureFlags } from "../../api/license";
import { useOrgSettings } from "../../context/OrgSettingsContext";

type NavItem = { label: string; path: string; requires?: keyof FeatureFlags };

const NAV_ITEMS: NavItem[] = [
  { label: "Overview",  path: "/overview" },
  { label: "Agents",    path: "/agents" },
  { label: "Policies",  path: "/policies" },
  { label: "Audit log", path: "/audit" },
  { label: "Reviews",   path: "/reviews", requires: "hitl" },
  { label: "Policy Drift", path: "/drift" },
  { label: "Metrics",   path: "/metrics" },
  { label: "Reports",   path: "/reports", requires: "compliance_reports" },
  { label: "Billing",   path: "/billing", requires: "compliance_reports" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const { orgName } = useOrgSettings();
  const [features, setFeatures] = useState<FeatureFlags | null>(null);

  useEffect(() => {
    getLicenseFeatures()
      .then((r) => setFeatures(r.features))
      .catch(() => {});
  }, []);

  const items = NAV_ITEMS.filter(
    (item) => !item.requires || features?.[item.requires],
  );

  return (
    <div className="w-[224px] shrink-0 bg-ac-canvas border-r border-ac-hairline flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2 px-4 py-4 border-b border-ac-hairline">
        <div className="w-[26px] h-[26px] bg-ac-primary rounded-md flex items-center justify-center shrink-0">
          <div className="w-[10px] h-[10px] bg-ac-on-primary rounded-[2px]" />
        </div>
        <span className="text-title-md text-ac-ink font-display truncate">
          {orgName || "AIControl"}
        </span>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden" aria-label="Primary">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              "relative block mx-2 my-0.5 px-3 py-2 text-nav-link rounded-sm transition-colors duration-standard " +
              "before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:rounded-full before:transition-opacity before:duration-standard " +
              (isActive
                ? "bg-ac-surface-sunk text-ac-ink before:bg-ac-primary before:opacity-100"
                : "text-ac-body before:opacity-0 hover:text-ac-ink hover:bg-ac-surface-sunk")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-ac-hairline px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-ac-primary flex items-center justify-center text-[10px] font-semibold text-ac-on-primary shrink-0">
            {user?.email?.[0]?.toUpperCase() ?? "A"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-caption text-ac-body truncate">{user?.email}</p>
            <p className="text-[10px] text-ac-muted">{user?.role}</p>
          </div>
          <button
            data-testid="logout-btn"
            onClick={logout}
            className="text-ac-muted hover:text-ac-ink transition-colors duration-standard shrink-0"
            title="Logout"
          >
            <LogOut size={14} strokeWidth={1.75} />
          </button>
        </div>
      </div>
    </div>
  );
}
