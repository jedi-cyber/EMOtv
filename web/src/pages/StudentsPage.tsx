import { Link } from "react-router-dom";
import type { Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { useAuth } from "../auth/useAuth";

export function StudentsPage() {
  const { user } = useAuth();
  const query = useApiQuery<Student[]>("/students");
  const students = query.data ?? [];
  return <section>
    <PageHeader section="Psicología" title="Seguimiento de estudiantes" description={user?.role === "psychologist" ? "Solo ves a los estudiantes que administración te asignó." : "Selecciona un estudiante para consultar sus sesiones."} />
    <PageState {...query} empty={!query.loading && !query.error && students.length === 0} emptyMessage={user?.role === "psychologist"
      ? "Aún no tienes estudiantes asignados. Administración debe asignarte los estudiantes que acompañas para que puedas ver su seguimiento."
      : "Todavía no hay estudiantes registrados."} onRetry={query.reload} />
    {students.length > 0 && <div className="card-list">{students.map((student) =>
      <Link className="card row-card" to={paths.studentSessions(student.id)} key={student.id}>
        <div><strong>{student.student_code}</strong><span>Ver sesiones del estudiante</span></div><span aria-hidden="true">→</span>
      </Link>
    )}</div>}
  </section>;
}
