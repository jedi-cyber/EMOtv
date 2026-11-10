"""Imitar un modelo («Haz la misma cara»): un ejercicio de práctica cuya
ilustración es el modelo. La expresión pedida sale de la imagen, la persona solo
ve la instrucción, el dibujo y la señal, y el resultado se registra como en
cualquier práctica. Incluye la migración 20261104_35 (SQLite en memoria, reloj y
analizador falsos; sin modelos ni imágenes de personas)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import PracticeOutcome
from emotv.domain.protocol import ProtocolStep
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_guided_sessions import state, view
from tests.integration.test_practice_api import create, practice, start
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import protocol as stored_protocol
from tests.integration.test_practice_sessions import HAPPY, _no_forbidden, results, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import approve, upload_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261104_35_imitation_steps.py"


def happy_drawing(env):  # noqa: F811
    return approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Cara alegre",
                                                       expected_expression="happiness"))


def imitation(stimulus, target="sadness"):
    """La expresión enviada no importa: el servidor la toma de la imagen."""
    return {**practice(target, illustration=stimulus), "imitate": True}


def get(env, path):  # noqa: F811
    response = env.client.get(path, headers=headers(env, env.user_1))
    assert response.status_code == 200, response.text
    return response.json()


def test_la_expresion_pedida_sale_de_la_imagen_del_modelo(env):  # noqa: F811
    response = create(env, imitation(happy_drawing(env)))
    assert response.status_code == 201, response.text
    [step] = response.json()["steps"]
    assert step["kind"] == "practice" and step["imitate"] is True and step["target_expression"] == "happiness"


def test_imitar_necesita_una_practica_con_imagen(env):  # noqa: F811
    drawing = happy_drawing(env)
    assert create(env, {**practice(), "imitate": True}).status_code == 422
    recognition = {"kind": "recognition", "stimulus_id": drawing["id"], "exposure_seconds": 10, "imitate": True}
    assert create(env, recognition).status_code == 422
    # Una práctica sin imitate sigue usando la imagen como ilustración de apoyo.
    [step] = create(env, practice("sadness", illustration=drawing)).json()["steps"]
    assert step["imitate"] is False and step["target_expression"] == "sadness"


def test_el_dominio_rechaza_imitar_sin_modelo():
    with pytest.raises(ValueError):
        ProtocolStep.practice("happiness", 2, 20, imitate=True)
    with pytest.raises(ValueError):
        ProtocolStep("s1", 10, 0, kind="recognition", option_count=2, imitate=True)


def test_la_persona_ve_haz_la_misma_cara_con_el_modelo_y_sin_etiquetas(env):  # noqa: F811
    session_id, token = start(env, imitation(happy_drawing(env)))
    shown = view(env, token).json()
    assert shown["practice"]["instruction"] == "Haz la misma cara"
    assert shown["stimulus"] is not None
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    _no_forbidden(shown)
    # Quien conduce sabe qué expresión se pide y que es una imitación.
    current = state(env, session_id)
    assert current["practice"]["imitate"] is True and current["practice"]["target_expression"] == "happiness"
    assert current["steps"][0]["imitate"] is True

    send(env, token, HAPPY, count=5)
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED and item.target_expression == "happiness"
    shown = view(env, token).json()
    assert shown["practice"]["achieved"] is True and shown["practice"]["message"] == "¡Lo lograste!"
    _no_forbidden(shown)

    [exercise] = get(env, f"/sessions/{session_id}/metrics")["practice"]["exercises"]
    assert exercise["imitate"] is True and exercise["outcome"] == "achieved"
    [lane] = get(env, f"/sessions/{session_id}/timeline")["lanes"]["stimuli"]
    assert lane["kind"] == "practice" and lane["imitate"] is True


# --- Persistencia y migración ------------------------------------------------------------------

def imitating():
    return stored_protocol(steps=(ProtocolStep.practice("happiness", 2, 20),
                                  ProtocolStep.practice("surprise", 3, 15, illustration_id="s1", imitate=True)))


def test_ida_y_vuelta(factory):  # noqa: F811
    PostgresProtocolRepository(factory).replace(imitating())
    assert PostgresProtocolRepository(factory).get("p1") == imitating()


def _run(engine, step: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261104_35", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261104_35", "20261102_34")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_downgrade_y_upgrade(engine, factory):  # noqa: F811
    PostgresProtocolRepository(factory).replace(imitating())
    _run(engine, "downgrade")
    assert "imitate" not in {column["name"] for column in inspect(engine).get_columns("protocol_steps")}
    _run(engine, "upgrade")
    # La imitación vuelve como práctica con ilustración.
    assert PostgresProtocolRepository(factory).get("p1").steps[1].imitate is False
    test_ida_y_vuelta(factory)
