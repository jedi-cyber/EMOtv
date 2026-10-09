"""Audita y, opcionalmente, repara actividades recomendadas en PostgreSQL."""
from __future__ import annotations

import argparse

from emotv.application.activity_catalog import DEFAULT_ACTIVITIES
from emotv.application.activity_recommendation_service import MINIMUM_RECOMMENDED_STEPS
from emotv.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from emotv.infrastructure.persistence.postgres_activity_repository import (
    PostgresActivityRepository,
)
from emotv.infrastructure.persistence.postgres_recommendation_repository import (
    PostgresRecommendationRepository,
)
from emotv.infrastructure.vision.movement_analysis import PostureValidator


MIN_RECOMMENDED_STEPS = MINIMUM_RECOMMENDED_STEPS


def recommended_ids(recommendations: PostgresRecommendationRepository) -> frozenset[str]:
    """Actividades asociadas a alguna expresión en emotion_activity_recommendations."""
    return frozenset(
        activity_id for ids in recommendations.list_all().values() for activity_id in ids
    )


def audit(repository: PostgresActivityRepository, recommended: frozenset[str]) -> tuple[str, ...]:
    supported = PostureValidator().supported_postures
    activities = {activity.id: activity for activity in repository.list_all()}
    problems: list[str] = []
    for activity_id in sorted(recommended):
        activity = activities.get(activity_id)
        if activity is None:
            problems.append(f"{activity_id}: no existe en PostgreSQL")
            continue
        if len(activity.steps) < MIN_RECOMMENDED_STEPS:
            problems.append(
                f"{activity_id}: tiene {len(activity.steps)} step; se requieren al menos 2"
            )
        unsupported = sorted(
            {step.posture.value for step in activity.steps if step.posture not in supported}
        )
        if unsupported:
            problems.append(
                f"{activity_id}: posturas sin validador: {', '.join(unsupported)}"
            )
    return tuple(problems)


def repair(repository: PostgresActivityRepository, recommended: frozenset[str]) -> None:
    defaults = {activity.id: activity for activity in DEFAULT_ACTIVITIES}
    for activity_id in sorted(recommended):
        expected = defaults.get(activity_id)
        if expected is None or len(expected.steps) < MIN_RECOMMENDED_STEPS:
            raise RuntimeError(
                f"El catálogo local no puede reparar {activity_id}: requiere varios steps"
            )
        current = repository.get_by_id(activity_id)
        if current is None:
            repository.add(expected)
        elif len(current.steps) < MIN_RECOMMENDED_STEPS:
            repository.update(expected)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba que cada actividad recomendada tenga varios steps válidos.",
    )
    parser.add_argument(
        "--repair", action="store_true",
        help="Crea actividades recomendadas ausentes y reemplaza las de menos de dos pasos.",
    )
    arguments = parser.parse_args()
    engine = create_database_engine()
    try:
        factory = create_session_factory(engine)
        repository = PostgresActivityRepository(factory)
        recommended = recommended_ids(PostgresRecommendationRepository(factory))
        before = audit(repository, recommended)
        if arguments.repair and before:
            repair(repository, recommended)
        after = audit(repository, recommended)
        for activity in repository.list_all():
            marker = "RECOMENDADA" if activity.id in recommended else "CATALOGO"
            print(f"[{marker}] {activity.id}: {len(activity.steps)} steps")
        if after:
            print("Problemas:")
            for problem in after:
                print(f"- {problem}")
            return 1
        print("OK: todas las actividades recomendadas tienen varios steps y validadores.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
