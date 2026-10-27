"""Estaciones del examen simulado: unirse con el código, esperar el consentimiento,
calibrarse, registrar una fila cada medio segundo y terminar con el debriefing.

SQLite en memoria, reloj manual y analizador falso: sin modelos, cámaras ni imágenes.
"""
from __future__ import annotations

from datetime import timedelta

from emotv.domain.guided_session import EXAM_DEBRIEFING, CaptureQuality, FrameAssessment, QualityIssue
from emotv.domain.session_state import SessionState
from tests.integration.test_privacy_accounts import accept_commitment, env, headers  # noqa: F401

FRAME = b"cuadro"   # el decodificador de prueba lo acepta tal cual; el analizador es falso


def create_exam(env):  # noqa: F811
    accept_commitment(env, env.docente_a)
    response = env.client.post("/exams", headers=headers(env, env.docente_a))
    assert response.status_code == 201, response.text
    return response.json()


def join(env, exam):  # noqa: F811
    response = env.client.post("/exam-stations", json={"join_code": exam["join_code"].lower()})
    assert response.status_code == 201, response.text
    return response.json()


def view(env, station):  # noqa: F811
    response = env.client.get(f"/participant-view/{station['view_token']}")
    assert response.status_code == 200, response.text
    return response.json()


def frame(env, station):  # noqa: F811
    response = env.client.post(f"/participant-view/{station['view_token']}/frames", content=FRAME)
    assert response.status_code == 200, response.text


def step(env, seconds=0.5):  # noqa: F811
    env.clock.now += timedelta(seconds=seconds)


def calibrate(env, station):  # noqa: F811
    """Cuadros cada medio segundo hasta completar la calibración (3 s)."""
    view(env, station)
    for _ in range(8):
        frame(env, station)
        step(env)
    assert view(env, station)["phase"] == "ready"


def docente(env, exam, action):  # noqa: F811
    response = env.client.post(f"/exams/{exam['id']}/{action}", headers=headers(env, env.docente_a))
    assert response.status_code == 200, response.text
    return response.json()


def session_of(env, exam, station):  # noqa: F811
    return next(item for item in env.exams.repository.list_sessions(exam["id"])
                if item.code == station["session_code"])


def test_la_estacion_se_une_con_el_codigo_y_espera_sin_analizar(env):  # noqa: F811
    exam = create_exam(env)
    station = join(env, exam)
    assert station["session_code"].startswith("S-") and station["view_token"]
    shown = view(env, station)
    assert shown["phase"] == "waiting" and shown["capture_frames"] is False
    # Sin consentimiento confirmado, ningún cuadro se analiza.
    before = env.frames_assessed
    frame(env, station)
    assert env.frames_assessed == before
    detail = env.client.get(f"/exams/{exam['id']}", headers=headers(env, env.docente_a)).json()
    assert detail["stations"][0]["phase"] == "waiting" and detail["stations"][0]["consent_confirmed"] is False
    session = session_of(env, exam, station)
    assert session.owner_user_id == env.docente_a.id and session.session_type.value == "adulto"
    assert session.authorization_confirmed_at is None


def test_codigo_invalido_o_examen_terminado(env):  # noqa: F811
    assert env.client.post("/exam-stations", json={"join_code": "ZZZZZZ"}).status_code == 404
    exam = create_exam(env)
    docente(env, exam, "finish")
    assert env.client.post("/exam-stations", json={"join_code": exam["join_code"]}).status_code == 404


def test_examen_completo_una_fila_cada_medio_segundo(env):  # noqa: F811
    exam = create_exam(env)
    active, silent = join(env, exam), join(env, exam)
    assert docente(env, exam, "consents")["confirmed"] == 2
    # Con el consentimiento, la calibración empieza sola.
    assert view(env, active)["phase"] == "calibration" and view(env, active)["capture_frames"] is True
    calibrate(env, active)
    calibrate(env, silent)
    # Calibrada, la estación no guarda nada hasta que el docente inicia.
    frame(env, active)
    assert env.guided.repository.list_captures(session_of(env, exam, active).id) == ()

    docente(env, exam, "start")
    shown = view(env, active)
    assert shown["phase"] == "exam" and shown["message"] == "Examen en curso."
    for _ in range(10):              # 5 s de examen con cuadros cada medio segundo
        frame(env, active)
        step(env)
    env.frame_result = FrameAssessment((QualityIssue.NO_FACE,))
    frame(env, active)               # a los 5 s, un cuadro sin rostro: se guarda marcado
    step(env)
    docente(env, exam, "finish")

    rows = env.guided.repository.list_captures(session_of(env, exam, active).id)
    assert [item.seconds_since_stimulus for item in rows] == [index * 0.5 for index in range(11)]
    assert all(item.quality is CaptureQuality.GOOD and item.emotion == "happiness" for item in rows[:10])
    assert rows[10].quality is CaptureQuality.FLAGGED and rows[10].quality_issues == (QualityIssue.NO_FACE,)
    assert all(item.stimulus_id is None and item.confidence is not None for item in rows[:10])
    # La estación que no envió cuadros registra sus huecos, marcados, hasta el cierre.
    gaps = env.guided.repository.list_captures(session_of(env, exam, silent).id)
    assert gaps and all(item.quality_issues == (QualityIssue.NO_FRAME,) for item in gaps)
    assert gaps[0].seconds_since_stimulus == 0.0

    # Al terminar: debriefing en la pantalla y sesiones completadas.
    finished = view(env, active)
    assert finished["phase"] == "finished" and finished["message"] == EXAM_DEBRIEFING
    assert finished["capture_frames"] is False
    assert session_of(env, exam, active).state is SessionState.COMPLETED
    assert session_of(env, exam, silent).state is SessionState.COMPLETED
    # Después del cierre, la estación ya no recibe cuadros.
    response = env.client.post(f"/participant-view/{active['view_token']}/frames", content=FRAME)
    assert response.status_code == 404


def test_una_estacion_que_llega_tarde_espera_una_nueva_confirmacion(env):  # noqa: F811
    exam = create_exam(env)
    first = join(env, exam)
    docente(env, exam, "consents")
    calibrate(env, first)
    docente(env, exam, "start")
    late = join(env, exam)
    before = env.frames_assessed
    frame(env, late)
    assert view(env, late)["phase"] == "waiting" and env.frames_assessed == before
    assert docente(env, exam, "consents")["confirmed"] == 1
    shown = view(env, late)
    assert shown["phase"] == "calibration" and shown["capture_frames"] is True


def test_una_estacion_sin_consentimiento_termina_sin_registro(env):  # noqa: F811
    exam = create_exam(env)
    first = join(env, exam)
    docente(env, exam, "consents")
    unconfirmed = join(env, exam)
    calibrate(env, first)
    docente(env, exam, "start")
    docente(env, exam, "finish")
    session = session_of(env, exam, unconfirmed)
    assert session.state is SessionState.CANCELLED
    assert env.guided.repository.list_captures(session.id) == ()
    assert view(env, unconfirmed)["message"] == EXAM_DEBRIEFING


def test_el_docente_no_ve_capturas_en_vivo(env):  # noqa: F811
    exam = create_exam(env)
    station = join(env, exam)
    docente(env, exam, "consents")
    calibrate(env, station)
    docente(env, exam, "start")
    frame(env, station)
    session_id = session_of(env, exam, station).id
    auth = headers(env, env.docente_a)
    assert env.client.get(f"/sessions/{session_id}/guided-results", headers=auth).status_code == 409
    assert env.client.get(f"/guided-sessions/{session_id}", headers=auth).status_code == 409
    step(env)
    docente(env, exam, "finish")
    results = env.client.get(f"/sessions/{session_id}/guided-results", headers=auth)
    assert results.status_code == 200 and results.json()["captures"]


def test_la_persona_puede_parar_y_lee_el_debriefing(env):  # noqa: F811
    exam = create_exam(env)
    station = join(env, exam)
    docente(env, exam, "consents")
    assert env.client.post(f"/participant-view/{station['view_token']}/stop").status_code == 200
    shown = view(env, station)
    assert shown["phase"] == "stopped" and shown["message"] == EXAM_DEBRIEFING
    assert session_of(env, exam, station).state is SessionState.CANCELLED


def test_la_pantalla_de_la_estacion_nunca_muestra_resultados(env):  # noqa: F811
    exam = create_exam(env)
    station = join(env, exam)
    docente(env, exam, "consents")
    calibrate(env, station)
    docente(env, exam, "start")
    for _ in range(3):
        frame(env, station)
        shown = view(env, station)
        step(env)
    assert set(shown) == {"phase", "message", "stimulus", "remaining_seconds", "capture_frames",
                          "frame_interval_ms", "abstract_notice"}
    text = str(shown).lower()
    assert "happiness" not in text and "confian" not in text and "emoci" not in text
    assert shown["frame_interval_ms"] == 500
