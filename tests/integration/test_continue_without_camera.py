"""Seguir sin cámara: si la pantalla de la persona no puede usarla (permiso
denegado, sin cámara o falla), quien conduce lo ve y la sesión sigue con los
pasos que no la necesitan. Incluye la migración 20261106_36 (SQLite en memoria,
reloj falso y analizador falso; sin modelos ni imágenes de personas)."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from emotv.domain.guided_session import GuidedRun, PracticeOutcome
from emotv.domain.protocol import ProtocolStep
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_guided_sessions import (
    calibrate,
    create_questionnaire,
    frame,
    guided,
    post,
    protocol,
    state,
    step,
    stimuli,
    view,
    wait,
)
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_sessions import NEUTRAL, practice_protocol, send
from tests.integration.test_privacy_accounts import KEY, env, headers  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_36_guided_camera_off.py"


def mixed(env, sad, *, pre=None):  # noqa: F811
    """Práctica, reconocimiento, práctica y reconocimiento (guardado en el repositorio)."""
    item = practice_protocol(env, ProtocolStep.practice("happiness", 2, 20),
                             ProtocolStep.recognition(sad["id"], 4, target_expression="sadness"),
                             ProtocolStep.practice("surprise", 2, 20),
                             ProtocolStep.recognition(sad["id"], 4, target_expression="sadness"))
    if pre is not None:
        stored = env.protocols.repository.get(item["id"])
        env.protocols.repository.replace(replace(stored, pre_questionnaire_id=pre["id"]))
    return item


def camera_problem(env, token, reason):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/camera-problem", json={"reason": reason})


def test_el_protocolo_informa_si_usa_la_camara(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    assert protocol(env, [recognition(sad)])["uses_camera"] is False
    assert protocol(env, [recognition(sad), step(emotional)])["uses_camera"] is True


def test_si_se_niega_la_camara_quien_conduce_lo_ve_y_sigue_con_los_reconocimientos(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = guided(env, mixed(env, sad))
    assert state(env, session_id)["phase"] == "calibration"
    assert post(env, session_id, "calibration").status_code == 200
    assert view(env, token).json()["capture_frames"] is True
    # La pantalla de la persona no pudo abrir la cámara: solo informa el motivo.
    assert camera_problem(env, token, "denied").json() == {"received": True}
    current = state(env, session_id)
    assert current["camera_problem"] == "denied" and current["camera_off"] is False
    assert current["phase"] == "calibration"

    moved = post(env, session_id, "continue-without-camera")
    assert moved.status_code == 200 and moved.json() == {"phase": "stimuli"}
    current = state(env, session_id)
    # La primera práctica se saltó sin empezar; sigue el reconocimiento.
    assert current["step_index"] == 1 and current["camera_off"] is True
    assert current["steps_log"][0]["skipped"] is True and current["steps_log"][0]["reason"] == "no_camera"
    shown = view(env, token).json()
    assert shown["uses_camera"] is False and shown["capture_frames"] is False and shown["recognition"]
    assessed = env.frames_assessed
    frame(env, token)
    assert env.frames_assessed == assessed
    assert post(env, session_id, "calibration").status_code == 409

    wait(env, 1)
    assert answer(env, token, "sadness").status_code == 200
    wait(env, 2.1)
    # La segunda práctica también se salta y sigue el último reconocimiento.
    assert state(env, session_id)["step_index"] == 3
    wait(env, 6.5)
    finished = state(env, session_id)
    assert finished["phase"] == "finished"
    assert [(item["step_index"], item["skipped"], item.get("reason")) for item in finished["steps_log"]] == [
        (0, True, "no_camera"), (1, False, None), (2, True, "no_camera"), (3, False, None)]
    # Los ejercicios que no se hicieron no dejan resultado de práctica.
    assert finished["practice_results"] == [] and finished["captures"] == []
    assert [item["outcome"] for item in finished["recognition_results"]] == ["answered", "timed_out"]
    assert env.sessions.get_session(session_id).state.value == "completed"


def test_seguir_sin_camara_a_mitad_de_un_ejercicio_lo_salta(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = guided(env, mixed(env, sad))
    env.frame_result = NEUTRAL
    calibrate(env, session_id, token)
    assert state(env, session_id)["step_index"] == 0
    send(env, token, NEUTRAL, count=2)
    assert post(env, session_id, "continue-without-camera").json() == {"phase": "stimuli"}
    current = state(env, session_id)
    assert current["step_index"] == 1
    assert current["steps_log"][0]["reason"] == "no_camera"
    # El ejercicio ya había empezado: queda registrado como saltado.
    [result] = env.guided.repository.list_practice_results(session_id)
    assert result.outcome is PracticeOutcome.SKIPPED and result.step_index == 0
    assert view(env, token).json()["capture_frames"] is False


def test_seguir_sin_camara_en_el_cuestionario_previo_lleva_a_empezar(env):  # noqa: F811
    sad = sad_stimulus(env)
    pre = create_questionnaire(env, env.user_1,
                               items=[{"id": "a", "kind": "faces", "text": "¿Cómo estás?", "required": True}])
    session_id, _ = guided(env, mixed(env, sad, pre=pre))
    assert state(env, session_id)["phase"] == "pre_questionnaire"
    assert post(env, session_id, "continue-without-camera").json() == {"phase": "pre_questionnaire"}
    env.client.post(f"/sessions/{session_id}/questionnaires/pre", headers=headers(env, env.user_1),
                    json={"answers": {"a": 3}, "entry_mode": "participant"})
    assert post(env, session_id, "advance").json() == {"phase": "ready"}
    assert post(env, session_id, "start").json() == {"phase": "stimuli"}
    assert state(env, session_id)["step_index"] == 1


def test_seguir_sin_camara_solo_donde_corresponde(env):  # noqa: F811
    sad = sad_stimulus(env)
    # Un protocolo solo de reconocimientos ya va sin cámara.
    only, _ = guided(env, protocol(env, [recognition(sad)]))
    assert post(env, only, "continue-without-camera").status_code == 409
    session_id, _ = guided(env, mixed(env, sad))
    assert post(env, session_id, "continue-without-camera", user=env.user_2).status_code in (403, 404)
    assert post(env, session_id, "continue-without-camera").status_code == 200
    # Repetirlo no cambia nada.
    assert post(env, session_id, "continue-without-camera").json() == {"phase": "stimuli"}
    post(env, session_id, "stop", {"reason": "conductor"})
    assert post(env, session_id, "continue-without-camera").status_code == 409


def test_sin_protocolo_la_sesion_necesita_la_camara(env):  # noqa: F811
    live, _ = guided(env, session_type="propia")
    assert post(env, live, "continue-without-camera").status_code == 409


def test_la_pantalla_de_la_persona_solo_informa_motivos_conocidos(env):  # noqa: F811
    sad = sad_stimulus(env)
    _, token = guided(env, mixed(env, sad))
    assert camera_problem(env, token, "cualquier cosa").status_code == 422
    assert camera_problem(env, "no-existe", "denied").status_code == 404


# --- Persistencia y migración -----------------------------------------------------------


def _run(engine, step_name):  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261106_36", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261106_36", "20261104_35")
    with engine.connect() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step_name)()
        connection.commit()


def test_seguir_sin_camara_ida_y_vuelta_y_su_migracion(engine, factory):  # noqa: F811
    repository = PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))
    run = repository.save_run(GuidedRun(session_id="ses1", owner_user_id="u1", created_at=T0))
    assert repository.get_run("ses1").camera_off_at is None
    repository.save_run(replace(run, camera_off_at=T0))
    assert repository.get_run("ses1").camera_off_at == T0

    _run(engine, "downgrade")
    assert "camera_off_at" not in {column["name"] for column in inspect(engine).get_columns("guided_runs")}
    _run(engine, "upgrade")
    # Las sesiones que ya existían siguen con la cámara.
    assert repository.get_run("ses1").camera_off_at is None
