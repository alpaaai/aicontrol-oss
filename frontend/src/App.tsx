import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { getStoredAuth } from "./store/auth";

import { OverviewPage } from "./pages/overview/OverviewPage";
import { AuditLogPage } from "./pages/audit/AuditLogPage";
import { MetricsPage } from "./pages/metrics/MetricsPage";
import { SessionsPage } from "./pages/sessions/SessionsPage";
import { SessionDetailPage } from "./pages/sessions/SessionDetailPage";
import { PoliciesPage } from "./pages/policies/PoliciesPage";
import { AgentsPage } from "./pages/agents/AgentsPage";
import { TokensPage } from "./pages/tokens/TokensPage";
import { ReviewQueuePage } from "./pages/reviews/ReviewQueuePage";
import { HealthPage } from "./pages/system/HealthPage";
import { ActivityLogPage } from "./pages/system/ActivityLogPage";
import { IntelligencePage } from "./pages/intelligence/IntelligencePage";
import { ReportsPage } from "./pages/reports/ReportsPage";

function RequireAuth({ children }: { children: React.ReactElement }) {
  return getStoredAuth() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
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
          <Route path="tokens"        element={<TokensPage />} />
          <Route path="reviews"       element={<ReviewQueuePage />} />
          <Route path="health"        element={<HealthPage />} />
          <Route path="activity-log"  element={<ActivityLogPage />} />
          <Route path="intelligence"  element={<IntelligencePage />} />
          <Route path="reports"       element={<ReportsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
