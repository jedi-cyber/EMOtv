import { useAuth } from "../auth/useAuth";

export function DashboardPage() {
  const { user } = useAuth();
  const descriptions = {
    student: "Selecciona una actividad corporal o revisa tus sesiones.",
    psychologist: "Consulta el seguimiento de estudiantes y sus sesiones autorizadas.",
    admin: "Administra usuarios, actividades y el funcionamiento general de EMOtv.",
  };
  return (
    <section>
      <p className="eyebrow">Panel principal</p>
      <h1>Hola, {user?.email.split("@")[0]}</h1>
      <p className="lead">{user ? descriptions[user.role] : ""}</p>
      <div className="card-grid">
        {user?.role === "student" && <article className="card"><h2>Analizador facial</h2><p>Prepara una sesión y selecciona el modelo de emociones.</p></article>}
        {user?.role === "psychologist" && <article className="card"><h2>Estudiantes</h2><p>Accede al seguimiento con los permisos correspondientes.</p></article>}
        {user?.role === "admin" && <article className="card"><h2>Usuarios</h2><p>Supervisa las cuentas y sus roles de acceso.</p></article>}
        <article className="card"><h2>Actividades</h2><p>Explora las posturas y ejercicios disponibles.</p></article>
        <article className="card"><h2>Sesiones</h2><p>Consulta el progreso y los resultados registrados.</p></article>
      </div>
    </section>
  );
}
