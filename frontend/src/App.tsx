import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { LicenseProvider } from "./context/LicenseContext";
import { OrgSettingsProvider } from "./context/OrgSettingsContext";
import { ThemeProvider } from "./context/ThemeContext";
import { Layout } from "./components/layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";
import { InvitePage } from "./pages/InvitePage";
import { getStoredAuth } from "./store/auth";
import { getSetupStatus } from "./api/setup";

import { OverviewPage } from "./pages/overview/OverviewPage";
import { AuditLogPage } from "./pages/audit/AuditLogPage";
import { MetricsPage } from "./pages/metrics/MetricsPage";
import { SessionsPage } from "./pages/sessions/SessionsPage";
import { SessionDetailPage } from "./pages/sessions/SessionDetailPage";
import { PoliciesPage } from "./pages/policies/PoliciesPage";
import { AgentsPage } from "./pages/agents/AgentsPage";
import { AdmissionScansPage } from "./pages/admission/AdmissionScansPage";
import { TokensPage } from "./pages/tokens/TokensPage";
import { ReviewQueuePage } from "./pages/reviews/ReviewQueuePage";
import { HealthPage } from "./pages/system/HealthPage";
import { ActivityLogPage } from "./pages/system/ActivityLogPage";
import { IntelligencePage } from "./pages/intelligence/IntelligencePage";
import { ReportsPage } from "./pages/reports/ReportsPage";
import { SettingsPage } from "./pages/settings/SettingsPage";
import BillingPage from "./pages/BillingPage";
import { DemoPage } from "./pages/demo/DemoPage";

function RequireSetupOrAuth({ children }: { children: React.ReactElement }) {
  const auth = getStoredAuth();
  const [redirect, setRedirect] = useState<string | null>(null);

  useEffect(() => {
    if (auth) return;
    getSetupStatus()
      .then(({ data }) => {
        setRedirect(data.setup_required ? "/setup" : "/login");
      })
      .catch(() => setRedirect("/login"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (auth) return children;
  if (redirect) return <Navigate to={redirect} replace />;
  return null;
}

export default function App() {
  return (
    <ThemeProvider>
    <LicenseProvider>
    <OrgSettingsProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/invite" element={<InvitePage />} />
        <Route
          path="/"
          element={
            <RequireSetupOrAuth>
              <Layout />
            </RequireSetupOrAuth>
          }
        >
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview"      element={<OverviewPage />} />
          <Route path="audit-log"     element={<AuditLogPage />} />
          <Route path="metrics"       element={<MetricsPage />} />
          <Route path="sessions"      element={<SessionsPage />} />
          <Route path="sessions/:id"  element={<SessionDetailPage />} />
          <Route path="policies"      element={<PoliciesPage />} />
          <Route path="agents"        element={<AgentsPage />} />
          <Route path="admission-scans" element={<AdmissionScansPage />} />
          <Route path="tokens"        element={<TokensPage />} />
          <Route path="reviews"       element={<ReviewQueuePage />} />
          <Route path="health"        element={<HealthPage />} />
          <Route path="activity-log"  element={<ActivityLogPage />} />
          <Route path="intelligence"  element={<IntelligencePage />} />
          <Route path="reports"       element={<ReportsPage />} />
          <Route path="settings"      element={<SettingsPage />} />
          <Route path="billing"       element={<BillingPage />} />
          <Route path="demo"          element={<DemoPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </OrgSettingsProvider>
    </LicenseProvider>
    </ThemeProvider>
  );
}
