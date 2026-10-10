"""run_eval.py con un EMOtv falso: no usa red ni califica respuestas."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

import httpx

from scripts.chatbot.run_eval import load_questions, run


def test_eval_file_has_the_35_planned_questions():
    questions = load_questions()
    assert len(questions) == 35 and len({item.id for item in questions}) == 35
    assert Counter(item.id[0] for item in questions) == {"A": 10, "B": 5, "C": 10, "D": 5, "E": 5}
    assert any("traduce al inglés qué es la tristeza" in item.question.lower() for item in questions)


def test_run_saves_answers_with_scope_and_category_and_waits_on_429(tmp_path):
    questions = load_questions()[:3]
    seen, waits, limited = [], [], [True]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/token":
            assert b"password=secreto-de-prueba" in request.content
            return httpx.Response(200, json={"access_token": "tk-prueba", "token_type": "bearer"})
        assert request.headers["Authorization"] == "Bearer tk-prueba"
        if request.url.path == "/chat/conversations":
            return httpx.Response(201, json={"conversation_id": f"c{len(seen)}", "messages": []})
        body = json.loads(request.content)
        if limited[0]:
            limited[0] = False
            return httpx.Response(429, json={"detail": "Espera unos minutos"})
        seen.append(body)
        return httpx.Response(200, json={"conversation_id": body["conversation_id"], "answer": "Respuesta",
                                         "in_scope": True, "category": "emotv"})

    with httpx.Client(base_url="http://emotv.invalid", transport=httpx.MockTransport(handler)) as client:
        json_path, markdown_path = run(client, "prueba-01@example.org", "secreto-de-prueba", questions,
                                       base_url="http://emotv.invalid", output_dir=tmp_path,
                                       retry_wait=5, sleep=waits.append, now=datetime(2026, 10, 9, 18, 30))

    assert waits == [5]
    assert [item["question"] for item in seen] == [item.question for item in questions]
    assert len({item["conversation_id"] for item in seen}) == 3  # una conversación por pregunta
    assert json_path.name == "emi-eval-20261009-183000.json"
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert [(item["in_scope"], item["category"], item["review"]) for item in report["results"]] == [
        (True, "emotv", "")] * 3
    text = json_path.read_text(encoding="utf-8") + markdown_path.read_text(encoding="utf-8")
    assert "secreto-de-prueba" not in text and "tk-prueba" not in text and "prueba-01@" not in text
