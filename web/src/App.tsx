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

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="analysis" element={<RoleRoute allowed={["student"]}><AnalysisPage /></RoleRoute>} />
          <Route path="activities" element={<ActivitiesPage />} />
          <Route path="activities/:activityId" element={<ActivityDetailPage />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/:sessionId" element={<SessionDetailPage />} />
          <Route path="students" element={<RoleRoute allowed={["psychologist", "admin"]}><StudentsPage /></RoleRoute>} />
          <Route path="students/:studentId/sessions" element={<RoleRoute allowed={["psychologist", "admin"]}><StudentSessionsPage /></RoleRoute>} />
          <Route path="users" element={<RoleRoute allowed={["admin"]}><UsersPage /></RoleRoute>} />
          <Route path="admin/activities" element={<RoleRoute allowed={["admin"]}><AdminActivitiesPage /></RoleRoute>} />
          <Route path="unauthorized" element={<UnauthorizedPage />} />
          <Route path="connection-error" element={<ConnectionErrorPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
