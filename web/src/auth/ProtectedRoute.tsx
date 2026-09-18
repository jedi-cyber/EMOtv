import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./useAuth";
import { Spinner } from "../components/Spinner";
import { ConnectionErrorPage } from "../pages/ConnectionErrorPage";
import { paths } from "../routes/paths";

export function ProtectedRoute() {
  const { user, loading, connectionError } = useAuth();
  const location = useLocation();

  if (loading) return <main className="centered"><Spinner label="Verificando sesión" /></main>;
  if (connectionError) return <main className="centered"><ConnectionErrorPage /></main>;
  if (!user) return <Navigate to={paths.login} replace state={{ from: location }} />;
  if (user.must_change_password && location.pathname !== paths.firstAccess)
    return <Navigate to={paths.firstAccess} replace />;
  if (!user.must_change_password && location.pathname === paths.firstAccess)
    return <Navigate to={paths.dashboard} replace />;
  return <Outlet />;
}
