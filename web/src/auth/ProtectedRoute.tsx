import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import { Spinner } from "../components/Spinner";
import { ConnectionErrorPage } from "../pages/ConnectionErrorPage";
import { paths } from "../routes/paths";
import { CommitmentProvider, useCommitment } from "../commitment/CommitmentContext";
import { CommitmentModal } from "../commitment/CommitmentModal";

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
 * Usuarios y docentes aceptan una vez el compromiso vigente, en una ventana al
 * entrar. Mientras se consulta no se bloquea la navegación: el servidor rechaza
 * igual iniciar sesiones sin la aceptación.
 */
function CommitmentGate() {
  const { state } = useCommitment();
  return <><Outlet />{state === "required" && <CommitmentModal />}</>;
}
