import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { LicenseProvider } from "./context/LicenseContext";
import { OrgSettingsProvider } from "./context/OrgSettingsContext";
import { Layout } from "./components/layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";
import { InvitePage } from "./pages/InvitePage";
import { getStoredAuth } from "./store/auth";
import { getSetupStatus } from "./api/setup";

import { OverviewPage } from "./pages/overview/OverviewPage";
import { AuditLogPage } from "./pages/audit/AuditLogPage";
import { MetricsPage } from "./pages/metrics/MetricsPage";
import { PoliciesPage } from "./pages/policies/PoliciesPage";
import { PolicyDetailPage } from "./pages/policies/PolicyDetailPage";
import { AgentsPage } from "./pages/agents/AgentsPage";
import { AgentDetailPage } from "./pages/agents/AgentDetailPage";
import { TokensPage } from "./pages/tokens/TokensPage";
import { ReviewQueuePage } from "./pages/reviews/ReviewQueuePage";
import { ReportsPage } from "./pages/reports/ReportsPage";
import { SettingsPage } from "./pages/settings/SettingsPage";
import BillingPage from "./pages/BillingPage";
import { DemoPage } from "./pages/demo/DemoPage";
import { Gallery } from "./components/primitives/Gallery";

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
    <LicenseProvider>
    <OrgSettingsProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/invite" element={<InvitePage />} />
        <Route path="/gallery" element={<Gallery />} />
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
          <Route path="audit"         element={<AuditLogPage />} />
          <Route path="metrics"       element={<MetricsPage />} />
          <Route path="policies"      element={<PoliciesPage />} />
          <Route path="policies/:id"  element={<PolicyDetailPage />} />
          <Route path="agents"        element={<AgentsPage />} />
          <Route path="agents/:id"    element={<AgentDetailPage />} />
          <Route path="tokens"        element={<TokensPage />} />
          <Route path="reviews"       element={<ReviewQueuePage />} />
          <Route path="reports"       element={<ReportsPage />} />
          <Route path="settings"      element={<SettingsPage />} />
          <Route path="billing"       element={<BillingPage />} />
          <Route path="demo"          element={<DemoPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </OrgSettingsProvider>
    </LicenseProvider>
  );
}
