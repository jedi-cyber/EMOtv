import { ButtonLink } from "../components/Button";
import { Card } from "../components/Card";
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
    <PageHeader title="Seguimiento de estudiantes" description={user?.role === "psychologist" ? "Solo ves a los estudiantes que administración te asignó." : "Selecciona un estudiante para consultar sus sesiones."} />
    <PageState {...query} empty={!query.loading && !query.error && students.length === 0} emptyMessage={user?.role === "psychologist"
      ? "Aún no tienes estudiantes asignados. Administración debe asignarte los estudiantes que acompañas para que puedas ver su seguimiento."
      : "Todavía no hay estudiantes registrados."} onRetry={query.reload} />
    {students.length > 0 && <div className="card-list">{students.map((student) =>
      <Card as="article" className="row-card" key={student.id}>
        <strong>{student.student_code}</strong>
        <ButtonLink variant="secondary" to={paths.studentSessions(student.id)} aria-label={`Ver sesiones del estudiante ${student.student_code}`}>Ver sesiones del estudiante</ButtonLink>
      </Card>
    )}</div>}
  </section>;
}
