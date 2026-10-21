import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import { Spinner } from "../components/Spinner";
import { ConnectionErrorPage } from "../pages/ConnectionErrorPage";
import { paths } from "../routes/paths";
import { CommitmentProvider, useCommitment } from "../commitment/CommitmentContext";

export function ProtectedRoute() {
  const { user, loading, connectionError } = useAuth();
  const location = useLocation();

  if (loading) return <main className="centered"><Spinner label="Verificando sesión" /></main>;
  if (connectionError) return <main className="centered"><ConnectionErrorPage /></main>;
  if (!user) return <Navigate to={paths.login} replace state={{ from: location }} />;
  if (user.must_change_password && location.pathname !== paths.firstAccess)
    return <Navigate to={paths.firstAccess} replace />;
  if (user.must_change_password) return <Outlet />;
  // Tras el primer acceso, el usuario continúa en el compromiso y el consentimiento.
  if (location.pathname === paths.firstAccess)
    return <Navigate to={user.role === "student" ? paths.consent : paths.dashboard} replace />;
  return <CommitmentProvider><CommitmentGate /></CommitmentProvider>;
}

/**
 * Usuarios y docentes aceptan el compromiso vigente antes de seguir. Mientras
 * se consulta no se bloquea la navegación: el servidor rechaza igual registrar
 * participantes o iniciar sesiones sin la aceptación.
 */
function CommitmentGate() {
  const { state } = useCommitment();
  const location = useLocation();
  if (state === "required" && location.pathname !== paths.commitment)
    return <Navigate to={paths.commitment} replace state={{ from: location }} />;
  return <Outlet />;
}
