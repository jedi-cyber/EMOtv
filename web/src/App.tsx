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
import { AssistantWidget } from "./components/AssistantWidget";
import { AssistantProvider } from "./components/AssistantContext";
import { ExpressionCatalogProvider } from "./expressions/ExpressionCatalog";
import { AdminExpressionsPage } from "./pages/AdminExpressionsPage";
import { AdminModelsPage } from "./pages/AdminModelsPage";
import { CommitmentPage } from "./pages/CommitmentPage";
import { ParticipantsPage } from "./pages/ParticipantsPage";
import { DeletionCertificatePage } from "./pages/DeletionCertificatePage";
import { AuditPage } from "./pages/AuditPage";

export function App() {
  return (
    <ExpressionCatalogProvider><AssistantProvider><ActiveSessionProvider><Routes>
      <Route path={paths.login} element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path={paths.firstAccess} element={<FirstAccessPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to={paths.dashboard} replace />} />
          <Route path={paths.dashboard} element={<DashboardPage />} />
          <Route path={paths.commitment} element={<RoleRoute allowed={["student", "psychologist"]}><CommitmentPage /></RoleRoute>} />
          {/* El docente también conduce sesiones propias. */}
          <Route path={paths.analysis} element={<RoleRoute allowed={["student", "psychologist"]}><AnalysisPage /></RoleRoute>} />
          <Route path={paths.participants} element={<RoleRoute allowed={["student", "psychologist"]}><ParticipantsPage /></RoleRoute>} />
          <Route path={paths.deletionCertificatePattern} element={<RoleRoute allowed={["student", "psychologist"]}><DeletionCertificatePage /></RoleRoute>} />
          <Route path={paths.consent} element={<RoleRoute allowed={["student"]}><ConsentPage /></RoleRoute>} />
          <Route path={paths.activities} element={<ActivitiesPage />} />
          <Route path={paths.activityPattern} element={<ActivityDetailPage />} />
          {/* Sesiones y resultados: solo usuarios y docentes; nunca la administración. */}
          <Route path={paths.sessions} element={<RoleRoute allowed={["student", "psychologist"]}><SessionsPage /></RoleRoute>} />
          <Route path={paths.sessionPattern} element={<RoleRoute allowed={["student", "psychologist"]}><SessionDetailPage /></RoleRoute>} />
          <Route path={paths.students} element={<RoleRoute allowed={["psychologist"]}><StudentsPage /></RoleRoute>} />
          <Route path={paths.studentSessionsPattern} element={<RoleRoute allowed={["psychologist"]}><StudentSessionsPage /></RoleRoute>} />
          <Route path={paths.users} element={<RoleRoute allowed={["admin", "superadmin"]}><UsersPage /></RoleRoute>} />
          <Route path={paths.audit} element={<RoleRoute allowed={["admin", "superadmin"]}><AuditPage /></RoleRoute>} />
          <Route path={paths.adminActivities} element={<RoleRoute allowed={["superadmin"]}><AdminActivitiesPage /></RoleRoute>} />
          <Route path={paths.adminExpressions} element={<RoleRoute allowed={["superadmin"]}><AdminExpressionsPage /></RoleRoute>} />
          <Route path={paths.adminModels} element={<RoleRoute allowed={["superadmin"]}><AdminModelsPage /></RoleRoute>} />
          <Route path={paths.unauthorized} element={<UnauthorizedPage />} />
          <Route path={paths.connectionError} element={<ConnectionErrorPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes><AssistantWidget /></ActiveSessionProvider></AssistantProvider></ExpressionCatalogProvider>
  );
}
