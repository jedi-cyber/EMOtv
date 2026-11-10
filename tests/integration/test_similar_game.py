"""Juego «Busca la misma emoción» (bloque 6): la imagen modelo y otras caras;
la persona elige la de la misma emoción. Reutiliza el paso, el motor y los
contadores del juego de emparejar. Las imágenes se comprueban al guardar: la
pareja no es la misma imagen otra vez y otra opción se le parece más a la
modelo que la pareja, para que se resuelva por la emoción."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import cv2
import numpy as np
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import SIMILAR_QUESTION, SIMILAR_RETRY, SIMILAR_RETRY_HELPED, GameOutcome
from emotv.domain.protocol import ProtocolStep, StepKind
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from emotv.infrastructure.stimuli.initial_bank import TITLES, draw
from tests.integration.test_guided_sessions import begin_steps, guided, state, view
from tests.integration.test_practice_persistence import engine, factory, protocol  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import approve, png_bytes, upload_stimulus

THREE = ("happiness", "sadness", "anger")


def add(env, expression, image, title):  # noqa: F811
    return approve(env, env.docente_a, upload_stimulus(env, env.docente_a, image=image, title=title,
                                                       expected_expression=expression))


def bank(env, expressions=THREE, variants=(0, 1, 2)):  # noqa: F811
    """Dibujos del banco inicial: por emoción, una cara por variante (otro color)."""
    return {item["id"]: (expression, variant)
            for expression in expressions for variant in variants
            for item in [add(env, expression, draw(expression, variant), f"{TITLES[expression]} {variant + 1}")]}


def similar(rounds=2, options=2, seconds=30, ids=()):
    return {"kind": "game", "game_type": "similar", "rounds": rounds, "option_count": options,
            "exposure_seconds": seconds, "game_stimulus_ids": list(ids)}


def save(env, steps, for_children=False):  # noqa: F811
    return env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Misma emoción", "description": "", "for_children": for_children, "steps": steps})


def start(env, *steps):  # noqa: F811
    response = save(env, list(steps))
    assert response.status_code == 201, response.text
    session_id, token = guided(env, response.json())
    begin_steps(env, session_id, token)
    return session_id, token


def act(env, token, action, key=None):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/game",
                           json={"action": action, **({"expression": key} if key else {})})


def round_info(env, session_id):  # noqa: F811
    return state(env, session_id)["game"]


def correct_key(info):
    return next(item["key"] for item in info["option_details"] if item["expression"] == info["target_expression"])


def wrong_keys(info):
    return [item["key"] for item in info["option_details"] if item["expression"] != info["target_expression"]
            and item["key"] not in info["tried"] and item["key"] != info["removed"]]


# --- Dominio --------------------------------------------------------------------------------


def test_el_paso_guarda_la_modelo_y_una_imagen_por_opcion():
    step = ProtocolStep.similar_game(2, 3, 20)
    assert step.is_game and step.images_per_round == 4 and step.seconds_limit == 40
    filled = replace(step, game_stimulus_ids=tuple(f"s{index}" for index in range(8)))
    assert filled.round_images(1) == ("s4", "s5", "s6", "s7")
    assert ProtocolStep.matching_game(2, 3).images_per_round == 1
    with pytest.raises(ValueError, match="más imágenes"):
        ProtocolStep.similar_game(2, 2, 20, tuple(f"s{index}" for index in range(7)))
    with pytest.raises(ValueError, match="juegos disponibles"):
        ProtocolStep(None, 20, 0, kind=StepKind.GAME, game_type="memoria", rounds=2, option_count=2)


# --- Elección y comprobación de las imágenes al guardar --------------------------------------


def test_cada_ronda_lleva_una_pareja_que_se_ve_distinta_y_otras_que_se_parecen_mas(env):  # noqa: F811
    images = bank(env)
    response = save(env, [similar(rounds=3, options=3)])
    assert response.status_code == 201, response.text
    [step] = response.json()["steps"]
    ids = step["game_stimulus_ids"]
    assert len(ids) == 3 * 4
    pairs = set()
    for start_at in range(0, len(ids), 4):
        model, match, *others = (images[item] for item in ids[start_at:start_at + 4])
        # La misma emoción, en otra cara (otra variante), nunca la misma imagen.
        assert model[0] == match[0] and model[1] != match[1]
        # Las otras opciones son de emociones distintas entre sí y de la modelo.
        assert len({item[0] for item in others}) == 2 and model[0] not in {item[0] for item in others}
        # Al menos una se parece más a la modelo (misma variante): el color no lleva a la respuesta.
        assert any(item[1] == model[1] for item in others)
        pairs.add(frozenset(ids[start_at:start_at + 2]))
    assert len(pairs) == 3
    # Se procuran emociones distintas en las rondas.
    assert len({images[ids[index]][0] for index in (0, 4, 8)}) == 3
    # Al editar sin cambios se conservan.
    edited = env.client.put(f"/protocols/{response.json()['id']}", headers=headers(env, env.user_1), json={
        "name": "Misma emoción", "description": "", "for_children": False,
        "steps": [similar(rounds=3, options=3, ids=ids)]})
    assert edited.status_code == 200, edited.text
    assert edited.json()["steps"][0]["game_stimulus_ids"] == ids



def test_el_banco_inicial_alcanza_para_seis_rondas_con_cuatro_caras(env):  # noqa: F811
    """Lo que dice docs/adaptacion-psicoeducacion.md (§17): 6 emociones con 3
    variantes alcanzan para 6 rondas de emociones distintas y 4 caras."""
    images = bank(env, expressions=tuple(TITLES))
    response = save(env, [similar(rounds=6, options=4)])
    assert response.status_code == 201, response.text
    ids = response.json()["steps"][0]["game_stimulus_ids"]
    assert len({images[ids[index]][0] for index in range(0, len(ids), 5)}) == 6

def test_la_misma_imagen_guardada_otra_vez_no_cuenta_como_pareja(env):  # noqa: F811
    for expression in THREE:
        image = draw(expression, 0)
        add(env, expression, image, f"{TITLES[expression]} A")
        # La misma cara recodificada como JPEG y con otro tamaño.
        decoded = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
        ok, jpeg = cv2.imencode(".jpg", cv2.resize(decoded, (300, 300)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        assert ok
        add(env, expression, jpeg.tobytes(), f"{TITLES[expression]} B")
    response = save(env, [similar(rounds=2, options=2)])
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "se vean distintas" in detail and "alcanza para 0" in detail


def test_si_la_pareja_es_la_que_mas_se_parece_no_se_usa(env, monkeypatch):  # noqa: F811
    """Con un aspecto controlado: la pareja de alegría se parece más a la modelo
    que la de otra emoción, así que la ronda se resolvería por el aspecto."""
    looks = {}
    for index, (expression, look) in enumerate((("happiness", 0), ("happiness", 20), ("sadness", 60))):
        image = png_bytes(f"imagen {index}".encode())
        item = add(env, expression, image, f"Cara {index}")
        looks[item["id"]] = look
    stored = {item_id: env.stimuli.image(env.docente_a, item_id)[1] for item_id in looks}
    by_bytes = {data: looks[item_id] for item_id, data in stored.items()}
    monkeypatch.setattr(env.protocols, "appearance", lambda data: (by_bytes.get(data, 255),) * 4)
    response = save(env, [similar(rounds=2, options=2)])
    assert response.status_code == 422 and "alcanza para 0" in response.json()["detail"]


def test_sin_material_suficiente_dice_que_falta(env):  # noqa: F811
    bank(env, variants=(0,))
    response = save(env, [similar(rounds=2, options=2)])
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "dos imágenes emocionales aprobadas de la misma emoción" in detail and "Agrega imágenes" in detail
    # Para niños solo cuentan las imágenes «Para niños».
    assert "«Para niños»" in save(env, [similar()], for_children=True).json()["detail"]


def test_sin_comparar_el_aspecto_no_se_guarda(env, monkeypatch):  # noqa: F811
    bank(env)
    monkeypatch.setattr(env.protocols, "appearance", None)
    response = save(env, [similar()])
    assert response.status_code == 422 and "no puede comprobar" in response.json()["detail"]


# --- Sesión -----------------------------------------------------------------------------------


def test_la_persona_elige_entre_caras_con_ayuda_reintento_y_explicacion(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, similar(rounds=2, options=3))
    shown = view(env, token).json()
    block = shown["game"]
    assert block["game_type"] == "similar" and block["question"] == SIMILAR_QUESTION
    # Cada opción es una imagen: «Cara 1», sin decir su emoción.
    assert [item["label"] for item in block["options"]] == ["Cara 1", "Cara 2", "Cara 3"]
    assert shown["capture_frames"] is False
    info = round_info(env, session_id)
    assert {item["stimulus_id"] for item in info["option_details"]}.isdisjoint({info["stimulus_id"]})
    # La modelo y cada opción se piden por separado; una clave que no está no existe.
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    for item in block["options"]:
        assert env.client.get(f"/participant-view/{token}/game/option/{item['key']}").status_code == 200
    assert env.client.get(f"/participant-view/{token}/game/option/9").status_code == 404
    assert act(env, token, "answer", "happiness").status_code == 422     # al buscar se elige un lugar

    # La ayuda quita una cara de otra emoción.
    assert act(env, token, "help").status_code == 200
    info = round_info(env, session_id)
    assert info["removed"] is not None and info["removed"] != correct_key(info)
    assert [item["available"] for item in view(env, token).json()["game"]["options"]].count(False) == 1
    [miss] = wrong_keys(info)
    assert act(env, token, "answer", miss).status_code == 200
    block = view(env, token).json()["game"]
    # Ya pidió ayuda: no se le vuelve a ofrecer.
    assert block["state"] == "retry" and block["message"] == SIMILAR_RETRY_HELPED
    answer = correct_key(info)
    assert act(env, token, "answer", answer).status_code == 200
    block = view(env, token).json()["game"]
    assert block["state"] == "matched" and block["answer"] == answer
    assert block["message"].startswith("Lo encontraste: las dos caras muestran la misma emoción")
    assert "explanation" in block
    assert act(env, token, "next").status_code == 200

    # Segunda ronda: la registra quien conduce.
    info = round_info(env, session_id)
    assert info["round"] == 2
    response = env.client.post(f"/guided-sessions/{session_id}/game", headers=headers(env, env.user_1),
                               json={"action": "answer", "expression": correct_key(info)})
    assert response.status_code == 200, response.text
    assert act(env, token, "next").status_code == 200
    [item] = env.guided.repository.list_game_attempts(session_id)
    assert item.game_type == "similar" and item.outcome is GameOutcome.COMPLETED
    assert (item.rounds_done, item.matched, item.first_try, item.help_used, item.by_conductor) == (2, 2, 1, 1, 1)
    summary = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1))
    assert summary.status_code == 200
    [exercise] = summary.json()["game"]["exercises"]
    assert exercise["game_type"] == "similar" and exercise["sentence"].startswith("Jugó 2 de 2 rondas.")


def test_tras_dos_caras_de_otra_emocion_se_muestra_la_pareja(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, similar(rounds=2, options=3))
    first, second = wrong_keys(round_info(env, session_id))
    assert act(env, token, "answer", first).status_code == 200
    assert view(env, token).json()["game"]["message"] == SIMILAR_RETRY        # sin ayuda todavía, se ofrece
    assert act(env, token, "answer", second).status_code == 200
    block = view(env, token).json()["game"]
    assert block["state"] == "shown" and block["message"].startswith("Esta cara muestra la misma emoción: ")
    assert block["answer"] == correct_key(round_info(env, session_id))


def test_en_el_juego_de_nombres_no_hay_imagenes_por_opcion(env):  # noqa: F811
    bank(env, variants=(0,))
    _, token = start(env, {"kind": "game", "game_type": "matching", "rounds": 2, "option_count": 2,
                           "exposure_seconds": 30})
    assert env.client.get(f"/participant-view/{token}/game/option/1").status_code == 404


# --- Base y migración -------------------------------------------------------------------------


def test_la_base_guarda_el_juego_semejante(factory):  # noqa: F811
    repository = PostgresProtocolRepository(factory)
    repository.add(replace(protocol(), id="p-similar", family_id="f-similar",
                           steps=(ProtocolStep.similar_game(2, 2, 30, ("s1",) * 6),)))
    [step] = repository.get("p-similar").steps
    assert step.game_type == "similar" and len(step.game_stimulus_ids) == 6


def _migration():
    path = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261107_42_similar_game.py"
    spec = importlib.util.spec_from_file_location("migration_42", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_42_sigue_al_primer_juego():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261107_42", "20261106_41")


def test_la_migracion_42_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    def checks():
        return {item["name"]: item["sqltext"] for item in inspect(engine).get_check_constraints("game_results")}

    assert "'similar'" in checks()["ck_game_results_type"]
    _run(engine, "downgrade")
    assert "'similar'" not in checks()["ck_game_results_type"]
    _run(engine, "upgrade")
    assert "'similar'" in checks()["ck_game_results_type"]
    steps = {item["name"]: item["sqltext"] for item in inspect(engine).get_check_constraints("protocol_steps")}
    assert "'similar'" in steps["ck_protocol_steps_practice"]
