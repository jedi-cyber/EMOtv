"""Envía las preguntas de tests/chatbot/emi_eval.md al endpoint /chat de EMOtv.

Guarda cada respuesta con in_scope y category en reports/chatbot/ para revisión
humana. No califica las respuestas.

Uso (con EMOtv en marcha, por ejemplo con Docker Compose):
    python scripts/chatbot/run_eval.py --base-url http://localhost:8080

Usa una cuenta de prueba (código PRUEBA-NN) con el consentimiento aceptado.
El correo y la contraseña se piden por consola o se leen de EMOTV_EVAL_EMAIL y
EMOTV_EVAL_PASSWORD; nunca se escriben en el informe. Cada pregunta va en una
conversación nueva para que no influya en las siguientes. Las 35 preguntas
consumen cuota de Groq y superan el límite de 20 mensajes cada 10 minutos: el
script espera y reintenta cuando EMOtv responde 429.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "tests" / "chatbot" / "emi_eval.md"
OUTPUT_DIR = ROOT / "reports" / "chatbot"
ROW = re.compile(r"^\| (?P<id>[A-E]\d{2}) \| (?P<question>.+?) \| (?P<expected>true o false|true|false) \| "
                 r"(?P<behavior>.+?) \|$")


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected_in_scope: str
    expected_behavior: str


@dataclass
class Result:
    id: str
    question: str
    expected_in_scope: str
    expected_behavior: str
    status_code: int | None
    answer: str | None
    in_scope: bool | None
    category: str | None
    error: str | None
    seconds: float
    review: str = ""  # lo completa una persona


def load_questions(path: Path = QUESTIONS) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if match := ROW.match(line.strip()):
            questions.append(Question(match["id"], match["question"], match["expected"], match["behavior"]))
    return questions


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/auth/token", data={"username": email, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"No se pudo iniciar sesión ({response.status_code}): {_detail(response)}")
    return response.json()["access_token"]


def ask(client: httpx.Client, headers: dict[str, str], question: Question, *, retry_wait: float,
        max_retries: int, sleep: Callable[[float], None] = time.sleep) -> Result:
    started = time.monotonic()
    for attempt in range(max_retries + 1):
        conversation = client.post("/chat/conversations", headers=headers)
        if conversation.status_code != 201:
            return _failure(question, conversation, started)
        response = client.post("/chat", headers=headers, json={
            "conversation_id": conversation.json()["conversation_id"], "question": question.question})
        if response.status_code == 429 and attempt < max_retries:
            print(f"  {question.id}: límite de uso alcanzado; espero {retry_wait:g} s ({_detail(response)})")
            sleep(retry_wait)
            continue
        if response.status_code != 200:
            return _failure(question, response, started)
        body = response.json()
        return Result(question.id, question.question, question.expected_in_scope, question.expected_behavior,
                      200, body.get("answer"), body.get("in_scope"), body.get("category"), None,
                      round(time.monotonic() - started, 2))
    raise AssertionError("inalcanzable")


def write_report(results: list[Result], base_url: str, output_dir: Path, now: datetime) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"emi-eval-{now:%Y%m%d-%H%M%S}"
    data = {"generated_at": now.isoformat(timespec="seconds"), "base_url": base_url,
            "note": "Revisión humana: completar 'review' en cada respuesta. Sin calificación automática.",
            "results": [asdict(result) for result in results]}
    json_path = output_dir / f"{stem}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Evaluación de Emi · {now:%Y-%m-%d %H:%M}", "", f"Servidor: {base_url}", "",
             "Revisar a mano cada respuesta según tests/chatbot/emi_eval.md. Anotar en «Revisión»: "
             "correcta, aceptable o incorrecta, y el motivo.", ""]
    for result in results:
        lines += [f"## {result.id}. {result.question}", "",
                  f"- in_scope esperado: {result.expected_in_scope} · recibido: {result.in_scope}"
                  f" · category: {result.category} · HTTP {result.status_code} · {result.seconds} s",
                  f"- Esperado: {result.expected_behavior}", "",
                  "> " + (result.answer or f"(sin respuesta: {result.error})").replace("\n", "\n> "), "",
                  "Revisión: ", ""]
    markdown_path = output_dir / f"{stem}.md"
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


def run(client: httpx.Client, email: str, password: str, questions: list[Question], *, base_url: str,
        output_dir: Path, retry_wait: float = 60, max_retries: int = 15,
        sleep: Callable[[float], None] = time.sleep, now: datetime | None = None) -> tuple[Path, Path]:
    headers = {"Authorization": f"Bearer {login(client, email, password)}"}
    results = []
    for question in questions:
        print(f"{question.id}: {question.question}")
        results.append(ask(client, headers, question, retry_wait=retry_wait, max_retries=max_retries, sleep=sleep))
    return write_report(results, base_url, output_dir, now or datetime.now())


def _failure(question: Question, response: httpx.Response, started: float) -> Result:
    return Result(question.id, question.question, question.expected_in_scope, question.expected_behavior,
                  response.status_code, None, None, None, _detail(response), round(time.monotonic() - started, 2))


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", ""))
    except ValueError:
        return response.text[:200]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://localhost:8080", help="URL de EMOtv (web o API)")
    parser.add_argument("--only", nargs="*", help="ids a enviar, por ejemplo A01 C07")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--retry-wait", type=float, default=60, help="segundos de espera tras un 429")
    parser.add_argument("--timeout", type=float, default=60, help="segundos por petición (n8n puede tardar)")
    args = parser.parse_args(argv)

    questions = load_questions()
    if args.only:
        questions = [item for item in questions if item.id in set(args.only)]
    email = os.environ.get("EMOTV_EVAL_EMAIL") or input("Correo de la cuenta de prueba: ").strip()
    password = os.environ.get("EMOTV_EVAL_PASSWORD") or getpass.getpass("Contraseña: ")
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        json_path, markdown_path = run(client, email, password, questions, base_url=args.base_url,
                                       output_dir=args.output_dir, retry_wait=args.retry_wait)
    print(f"Informe para revisión humana: {markdown_path}\nDatos: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
