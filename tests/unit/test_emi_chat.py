"""Emi con un webhook falso que imita al workflow de n8n. Nunca se llama a la URL real."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import certifi
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import AuthenticationService, IdentityRegistrationService
from emotv.application.chat_categories import CATEGORIES, normalize_category
from emotv.application.chat_safety import (IDENTIFIER_CATEGORY, IDENTIFIER_MESSAGE, RISK_CATEGORY,
                                           identifier_kind, is_risky)
from emotv.application.chat_service import ChatService
from emotv.config import N8N_PRODUCTION_WEBHOOK_URL, ChatSettings, get_chat_settings
from emotv.domain import Role
from emotv.infrastructure.chat import N8nWebhookChatGateway, SimChatGateway
from emotv.infrastructure.chat.n8n_client import KEY_HEADER, _verify_setting
from emotv.infrastructure.chat.sim_client import SIM_KEY_HEADER
from emotv.infrastructure.persistence import (Base, PostgresChatRepository, PostgresConsentRepository,
                                               PostgresStudentRepository, PostgresUserRepository)
from emotv.interfaces.web.chat_router import create_chat_router

FAKE_URL = "https://n8n.invalid/webhook/emi-chat"
FAKE_KEY = "clave-de-prueba-no-real"


class FakeN8n:
    """Imita el contrato del webhook EMI y registra cada petición recibida."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.next: list[object] = []  # respuestas programadas; por defecto, dentro de alcance

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == FAKE_URL
        self.requests.append(request)
        body = json.loads(request.content)
        planned = self.next.pop(0) if self.next else None
        if isinstance(planned, Exception):
            raise planned
        if isinstance(planned, httpx.Response):
            return planned
        if request.headers.get(KEY_HEADER) != FAKE_KEY:
            return httpx.Response(403)
        in_scope = planned != "out"
        return httpx.Response(200, json={
            "answer": f"Respuesta a: {body['question']}" if in_scope else "Solo puedo ayudarte con temas de EMOtv.",
            "in_scope": in_scope,
            "category": "psicologia_general" if in_scope else "matematica",
            "request_id": body["request_id"],
        })

    def bodies(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def emi():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users = PostgresUserRepository(factory)
    auth = AuthenticationService(users, "emi-chat-test-secret-at-least-32-chars")
    identity = IdentityRegistrationService(users, PostgresStudentRepository(factory),
                                           PostgresConsentRepository(factory), auth)
    fake, clock = FakeN8n(), Clock()
    repository = PostgresChatRepository(factory)
    gateway = N8nWebhookChatGateway(FAKE_URL, FAKE_KEY, transport=httpx.MockTransport(fake.handler))
    service = ChatService(repository, gateway, ChatSettings(webhook_url=FAKE_URL, webhook_key=FAKE_KEY), clock)
    app = FastAPI()
    app.include_router(create_chat_router(service, auth, users))
    accounts = {}
    for code in ("PRUEBA-01", "PRUEBA-02"):
        user, _ = identity.register_student(f"{code.lower()}@example.org", "student-secret-123", code)
        accounts[code] = (user, {"Authorization": f"Bearer {auth.create_access_token(user)}"})
    for name, role in (("docente", Role.PSYCHOLOGIST), ("admin", Role.ADMIN), ("superadmin", Role.SUPERADMIN)):
        user = identity.register_user(f"{name}@example.org", "account-secret-123", role)
        accounts[name] = (user, {"Authorization": f"Bearer {auth.create_access_token(user)}"})
    with TestClient(app) as client:
        yield client, service, repository, fake, clock, accounts
    engine.dispose()


def ask(client, headers, question, conversation_id=None):
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return client.post("/chat", headers=headers, json=payload)


def test_sends_key_header_and_contract_body_without_user_data(emi):
    client, _, _, fake, _, accounts = emi
    user, headers = accounts["PRUEBA-01"]

    response = ask(client, headers, "¿Cómo funciona una actividad?")

    assert response.status_code == 200
    assert response.json()["answer"] == "Respuesta a: ¿Cómo funciona una actividad?"
    request = fake.requests[0]
    assert request.method == "POST" and request.headers[KEY_HEADER] == FAKE_KEY
    body = fake.bodies()[0]
    assert set(body) == {"request_id", "question", "history", "knowledge"}
    assert uuid.UUID(body["request_id"]) and body["knowledge"] == "" and body["history"] == []
    raw = request.content.decode()
    for private in (user.id, user.email, "PRUEBA-01", "session", "emotion", "confidence"):
        assert private not in raw


def test_knowledge_travels_in_every_request_and_category_is_returned(emi):
    client, service, _, fake, _, accounts = emi
    service.knowledge = lambda: "## Posturas\n- Brazos arriba"
    _, headers = accounts["PRUEBA-01"]
    fake.next.append("out")

    first = ask(client, headers, "¿Qué es una postura?").json()
    ask(client, headers, "Otra pregunta", first["conversation_id"])

    assert first["category"] == "matematica"
    assert [body["knowledge"] for body in fake.bodies()] == ["## Posturas\n- Brazos arriba"] * 2


def test_history_is_trimmed_and_excludes_out_of_scope_exchanges(emi):
    client, service, _, fake, _, accounts = emi
    service.settings = replace(service.settings, history_messages=4)
    _, headers = accounts["PRUEBA-01"]
    first = ask(client, headers, "Pregunta uno").json()["conversation_id"]
    fake.next.append("out")
    ask(client, headers, "¿Quién ganó el mundial?", first)
    for question in ("Pregunta tres", "Pregunta cuatro", "Pregunta cinco"):
        ask(client, headers, question, first)

    history = fake.bodies()[-1]["history"]

    assert history == [
        {"role": "user", "content": "Pregunta tres"},
        {"role": "assistant", "content": "Respuesta a: Pregunta tres"},
        {"role": "user", "content": "Pregunta cuatro"},
        {"role": "assistant", "content": "Respuesta a: Pregunta cuatro"},
    ]
    assert all("mundial" not in body_item["content"] for body in fake.bodies() for body_item in body["history"])


def test_out_of_scope_answer_is_stored_with_category_and_counted(emi):
    client, _, repository, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    fake.next.append("out")

    response = ask(client, headers, "Recomiéndame una película")

    assert response.status_code == 200 and response.json()["in_scope"] is False
    stored = repository.list_messages(response.json()["conversation_id"], 30)
    assert [(item.role, item.in_scope, item.category) for item in stored] == [
        ("user", False, "matematica"), ("assistant", False, "matematica"),
    ]
    assert repository.rejection_counts() == {"matematica": 1}


def test_users_only_access_their_own_conversations(emi):
    client, _, _, fake, _, accounts = emi
    _, owner = accounts["PRUEBA-01"]
    _, other = accounts["PRUEBA-02"]
    conversation_id = ask(client, owner, "Pregunta privada").json()["conversation_id"]

    assert client.get("/chat/conversations/current", headers=other).json() == {"conversation_id": None, "messages": []}
    foreign = ask(client, other, "Hola", conversation_id)
    assert foreign.status_code == 404
    assert len(fake.requests) == 1
    mine = client.get("/chat/conversations/current", headers=owner).json()
    assert mine["conversation_id"] == conversation_id
    assert [item["role"] for item in mine["messages"]] == ["user", "assistant"]


def test_new_conversation_starts_empty_and_current_returns_last_30(emi):
    client, service, _, _, _, accounts = emi
    service.settings = replace(service.settings, window_messages=100)
    _, headers = accounts["PRUEBA-01"]
    first = ask(client, headers, "Inicio").json()["conversation_id"]
    for index in range(20):
        ask(client, headers, f"Pregunta {index}", first)
    assert len(client.get("/chat/conversations/current", headers=headers).json()["messages"]) == 30

    created = client.post("/chat/conversations", headers=headers)

    assert created.status_code == 201 and created.json()["messages"] == []
    current = client.get("/chat/conversations/current", headers=headers).json()
    assert current == {"conversation_id": created.json()["conversation_id"], "messages": []}
    assert ask(client, headers, "Otra").json()["conversation_id"] == created.json()["conversation_id"]


def test_rate_limits_per_window_and_per_day(emi):
    client, service, _, fake, clock, accounts = emi
    service.settings = replace(service.settings, window_messages=2, window_minutes=10, daily_messages=3)
    _, headers = accounts["PRUEBA-01"]
    _, other = accounts["PRUEBA-02"]
    assert ask(client, headers, "Uno").status_code == 200
    assert ask(client, headers, "Dos").status_code == 200

    window = ask(client, headers, "Tres")
    assert window.status_code == 429 and "Espera unos minutos" in window.json()["detail"]
    assert ask(client, other, "Otra cuenta").status_code == 200

    clock.now += timedelta(minutes=11)
    assert ask(client, headers, "Tres").status_code == 200
    clock.now += timedelta(minutes=11)
    daily = ask(client, headers, "Cuatro")
    assert daily.status_code == 429 and "24 horas" in daily.json()["detail"]
    assert len(fake.requests) == 4


def test_risk_message_never_reaches_the_webhook(emi):
    client, service, repository, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]

    response = ask(client, headers, "A veces pienso en QUITARME LA VIDA")

    assert response.status_code == 200
    assert response.json() == {"conversation_id": None, "answer": service.settings.risk_message,
                               "in_scope": False, "category": RISK_CATEGORY}
    assert "emergencia" in response.json()["answer"] and not any(char.isdigit() for char in response.json()["answer"])
    assert fake.requests == []
    assert repository.rejection_counts() == {RISK_CATEGORY: 1}
    assert client.get("/chat/conversations/current", headers=headers).json()["messages"] == []


@pytest.mark.parametrize("text,risky", [
    ("me quiero morir", True), ("pienso en el suicidio", True), ("quiero hacerme daño", True),
    ("¿Qué es la tristeza?", False), ("¿Cómo se ve el miedo en el rostro?", False),
])
def test_risk_patterns(text, risky):
    assert is_risky(text) is risky


@pytest.mark.parametrize("planned,status,fragment", [
    (httpx.Response(502, json={"error": "llm_unavailable", "answer": "x", "request_id": "r"}), 502,
     "inteligencia artificial"),
    (httpx.Response(403), 502, "configuración del servidor"),
    (httpx.Response(401), 502, "configuración del servidor"),
    (httpx.Response(404), 502, "no está activo"),
    (httpx.Response(500), 502, "No se pudo contactar"),
    (httpx.Response(200, json={"answer": "sin in_scope", "category": "emotv"}), 502, "no se pudo leer"),
    (httpx.Response(200, json={"in_scope": True}), 502, "no se pudo leer"),
    (httpx.ReadTimeout("lento"), 504, "tardó demasiado"),
])
def test_webhook_failures_are_translated_and_logged_without_secrets(emi, caplog, planned, status, fragment):
    client, _, _, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    fake.next.append(planned)
    question = "Pregunta confidencial de prueba"

    with caplog.at_level(logging.INFO):
        response = ask(client, headers, question)

    assert response.status_code == status
    assert fragment in response.json()["detail"]
    request_id = fake.bodies()[0]["request_id"]
    assert request_id in caplog.text
    assert FAKE_KEY not in caplog.text and question not in caplog.text


def test_wrong_key_reaches_webhook_as_403(emi):
    client, service, repository, _, _, accounts = emi
    fake = FakeN8n()
    service.gateway = N8nWebhookChatGateway(FAKE_URL, "otra-clave", transport=httpx.MockTransport(fake.handler))
    _, headers = accounts["PRUEBA-01"]

    response = ask(client, headers, "Hola")

    assert response.status_code == 502 and "configuración" in response.json()["detail"]
    assert fake.requests[0].headers[KEY_HEADER] == "otra-clave"


def test_successful_call_logs_request_id_and_status(emi, caplog):
    client, _, _, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    with caplog.at_level(logging.INFO):
        ask(client, headers, "Pregunta de registro")
    assert f"request_id={fake.bodies()[0]['request_id']} gateway_status=200" in caplog.text
    assert "Pregunta de registro" not in caplog.text and FAKE_KEY not in caplog.text


def test_empty_key_disables_chat_with_503(emi):
    client, service, _, fake, _, accounts = emi
    service.gateway = None
    _, headers = accounts["PRUEBA-01"]

    response = ask(client, headers, "Hola")

    assert response.status_code == 503 and "Emi no está disponible" in response.json()["detail"]
    assert fake.requests == []
    assert get_chat_settings({"N8N_WEBHOOK_KEY": "  "}).webhook_key == ""
    with pytest.raises(ValueError, match="obligatoria"):
        N8nWebhookChatGateway(FAKE_URL, "")


def test_question_validation_in_spanish(emi):
    client, service, _, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    assert ask(client, headers, "   ").json()["detail"] == "Escribe una pregunta para Emi."
    too_long = ask(client, headers, "a" * (service.settings.max_question_chars + 1))
    assert too_long.status_code == 422 and "demasiado larga" in too_long.json()["detail"]
    assert fake.requests == []


def test_retention_purges_old_messages(emi):
    client, service, repository, _, clock, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    old = ask(client, headers, "Mensaje antiguo").json()["conversation_id"]
    clock.now += timedelta(days=91)

    ask(client, headers, "Mensaje nuevo", old)

    assert [item.content for item in repository.list_messages(old, 30)] == [
        "Mensaje nuevo", "Respuesta a: Mensaje nuevo",
    ]
    clock.now += timedelta(days=91)
    service.purge_expired()  # al arrancar también se borran las conversaciones vacías
    assert repository.list_messages(old, 30) == []
    assert client.get("/chat/conversations/current", headers=headers).json()["conversation_id"] is None


def test_settings_defaults_and_no_test_uses_the_production_url():
    settings = get_chat_settings({})
    assert settings.webhook_url == N8N_PRODUCTION_WEBHOOK_URL and settings.webhook_key == ""
    assert (settings.timeout_seconds, settings.history_messages, settings.retention_days) == (30.0, 10, 90)
    assert (settings.window_messages, settings.window_minutes, settings.daily_messages) == (20, 10, 200)
    assert FAKE_KEY not in repr(get_chat_settings({"N8N_WEBHOOK_KEY": FAKE_KEY}))
    assert FAKE_KEY not in repr(N8nWebhookChatGateway(FAKE_URL, FAKE_KEY))
    assert FAKE_URL != N8N_PRODUCTION_WEBHOOK_URL


def test_ssl_cert_file_is_respected(tmp_path):
    assert _verify_setting(None) is True
    assert _verify_setting(str(tmp_path / "missing.pem")) is True
    context = _verify_setting(certifi.where())
    assert not isinstance(context, bool)


# --- Público, filtro de identificadores, categorías y borrado ---

def test_emi_is_for_users_and_docentes_only(emi):
    client, _, _, fake, _, accounts = emi
    assert ask(client, accounts["docente"][1], "¿Qué es la teoría del apego?").status_code == 200
    for name in ("admin", "superadmin"):
        headers = accounts[name][1]
        assert ask(client, headers, "Hola").status_code == 403
        assert client.get("/chat/conversations/current", headers=headers).status_code == 403
        assert client.post("/chat/conversations", headers=headers).status_code == 403
    assert client.post("/chat", json={"question": "Hola"}).status_code == 401
    assert len(fake.requests) == 1


@pytest.mark.parametrize("question,kind", [
    ("El niño tiene DNI 45678912, ¿cómo lo evalúo?", "dni"),
    ("Su documento es 12.345.678", "dni"),
    ("Escríbele a la madre: madre.familia@example.org", "correo"),
    ("La tutora dejó su celular 987 654 321", "telefono"),
    ("Llamar al +51 (062) 51-2345 para coordinar", "telefono"),
])
def test_identifier_filter_blocks_without_calling_the_webhook(emi, caplog, question, kind):
    client, _, repository, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    assert identifier_kind(question) == kind

    with caplog.at_level(logging.INFO):
        response = ask(client, headers, question)

    assert response.status_code == 200
    assert response.json() == {"conversation_id": None, "answer": IDENTIFIER_MESSAGE,
                               "in_scope": False, "category": IDENTIFIER_CATEGORY}
    assert fake.requests == []
    # Solo la categoría: ni el texto ni el tipo de dato quedan guardados ni en el log.
    assert repository.rejection_counts() == {IDENTIFIER_CATEGORY: 1}
    assert client.get("/chat/conversations/current", headers=headers).json()["messages"] == []
    assert question not in caplog.text and "45678912" not in caplog.text


@pytest.mark.parametrize("text", [
    "Un niño de 7 años evita mirar a los ojos durante la sesión, ¿qué debo observar?",
    "¿Qué diferencias hubo entre los periodos 2024-2025 en la evaluación infantil?",
    "Aplicamos 3 cuestionarios y 12 estímulos en 15 minutos.",
    "Fecha de la sesión: 12/10/2026, puntaje 120 de 150.",
])
def test_identifier_filter_lets_ordinary_numbers_through(text):
    assert identifier_kind(text) is None


def test_case_description_is_sent_exactly_as_written(emi):
    client, _, _, fake, _, accounts = emi
    _, headers = accounts["docente"]
    case = ("  Una niña de 6 años llora cuando la madre sale del aula y no quiere\n"
            "participar en las actividades grupales. ¿Qué aspectos del desarrollo conviene revisar?  ")

    response = ask(client, headers, case)

    assert response.status_code == 200
    body = fake.bodies()[0]
    # Contrato sin cambios; la pregunta solo pierde los espacios de los extremos.
    assert set(body) == {"request_id", "question", "history", "knowledge"}
    assert body["question"] == case.strip()


def test_rejection_counter_uses_the_classifier_categories(emi):
    client, _, repository, fake, _, accounts = emi
    _, headers = accounts["PRUEBA-01"]
    for category in ("diagnostico_persona", "otra_psicologia", "categoria_inventada", ""):
        fake.next.append(httpx.Response(200, json={"answer": "No puedo ayudarte con eso.", "in_scope": False,
                                                   "category": category, "request_id": "r"}))
        ask(client, headers, "Pregunta")

    assert repository.rejection_counts() == {"diagnostico_persona": 1, "psicologia_general": 1, "otro": 2}


def test_category_catalog():
    for category in ("psicologia_general", "evaluacion_infantil", "uso_emotv", "limites_de_emi", "matematica",
                     "idiomas", "programacion", "diagnostico_persona", "reemplazo_docente", "cambio_de_reglas",
                     RISK_CATEGORY, IDENTIFIER_CATEGORY):
        assert category in CATEGORIES and normalize_category(category.upper()) == category
    assert normalize_category("plataforma") == "uso_emotv"
    assert normalize_category("x" * 300) == "otro"


def test_user_deletes_only_their_own_conversation(emi):
    client, _, repository, fake, _, accounts = emi
    _, owner = accounts["PRUEBA-01"]
    _, other = accounts["PRUEBA-02"]
    fake.next.append("out")
    conversation_id = ask(client, owner, "Pregunta para borrar").json()["conversation_id"]

    assert client.delete(f"/chat/conversations/{conversation_id}", headers=other).status_code == 404
    assert client.delete(f"/chat/conversations/{conversation_id}", headers=accounts["admin"][1]).status_code == 403
    assert len(repository.list_messages(conversation_id, 30)) == 2

    deleted = client.delete(f"/chat/conversations/{conversation_id}", headers=owner)

    assert deleted.status_code == 204
    assert repository.list_messages(conversation_id, 30) == []
    assert client.get("/chat/conversations/current", headers=owner).json() == {"conversation_id": None,
                                                                              "messages": []}
    assert client.delete(f"/chat/conversations/{conversation_id}", headers=owner).status_code == 404
    # El contador agregado no depende de la conversación.
    assert repository.rejection_counts() == {"matematica": 1}


# --- Sim (sim.ai): mismo contrato de Emi con el sobre de la API v2 ---

FAKE_SIM_URL = "https://sim.invalid/api/v2/workflows/emi/execute"


class FakeSim:
    """Imita la API v2 de Sim: ``{"input": ...}`` → ``{"data": {"status", "output"}}``."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.next: list[object] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == FAKE_SIM_URL
        self.requests.append(request)
        body = json.loads(request.content)["input"]
        planned = self.next.pop(0) if self.next else None
        if isinstance(planned, httpx.Response):
            return planned
        if request.headers.get(SIM_KEY_HEADER) != FAKE_KEY:
            return httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Invalid API key"}})
        output = planned if isinstance(planned, dict) else {
            "answer": f"Respuesta a: {body['question']}", "in_scope": True,
            "category": "uso_emotv", "request_id": body["request_id"],
        }
        return httpx.Response(200, json={"data": {"runId": "run-1", "status": "completed",
                                                  "output": output, "error": None}})

    def inputs(self) -> list[dict]:
        return [json.loads(request.content)["input"] for request in self.requests]


@pytest.fixture
def emi_sim(emi):
    client, service, repository, _, clock, accounts = emi
    fake = FakeSim()
    service.gateway = SimChatGateway(FAKE_SIM_URL, FAKE_KEY, transport=httpx.MockTransport(fake.handler))
    service.knowledge = lambda: "# Conocimiento de prueba"
    return client, service, repository, fake, clock, accounts


def test_sim_keeps_the_emi_contract(emi_sim):
    client, _, repository, fake, _, accounts = emi_sim
    user, headers = accounts["PRUEBA-01"]

    response = ask(client, headers, "¿Qué es EMOtv?")

    assert response.status_code == 200
    data = response.json()
    assert (data["answer"], data["in_scope"], data["category"]) == ("Respuesta a: ¿Qué es EMOtv?", True, "uso_emotv")
    request = fake.requests[0]
    assert request.headers[SIM_KEY_HEADER] == FAKE_KEY and KEY_HEADER not in request.headers
    sent = fake.inputs()[0]
    assert set(sent) == {"request_id", "question", "history", "knowledge"}
    assert sent["knowledge"] == "# Conocimiento de prueba" and sent["history"] == []
    assert user.id not in request.content.decode() and "prueba-01@example.org" not in request.content.decode()


@pytest.mark.parametrize("output", [
    {"data": {"answer": "Anidada", "in_scope": False, "category": "otro"}},
    {"content": json.dumps({"answer": "Anidada", "in_scope": False, "category": "otro"}), "model": "x"},
])
def test_sim_accepts_nested_or_structured_agent_output(emi_sim, output):
    client, _, _, fake, _, accounts = emi_sim
    fake.next.append(output)
    data = ask(client, accounts["PRUEBA-01"][1], "Pregunta").json()
    assert (data["answer"], data["in_scope"], data["category"]) == ("Anidada", False, "otro")


@pytest.mark.parametrize("planned,status,fragment", [
    (httpx.Response(200, json={"data": {"status": "failed", "output": {}, "error": "Groq"}}), 502,
     "inteligencia artificial"),
    (httpx.Response(200, json={"data": {"status": "completed", "output": {"error": "llm_unavailable",
                                                                          "answer": "x"}}}), 502,
     "inteligencia artificial"),
    (httpx.Response(429), 502, "inteligencia artificial"),
    (httpx.Response(402), 502, "inteligencia artificial"),
    (httpx.Response(401), 502, "configuración del servidor"),
    (httpx.Response(403), 502, "configuración del servidor"),
    (httpx.Response(404), 502, "no está activo"),
    (httpx.Response(500), 502, "No se pudo contactar"),
    (httpx.Response(200, json={"data": {"status": "completed", "output": {"answer": "sin in_scope"}}}), 502,
     "no se pudo leer"),
    (httpx.Response(200, text="no es json"), 502, "no se pudo leer"),
])
def test_sim_failures_are_translated_without_secrets(emi_sim, caplog, planned, status, fragment):
    client, _, _, fake, _, accounts = emi_sim
    fake.next.append(planned)
    question = "Pregunta confidencial de prueba"

    with caplog.at_level(logging.INFO):
        response = ask(client, accounts["PRUEBA-01"][1], question)

    assert response.status_code == status
    assert fragment in response.json()["detail"]
    assert fake.inputs()[0]["request_id"] in caplog.text
    assert FAKE_KEY not in caplog.text and question not in caplog.text


def test_sim_wrong_key_is_a_configuration_error(emi_sim):
    client, service, _, _, _, accounts = emi_sim
    fake = FakeSim()
    service.gateway = SimChatGateway(FAKE_SIM_URL, "otra-clave", transport=httpx.MockTransport(fake.handler))
    response = ask(client, accounts["PRUEBA-01"][1], "Hola")
    assert response.status_code == 502 and "configuración" in response.json()["detail"]


def test_provider_settings():
    settings = get_chat_settings({})
    assert settings.provider == "sim" and settings.sim_workflow_url == "" and settings.sim_api_key == ""
    sim = get_chat_settings({"SIM_WORKFLOW_URL": FAKE_SIM_URL, "SIM_API_KEY": FAKE_KEY})
    assert (sim.sim_workflow_url, sim.sim_api_key) == (FAKE_SIM_URL, FAKE_KEY)
    assert FAKE_KEY not in repr(sim) and FAKE_KEY not in repr(SimChatGateway(FAKE_SIM_URL, FAKE_KEY))
    assert get_chat_settings({"CHAT_PROVIDER": " N8N "}).provider == "n8n"
    assert get_chat_settings({"CHAT_TIMEOUT_SECONDS": "12", "N8N_TIMEOUT_SECONDS": "40"}).timeout_seconds == 12
    assert get_chat_settings({"N8N_TIMEOUT_SECONDS": "40"}).timeout_seconds == 40
    with pytest.raises(ValueError, match="CHAT_PROVIDER"):
        get_chat_settings({"CHAT_PROVIDER": "gemini"})
    with pytest.raises(ValueError, match="obligatoria"):
        SimChatGateway(FAKE_SIM_URL, "")
    with pytest.raises(ValueError, match="URL"):
        SimChatGateway("sim.invalid", FAKE_KEY)
