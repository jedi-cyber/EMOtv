import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import type { UserRole } from "./types";
import { useAuth } from "./useAuth";

interface RoleRouteProps extends PropsWithChildren {
  allowed: readonly UserRole[];
}

export function RoleRoute({ allowed, children }: RoleRouteProps) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!allowed.includes(user.role)) return <Navigate to="/unauthorized" replace />;
  return children;
}
