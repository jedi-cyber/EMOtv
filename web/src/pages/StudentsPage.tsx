import { Link } from "react-router-dom";
import type { Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";

export function StudentsPage() {
  const query = useApiQuery<Student[]>("/students");
  const students = query.data ?? [];
  return <section>
    <PageHeader section="Psicología" title="Seguimiento de estudiantes" description="Selecciona un estudiante para consultar sus sesiones." />
    <PageState {...query} empty={!query.loading && !query.error && students.length === 0} emptyMessage="Todavía no hay estudiantes registrados." onRetry={query.reload} />
    {students.length > 0 && <div className="card-list">{students.map((student) =>
      <Link className="card row-card" to={paths.studentSessions(student.id)} key={student.id}>
        <div><strong>{student.student_code}</strong><span>Ver sesiones del estudiante</span></div><span aria-hidden="true">→</span>
      </Link>
    )}</div>}
  </section>;
}
