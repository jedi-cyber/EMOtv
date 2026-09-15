from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from emotv.domain.activity import Activity
from emotv.infrastructure.persistence.models import ActivityRecord


class PostgresActivityRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    @staticmethod
    def _domain(row: ActivityRecord) -> Activity:
        return Activity(row.id, row.name, row.description, row.required_posture,
                        row.duration_seconds, row.repetitions)

    def get_by_id(self, activity_id: str) -> Activity | None:
        with self._factory() as db:
            row = db.get(ActivityRecord, activity_id)
            return self._domain(row) if row else None

    def list_all(self) -> tuple[Activity, ...]:
        with self._factory() as db:
            return tuple(self._domain(row) for row in db.scalars(select(ActivityRecord).order_by(ActivityRecord.id)))

    def add(self, activity: Activity) -> Activity:
        try:
            with self._factory.begin() as db:
                db.add(ActivityRecord(id=activity.id, name=activity.name,
                    description=activity.description, required_posture=activity.required_posture.value,
                    duration_seconds=activity.duration_seconds, repetitions=activity.repetitions))
        except IntegrityError as error:
            raise ValueError("Actividad duplicada o inválida") from error
        return activity

    def update(self, activity: Activity) -> Activity:
        with self._factory.begin() as db:
            row = db.get(ActivityRecord, activity.id)
            if row is None:
                raise KeyError("Actividad no encontrada")
            row.name, row.description = activity.name, activity.description
            row.required_posture = activity.required_posture.value
            row.duration_seconds, row.repetitions = activity.duration_seconds, activity.repetitions
        return activity

    def remove(self, activity_id: str) -> Activity:
        with self._factory.begin() as db:
            row = db.get(ActivityRecord, activity_id)
            if row is None:
                raise KeyError("Actividad no encontrada")
            activity = self._domain(row)
            db.delete(row)
        return activity
