from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.domain.activity import Activity, ActivityStep
from emotv.infrastructure.persistence.models import Base
from emotv.infrastructure.persistence.postgres_activity_repository import PostgresActivityRepository


def test_steps_survive_repository_round_trip() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        repository = PostgresActivityRepository(sessionmaker(engine))
        activity = Activity("sequence", "Secuencia", "Tres posturas", "arms_up", 3,
            steps=(ActivityStep("arms_up", "Eleva los brazos", 3),
                   ActivityStep("arms_open", "Abre los brazos", 4)))
        repository.add(activity)
        loaded = repository.get_by_id("sequence")
        assert loaded == activity
        repository.update(Activity("sequence", "Secuencia", "Dos posturas", "arms_up", 3,
            steps=(ActivityStep("arms_up", "Eleva los brazos", 3),)))
        assert len(repository.get_by_id("sequence").steps) == 1
    finally:
        engine.dispose()
