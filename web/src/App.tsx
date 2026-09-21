import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { RoleRoute } from "./auth/RoleRoute";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ActivitiesPage } from "./pages/ActivitiesPage";
import { ActivityDetailPage } from "./pages/ActivityDetailPage";
import { AdminActivitiesPage } from "./pages/AdminActivitiesPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { ConnectionErrorPage } from "./pages/ConnectionErrorPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SessionsPage } from "./pages/SessionsPage";
import { SessionDetailPage } from "./pages/SessionDetailPage";
import { StudentSessionsPage } from "./pages/StudentSessionsPage";
import { StudentsPage } from "./pages/StudentsPage";
import { UnauthorizedPage } from "./pages/UnauthorizedPage";
import { UsersPage } from "./pages/UsersPage";
import { FirstAccessPage } from "./pages/FirstAccessPage";
import { ConsentPage } from "./pages/ConsentPage";
import { ActiveSessionProvider } from "./analysis/ActiveSessionContext";
import { paths } from "./routes/paths";

export function App() {
  return (
    <ActiveSessionProvider><Routes>
      <Route path={paths.login} element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path={paths.firstAccess} element={<FirstAccessPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to={paths.dashboard} replace />} />
          <Route path={paths.dashboard} element={<DashboardPage />} />
          <Route path={paths.analysis} element={<RoleRoute allowed={["student"]}><AnalysisPage /></RoleRoute>} />
          <Route path={paths.consent} element={<RoleRoute allowed={["student"]}><ConsentPage /></RoleRoute>} />
          <Route path={paths.activities} element={<ActivitiesPage />} />
          <Route path={paths.activityPattern} element={<ActivityDetailPage />} />
          <Route path={paths.sessions} element={<SessionsPage />} />
          <Route path={paths.sessionPattern} element={<SessionDetailPage />} />
          <Route path={paths.students} element={<RoleRoute allowed={["psychologist", "admin"]}><StudentsPage /></RoleRoute>} />
          <Route path={paths.studentSessionsPattern} element={<RoleRoute allowed={["psychologist", "admin"]}><StudentSessionsPage /></RoleRoute>} />
          <Route path={paths.users} element={<RoleRoute allowed={["admin"]}><UsersPage /></RoleRoute>} />
          <Route path={paths.adminActivities} element={<RoleRoute allowed={["admin"]}><AdminActivitiesPage /></RoleRoute>} />
          <Route path={paths.unauthorized} element={<UnauthorizedPage />} />
          <Route path={paths.connectionError} element={<ConnectionErrorPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes></ActiveSessionProvider>
  );
}
