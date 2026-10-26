import { ButtonLink } from "../components/Button";
import { Card } from "../components/Card";
import type { Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";

/** Usuarios del grupo del docente (lo arma el administrador). */
export function StudentsPage() {
  const query = useApiQuery<Student[]>("/students");
  const students = query.data ?? [];
  return <section>
    <PageHeader title="Mi grupo" description="Usuarios de tu grupo. Ves sus sesiones y sus reportes." />
    <PageState {...query} empty={!query.loading && !query.error && students.length === 0}
      emptyMessage="Aún no tienes usuarios en tu grupo. El administrador asigna los usuarios a cada docente." onRetry={query.reload} />
    {students.length > 0 && <div className="card-list">{students.map((student) =>
      <Card as="article" className="row-card" key={student.id}>
        <strong>{student.student_code}</strong>
        <ButtonLink variant="secondary" to={paths.studentSessions(student.id)} aria-label={`Ver sesiones del usuario ${student.student_code}`}>Ver sesiones</ButtonLink>
      </Card>
    )}</div>}
  </section>;
}
