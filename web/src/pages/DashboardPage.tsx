import { useAuth } from "../auth/useAuth";
import { PageHeader } from "../components/PageHeader";
import { ButtonLink } from "../components/Button";
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
      <PageHeader title={`Hola, ${user?.email.split("@")[0] ?? ""}`} description={user ? descriptions[user.role] : ""} />
      <div className="card-grid">
        {user?.role === "student" && <article className="card"><h2>Analizador facial</h2><p>Reconoce tu expresión y recibe una actividad sugerida.</p><ButtonLink variant="secondary" className="card-action" to={paths.analysis}>Abrir analizador</ButtonLink></article>}
        {user?.role === "psychologist" && <article className="card"><h2>Estudiantes</h2><p>Accede al seguimiento con los permisos correspondientes.</p><ButtonLink variant="secondary" className="card-action" to={paths.students}>Ver estudiantes</ButtonLink></article>}
        {user?.role === "admin" && <article className="card"><h2>Usuarios</h2><p>Supervisa las cuentas y sus roles de acceso.</p><ButtonLink variant="secondary" className="card-action" to={paths.users}>Ver usuarios</ButtonLink></article>}
        <article className="card"><h2>Actividades</h2><p>Explora las posturas y ejercicios disponibles.</p><ButtonLink variant="secondary" className="card-action" to={user?.role === "admin" ? paths.adminActivities : paths.activities}>{user?.role === "admin" ? "Administrar actividades" : "Ver actividades"}</ButtonLink></article>
        <article className="card"><h2>Sesiones</h2><p>Consulta el progreso y los resultados registrados.</p><ButtonLink variant="secondary" className="card-action" to={paths.sessions}>Ver sesiones</ButtonLink></article>
      </div>
    </section>
  );
}
