"""Audita y, opcionalmente, repara actividades recomendadas en PostgreSQL."""
from __future__ import annotations

import argparse

from emotv.application.activity_catalog import DEFAULT_ACTIVITIES
from emotv.application.activity_recommendation_service import DEFAULT_ACTIVITIES_BY_EMOTION
from emotv.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from emotv.infrastructure.persistence.postgres_activity_repository import (
    PostgresActivityRepository,
)
from emotv.infrastructure.vision.movement_analysis import PostureValidator


MIN_RECOMMENDED_STEPS = 2


def recommended_ids() -> frozenset[str]:
    return frozenset(
        activity_id
        for activity_ids in DEFAULT_ACTIVITIES_BY_EMOTION.values()
        for activity_id in activity_ids
    )


def audit(repository: PostgresActivityRepository) -> tuple[str, ...]:
    supported = PostureValidator().supported_postures
    activities = {activity.id: activity for activity in repository.list_all()}
    problems: list[str] = []
    for activity_id in sorted(recommended_ids()):
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


def repair(repository: PostgresActivityRepository) -> None:
    defaults = {activity.id: activity for activity in DEFAULT_ACTIVITIES}
    for activity_id in sorted(recommended_ids()):
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
        repository = PostgresActivityRepository(create_session_factory(engine))
        before = audit(repository)
        if arguments.repair and before:
            repair(repository)
        after = audit(repository)
        for activity in repository.list_all():
            marker = "RECOMENDADA" if activity.id in recommended_ids() else "CATALOGO"
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
