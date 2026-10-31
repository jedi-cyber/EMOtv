"""Ejercicios de práctica en métricas, línea de tiempo, reporte y estadísticas
agregadas (SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes
de personas)."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from emotv.domain.guided_session import PRACTICE_NOTICE, PracticeResult
from emotv.domain.protocol import Protocol, ProtocolStep
from tests.integration.test_guided_sessions import post, state
from tests.integration.test_practice_api import practice, start
from tests.integration.test_practice_sessions import HAPPY, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_session_statistics import session, statistics


def get(env, path, user=None):  # noqa: F811
    response = env.client.get(path, headers=headers(env, user or env.user_1))
    assert response.status_code == 200, response.text
    return response.json()


# --- Una sesión ------------------------------------------------------------------------------

def test_la_sesion_resume_sus_ejercicios_aparte_de_los_estimulos(env):  # noqa: F811
    session_id, token = start(env, practice(), practice("surprise"), practice("sadness"))
    send(env, token, HAPPY, count=6)                 # el primero se logra
    send(env, token, HAPPY, count=5)                 # pasa la pausa y empieza el segundo
    assert state(env, session_id)["step_index"] == 1
    assert post(env, session_id, "skip").status_code == 200
    assert post(env, session_id, "stop", {"reason": "participant"}).status_code == 200

    metrics = get(env, f"/sessions/{session_id}/metrics")
    assert metrics["totals"]["emotional_stimuli"] == 0 and metrics["emotional"] == []
    totals = metrics["practice"]["totals"]
    assert totals["sentence"] == "Logró la expresión pedida en 1 de 1 ejercicio."
    assert (totals["skipped"], totals["stopped"], totals["not_reached"]) == (1, 1, 0)
    assert totals["feedback_sentence"] == "La señal visual estuvo activa en todos los ejercicios."
    assert [item["outcome"] for item in metrics["practice"]["exercises"]] == ["achieved", "skipped", "stopped"]
    assert metrics["practice"]["notice"] == PRACTICE_NOTICE
    # Su docente ve lo mismo.
    assert get(env, f"/sessions/{session_id}/metrics", env.docente_a)["practice"] == metrics["practice"]

    lane = get(env, f"/sessions/{session_id}/timeline")["lanes"]["stimuli"]
    assert [(item["kind"], item["target_expression"], item["outcome"]) for item in lane] == [
        ("practice", "happiness", "achieved"), ("practice", "surprise", "skipped"), ("practice", "sadness", "stopped")]
    assert lane[0]["seconds_to_achieve"] == 2.5 and lane[1]["skipped"] is True


def test_el_reporte_incluye_la_practica_con_su_aviso(env):  # noqa: F811
    session_id, token = start(env, practice())
    send(env, token, HAPPY, count=6)
    send(env, token, HAPPY, count=5)
    assert state(env, session_id)["phase"] == "finished"
    created = env.client.post(f"/sessions/{session_id}/report", headers=headers(env, env.user_1))
    assert created.status_code in (200, 201), created.text
    report = created.json()
    assert report["metrics"]["practice"]["totals"]["sentence"] == "Logró la expresión pedida en 1 de 1 ejercicio."
    assert report["metrics"]["practice"]["notice"] == PRACTICE_NOTICE


def test_sin_ejercicios_las_metricas_no_tienen_practica(env):  # noqa: F811
    item = session(env, env.user_1)
    assert get(env, f"/sessions/{item.id}/metrics")["practice"] is None


# --- Estadísticas agregadas ---------------------------------------------------------------------

def protocol(env, owner, name, *targets):  # noqa: F811
    item = Protocol(id=str(uuid4()), family_id=str(uuid4()), version=1, owner_user_id=owner.id, name=name,
                    description="", for_children=True, created_at=env.clock.now,
                    steps=tuple(ProtocolStep.practice(target, 2, 20) for target in targets))
    env.protocols.repository.add(item)
    return {"id": item.id, "family_id": item.family_id}


def results(env, item, *outcomes):  # noqa: F811
    """outcomes: (expresión, resultado, segundos, señal visible) por ejercicio, en orden."""
    for index, (target, outcome, seconds, visible) in enumerate(outcomes):
        env.guided.repository.save_practice_result(PracticeResult(
            id=str(uuid4()), session_id=item.id, step_index=index, target_expression=target, outcome=outcome,
            peak_level=0.9 if outcome == "achieved" else 0.2, relative_to_calibration=True, feedback_visible=visible,
            analyzed_frames=8, flagged_frames=0, emotion_model_id="m", emotion_model_version="1",
            started_at=item.started_at, ended_at=item.started_at + timedelta(seconds=10),
            seconds_to_achieve=seconds))


def test_estadisticas_por_protocolo_por_expresion_y_por_usuario(env):  # noqa: F811
    alegria = protocol(env, env.user_1, "Alegría y sorpresa", "happiness", "surprise")
    tristeza = protocol(env, env.user_1, "Tristeza", "sadness")
    first = session(env, env.user_1, protocol=alegria, audience="infantil")
    results(env, first, ("happiness", "achieved", 2.0, True), ("surprise", "timed_out", None, True))
    second = session(env, env.user_1, day=1, protocol=alegria, audience="infantil")
    results(env, second, ("happiness", "achieved", 4.0, False), ("surprise", "skipped", None, True))
    third = session(env, env.user_1, day=2, protocol=tristeza, state="cancelled", audience="infantil")
    results(env, third, ("sadness", "stopped", None, True))
    # Otro grupo: nunca entra.
    other = session(env, env.user_2, protocol=protocol(env, env.user_2, "Ajeno", "happiness"))
    results(env, other, ("happiness", "achieved", 1.0, True))

    body = statistics(env, env.user_1).json()
    practice_stats = body["practice"]
    assert practice_stats["sessions"] == 3 and practice_stats["notice"] == PRACTICE_NOTICE
    totals = practice_stats["totals"]
    assert totals["sentence"] == "Logró la expresión pedida en 2 de 3 ejercicios."
    assert totals["average_seconds_to_achieve"] == 3.0
    assert (totals["skipped"], totals["stopped"]) == (1, 1)
    assert totals["feedback_sentence"] == "La señal visual estuvo activa en 2 de 3 ejercicios."
    by_target = {row["target_expression"]: row for row in practice_stats["by_target"]}
    assert list(by_target) == ["happiness", "surprise", "sadness"]
    assert (by_target["happiness"]["achieved"], by_target["happiness"]["applied"]) == (2, 2)
    assert (by_target["surprise"]["achieved"], by_target["surprise"]["applied"], by_target["surprise"]["skipped"]) == (0, 1, 1)
    assert (by_target["sadness"]["applied"], by_target["sadness"]["stopped"]) == (0, 1)
    by_protocol = {row["name"]: row for row in practice_stats["by_protocol"]}
    assert set(by_protocol) == {"Alegría y sorpresa", "Tristeza"}
    assert (by_protocol["Alegría y sorpresa"]["sessions"], by_protocol["Alegría y sorpresa"]["achieved"],
            by_protocol["Alegría y sorpresa"]["applied"]) == (2, 2, 3)
    assert "by_user" not in practice_stats
    # La coincidencia de estímulos no cambia con los ejercicios.
    assert body["coincidence"] == {"compared": 0, "matched": 0}

    # Filtrar por protocolo.
    filtered = statistics(env, env.user_1, protocol=tristeza["family_id"]).json()["practice"]
    assert filtered["totals"]["sentence"] == "Ningún ejercicio de práctica llegó a terminar."

    group = statistics(env, env.docente_a, scope="group").json()["practice"]
    assert group["totals"]["sentence"] == totals["sentence"]
    assert [(row["email"], row["achieved"], row["applied"]) for row in group["by_user"]] == [
        ("usuario1@example.com", 2, 3)]
    assert statistics(env, env.docente_b, scope="group").json()["practice"]["by_user"][0]["achieved"] == 1


def test_sin_ejercicios_las_estadisticas_no_tienen_practica(env):  # noqa: F811
    session(env, env.user_1)
    assert statistics(env, env.user_1).json()["practice"] is None
    assert statistics(env, env.docente_a, scope="group").json()["practice"] is None


def test_un_usuario_no_ve_las_estadisticas_del_grupo(env):  # noqa: F811
    assert statistics(env, env.user_1, scope="group").status_code == 403
    for user in (env.admin, env.superadmin):
        assert statistics(env, user).status_code == 403
