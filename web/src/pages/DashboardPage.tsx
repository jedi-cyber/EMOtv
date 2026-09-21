import { useAuth } from "../auth/useAuth";
import { PageHeader } from "../components/PageHeader";
import { Link } from "react-router-dom";
import { paths } from "../routes/paths";

export function DashboardPage() {
  const { user } = useAuth();
  const descriptions = {
    student: "Selecciona una actividad corporal o revisa tus sesiones.",
    psychologist: "Consulta el seguimiento de estudiantes y sus sesiones autorizadas.",
    admin: "Administra usuarios, actividades y el funcionamiento general de EMOtv.",
  };
  return (
    <section>
      <PageHeader section="Panel principal" title={`Hola, ${user?.email.split("@")[0] ?? ""}`} description={user ? descriptions[user.role] : ""} />
      <div className="card-grid">
        {user?.role === "student" && <article className="card"><h2>Analizador facial</h2><p>Reconoce tu expresión y recibe una actividad sugerida.</p><Link className="text-link" to={paths.analysis}>Abrir analizador</Link></article>}
        {user?.role === "psychologist" && <article className="card"><h2>Estudiantes</h2><p>Accede al seguimiento con los permisos correspondientes.</p><Link className="text-link" to={paths.students}>Ver estudiantes</Link></article>}
        {user?.role === "admin" && <article className="card"><h2>Usuarios</h2><p>Supervisa las cuentas y sus roles de acceso.</p><Link className="text-link" to={paths.users}>Ver usuarios</Link></article>}
        <article className="card"><h2>Actividades</h2><p>Explora las posturas y ejercicios disponibles.</p><Link className="text-link" to={user?.role === "admin" ? paths.adminActivities : paths.activities}>{user?.role === "admin" ? "Administrar actividades" : "Ver actividades"}</Link></article>
        <article className="card"><h2>Sesiones</h2><p>Consulta el progreso y los resultados registrados.</p><Link className="text-link" to={paths.sessions}>Ver sesiones</Link></article>
      </div>
    </section>
  );
}
