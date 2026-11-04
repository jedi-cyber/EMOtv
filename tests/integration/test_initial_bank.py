"""Banco inicial de dibujos y plantilla «Emociones básicas 4 a 6 años»: solo el
administrador agrega el banco, repetirlo no duplica y la plantilla arma un
protocolo para niños, accesible, con un «¿Qué emoción es?» por emoción."""
from __future__ import annotations

import cv2
import numpy as np

from emotv.infrastructure.stimuli.initial_bank import TITLES, initial_drawings
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def add_bank(env, user):  # noqa: F811
    return env.client.post("/stimuli/initial-bank", headers=headers(env, user))


def test_los_dibujos_son_png_de_seis_emociones_y_tres_variantes():
    drawings = list(initial_drawings())
    assert len(drawings) == 18
    assert {item.expected_expression for item in drawings} == set(TITLES)
    assert len({item.title for item in drawings}) == 18
    image = cv2.imdecode(np.frombuffer(drawings[0].image, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None and image.shape[:2] == (512, 512)


def test_solo_el_administrador_agrega_el_banco_y_no_se_duplica(env):  # noqa: F811
    for user in (env.superadmin, env.docente_a, env.user_1):
        assert add_bank(env, user).status_code == 403
    first = add_bank(env, env.admin)
    assert first.status_code == 200 and first.json() == {"added": 18, "total": 18}
    assert add_bank(env, env.admin).json() == {"added": 0, "total": 18}
    # Todos los ven como institucionales, aprobados y aptos para niños.
    bank = [item for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()
            if item["category"] == "Banco inicial EMOtv"]
    assert len(bank) == 18
    assert all(item["approved"] and item["scope"] == "institution" and item["min_age"] == 3 for item in bank)


def test_un_dibujo_retirado_no_vuelve_al_repetir(env):  # noqa: F811
    add_bank(env, env.admin)
    item = env.stimuli.initial_bank_present()[0]
    retired = env.client.put(f"/stimuli/{item.id}/active", headers=headers(env, env.admin), json={"active": False})
    assert retired.status_code == 200
    assert add_bank(env, env.admin).json()["added"] == 0


def test_la_plantilla_necesita_el_banco(env):  # noqa: F811
    response = env.client.post("/protocols/starter", headers=headers(env, env.user_1))
    assert response.status_code == 422
    assert "banco inicial" in response.json()["detail"]


def test_la_plantilla_crea_un_protocolo_infantil_accesible_de_seis_pasos(env):  # noqa: F811
    add_bank(env, env.admin)
    response = env.client.post("/protocols/starter", headers=headers(env, env.user_1))
    assert response.status_code == 201, response.text
    protocol = response.json()
    assert protocol["name"] == "Emociones básicas 4 a 6 años"
    assert protocol["for_children"] is True and protocol["accessible"] is True and protocol["owned_by_me"] is True
    steps = protocol["steps"]
    assert len(steps) == 6 and all(step["kind"] == "recognition" for step in steps)
    assert all(step["option_count"] == 2 and step["exposure_seconds"] == 30 for step in steps)
    by_id = {item["id"]: item for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()}
    assert [by_id[step["stimulus_id"]]["expected_expression"] for step in steps] == list(TITLES)
    # Cada quien recibe su propia copia; el docente también.
    assert env.client.post("/protocols/starter", headers=headers(env, env.docente_a)).status_code == 201
    for user in (env.admin, env.superadmin):
        assert env.client.post("/protocols/starter", headers=headers(env, user)).status_code == 403
