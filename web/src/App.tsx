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
import { ProtocolsPage } from "./pages/ProtocolsPage";
import { QuestionnairesPage } from "./pages/QuestionnairesPage";
import { GuidedConductorPage } from "./pages/GuidedConductorPage";
import { ParticipantViewPage } from "./pages/ParticipantViewPage";
import { ReportPrintPage } from "./pages/ReportPrintPage";
import { SessionReportPage } from "./pages/SessionReportPage";
import { SessionQuestionnairePage } from "./pages/SessionQuestionnairePage";
import { StimuliPage } from "./pages/StimuliPage";
import { ImagesPage } from "./pages/ImagesPage";
import { ImageReviewPage } from "./pages/ImageReviewPage";
import { StatisticsPage } from "./pages/StatisticsPage";
import { DeletionCertificatePage } from "./pages/DeletionCertificatePage";
import { AuditPage } from "./pages/AuditPage";
import { ExamsPage } from "./pages/ExamsPage";
import { ExamPage } from "./pages/ExamPage";
import { StationPage } from "./pages/StationPage";

export function App() {
  return (
    <ExpressionCatalogProvider><AssistantProvider><ActiveSessionProvider><Routes>
      <Route path={paths.login} element={<LoginPage />} />
      {/* Pantalla de la persona evaluada: enlace propio, sin cuenta ni navegación de la aplicación. */}
      <Route path={paths.participantViewPattern} element={<ParticipantViewPage />} />
      <Route path={paths.station} element={<StationPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path={paths.firstAccess} element={<FirstAccessPage />} />
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to={paths.dashboard} replace />} />
          <Route path={paths.dashboard} element={<DashboardPage />} />
          <Route path={paths.commitment} element={<RoleRoute allowed={["student", "psychologist"]}><CommitmentPage /></RoleRoute>} />
          {/* El docente también conduce sesiones propias. */}
          <Route path={paths.analysis} element={<RoleRoute allowed={["student", "psychologist"]}><AnalysisPage /></RoleRoute>} />
          <Route path={paths.sessionReportPattern} element={<RoleRoute allowed={["student", "psychologist"]}><SessionReportPage /></RoleRoute>} />
          <Route path={paths.reportPrintPattern} element={<RoleRoute allowed={["student", "psychologist"]}><ReportPrintPage /></RoleRoute>} />
          <Route path={paths.guidedSessionPattern} element={<RoleRoute allowed={["student", "psychologist"]}><GuidedConductorPage /></RoleRoute>} />
          <Route path={paths.questionnaires} element={<RoleRoute allowed={["student", "psychologist"]}><QuestionnairesPage /></RoleRoute>} />
          <Route path={paths.sessionQuestionnairePattern} element={<RoleRoute allowed={["student", "psychologist"]}><SessionQuestionnairePage /></RoleRoute>} />
          <Route path={paths.protocols} element={<RoleRoute allowed={["student", "psychologist"]}><ProtocolsPage /></RoleRoute>} />
          <Route path={paths.stimuli} element={<RoleRoute allowed={["psychologist", "admin"]}><StimuliPage /></RoleRoute>} />
          <Route path={paths.images} element={<RoleRoute allowed={["student"]}><ImagesPage /></RoleRoute>} />
          <Route path={paths.statistics} element={<RoleRoute allowed={["student", "psychologist"]}><StatisticsPage /></RoleRoute>} />
          <Route path={paths.imageReview} element={<RoleRoute allowed={["psychologist"]}><ImageReviewPage /></RoleRoute>} />
          <Route path={paths.deletionCertificatePattern} element={<RoleRoute allowed={["student", "psychologist"]}><DeletionCertificatePage /></RoleRoute>} />
          <Route path={paths.consent} element={<RoleRoute allowed={["student"]}><ConsentPage /></RoleRoute>} />
          <Route path={paths.activities} element={<ActivitiesPage />} />
          <Route path={paths.activityPattern} element={<ActivityDetailPage />} />
          {/* Sesiones y resultados: solo usuarios y docentes; nunca la administración. */}
          <Route path={paths.sessions} element={<RoleRoute allowed={["student", "psychologist"]}><SessionsPage /></RoleRoute>} />
          <Route path={paths.sessionPattern} element={<RoleRoute allowed={["student", "psychologist"]}><SessionDetailPage /></RoleRoute>} />
          <Route path={paths.exams} element={<RoleRoute allowed={["psychologist"]}><ExamsPage /></RoleRoute>} />
          <Route path={paths.examPattern} element={<RoleRoute allowed={["psychologist"]}><ExamPage /></RoleRoute>} />
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
