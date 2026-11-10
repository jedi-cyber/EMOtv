"""Bloque 3: explicaciones educativas en «¿Qué emoción es?». La explicación
sencilla sale del catálogo revisable (expression_info.child_explanation), se
muestra solo al terminar el paso y nunca la genera un LLM. Migración
20261106_37 (SQLite en memoria, reloj falso; sin modelos ni personas)."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from emotv.domain import Role
from emotv.domain.expression_info import EXPRESSION_KEYS, ExpressionInfo
from emotv.infrastructure.persistence import Base
from tests.integration.test_expressions_api import api, edit_body, seeded_items  # noqa: F401
from tests.integration.test_guided_sessions import view, wait
from tests.integration.test_privacy_accounts import env  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus, start

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_37_child_explanation.py"
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_20261106_37", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def with_explanation(env, key="sadness"):  # noqa: F811
    """Fila del catálogo con la explicación de la migración."""
    item = next(row for row in seeded_items() if row.expression_key == key)
    env.expressions.save(ExpressionInfo(**{
        **{name: getattr(item, name) for name in ("expression_key", "label_es", "what_it_is", "why_it_occurs",
                                                    "facial_cues", "practice_tip", "limitation_note")},
        "updated_at": NOW, "child_explanation": load_migration().SEED[key]}))


# --- En la sesión ---------------------------------------------------------------------------


def test_la_explicacion_aparece_solo_al_terminar_el_paso(env):  # noqa: F811
    with_explanation(env)
    sad = sad_stimulus(env)
    _, token = start(env, recognition(sad), recognition(sad))
    before = view(env, token).json()["recognition"]
    # Antes de responder no se adelanta la respuesta.
    assert before["explanation"] is None and before["message"] is None and before["note"] is None
    # Se lee igual con cualquier opción: no dice si coincidió.
    other = next(item["key"] for item in before["options"] if item["key"] != "sadness")
    assert answer(env, token, other).json() == {"received": True}
    after = view(env, token).json()["recognition"]
    assert after["message"] == "Es tristeza" and after["chosen"] == other
    assert after["explanation"] == "En la tristeza, las cejas suben en el centro y las puntas de la boca bajan."
    assert after["note"] is None


def test_al_vencer_el_tiempo_tambien_se_explica(env):  # noqa: F811
    with_explanation(env)
    sad = sad_stimulus(env)
    _, token = start(env, recognition(sad, exposure=5), recognition(sad))
    wait(env, 5.5)
    block = view(env, token).json()["recognition"]
    assert block["chosen"] is None and block["explanation"].startswith("En la tristeza")


def test_sin_explicacion_en_el_catalogo_el_paso_sigue_igual(env):  # noqa: F811
    sad = sad_stimulus(env)
    _, token = start(env, recognition(sad), recognition(sad))
    answer(env, token, "sadness")
    block = view(env, token).json()["recognition"]
    assert block["message"] == "Es tristeza" and block["explanation"] is None


# --- Catálogo -------------------------------------------------------------------------------


def test_la_explicacion_se_valida():
    base = next(iter(seeded_items()))
    with pytest.raises(ValueError, match="child_explanation"):
        ExpressionInfo(**{**_fields(base), "child_explanation": "Corta."})
    with pytest.raises(ValueError, match="child_explanation"):
        ExpressionInfo(**{**_fields(base), "child_explanation": "x" * 201})
    assert ExpressionInfo(**{**_fields(base), "child_explanation": "  Una cara tranquila.  "}).child_explanation \
        == "Una cara tranquila."


def _fields(item: ExpressionInfo) -> dict:
    return {name: getattr(item, name) for name in ("expression_key", "label_es", "what_it_is", "why_it_occurs",
                                                    "facial_cues", "practice_tip", "limitation_note", "updated_at")}


def test_administracion_edita_la_explicacion_y_vuelve_a_borrador(api):  # noqa: F811
    client, headers, _, repository = api
    body = edit_body(child_explanation="En la tristeza, la boca baja en las puntas.")
    saved = client.put("/expressions/sadness", headers=headers[Role.SUPERADMIN], json=body).json()
    assert saved["child_explanation"] == "En la tristeza, la boca baja en las puntas."
    assert saved["review_status"] == "reviewed"
    # Sin el campo se conserva; cambiarlo sin marcar revisión lo deja en borrador.
    kept = client.put("/expressions/sadness", headers=headers[Role.SUPERADMIN],
                      json=edit_body(review_status="draft")).json()
    assert kept["child_explanation"] == "En la tristeza, la boca baja en las puntas."
    assert kept["review_status"] == "draft"
    assert client.put("/expressions/sadness", headers=headers[Role.SUPERADMIN],
                      json=edit_body(child_explanation="Corta.")).status_code == 422
    assert client.get("/expressions/sadness", headers=headers[Role.STUDENT]).json()["child_explanation"] \
        == repository.get("sadness").child_explanation


# --- Migración ------------------------------------------------------------------------------


def _sentences(value: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part])


def test_los_borradores_cubren_cada_expresion_con_una_oracion_que_describe_la_cara():
    seed = load_migration().SEED
    assert sorted(seed) == sorted(EXPRESSION_KEYS)
    forbidden = re.compile(r"diagn|trastorn|terap|sientes|te pasa|estás|bien|mal\b|correct|error", re.IGNORECASE)
    for key, value in seed.items():
        assert _sentences(value) == 1 and 10 <= len(value) <= 200, key
        assert not forbidden.search(value), key


def _run(engine, step: str) -> None:
    module = load_migration()
    assert (module.revision, module.down_revision) == ("20261106_37", "20261106_36")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_llena_la_explicacion_y_devuelve_a_borrador_lo_revisado():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    _run(engine, "downgrade")
    assert "child_explanation" not in {column["name"] for column in inspect(engine).get_columns("expression_info")}
    with engine.begin() as connection:
        for item in seeded_items():
            reviewed = item.expression_key == "sadness"
            connection.execute(text(
                "INSERT INTO expression_info (expression_key, label_es, what_it_is, why_it_occurs, facial_cues, "
                "practice_tip, limitation_note, review_status, reviewed_at, updated_at) VALUES (:k, :l, :a, :b, "
                ":c, :d, :e, :s, :r, :u)"), {
                    "k": item.expression_key, "l": item.label_es, "a": item.what_it_is, "b": item.why_it_occurs,
                    "c": item.facial_cues, "d": item.practice_tip, "e": item.limitation_note,
                    "s": "reviewed" if reviewed else "draft", "r": NOW if reviewed else None, "u": NOW})
    _run(engine, "upgrade")
    with engine.connect() as connection:
        rows = {row.expression_key: row for row in connection.execute(text(
            "SELECT expression_key, child_explanation, review_status, reviewed_at FROM expression_info"))}
    assert all(rows[key].child_explanation == value for key, value in load_migration().SEED.items())
    assert rows["sadness"].review_status == "draft" and rows["sadness"].reviewed_at is None
    engine.dispose()
