"""GET /guide: cada cuenta recibe los temas de su papel; sin sesión, 401."""
from __future__ import annotations

from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def topics(env, user):  # noqa: F811
    response = env.client.get("/guide", headers=headers(env, user))
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()["topics"]}


def test_cada_cuenta_ve_la_guia_de_su_papel(env):  # noqa: F811
    user = topics(env, env.user_1)
    assert "conduct" in user and "supervise" not in user
    assert user["conduct"]["title"] == "Conducir una sesión" and user["conduct"]["steps"]
    assert "supervise" in topics(env, env.docente_a)
    admin = topics(env, env.admin)
    assert "admin-stimuli" in admin and "conduct" not in admin
    assert "support" in topics(env, env.superadmin)


def test_la_guia_pide_sesion_iniciada(env):  # noqa: F811
    assert env.client.get("/guide").status_code == 401
