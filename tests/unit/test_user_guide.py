"""Guía de uso: cada papel tiene sus temas, la guía nombra solo botones y
pantallas que existen en la interfaz y no describe funciones congeladas ni
afirma lo que EMOtv no hace."""
from __future__ import annotations

import re
from pathlib import Path

from emotv.application.user_guide import GUIDE, guide_for, guide_knowledge
from emotv.domain import Role

WEB = Path(__file__).resolve().parents[2] / "web" / "src"


def _all_text() -> str:
    return " ".join(" ".join((topic.title, *topic.steps, topic.note or "")) for topic in GUIDE)


def test_cada_papel_tiene_sus_temas():
    ids = {role: {topic.id for topic in guide_for(role)} for role in Role}
    assert {"first-steps", "material", "conduct", "after"} <= ids[Role.STUDENT]
    assert {"supervise", "teach", "conduct"} <= ids[Role.PSYCHOLOGIST]
    assert "after" not in ids[Role.PSYCHOLOGIST] and "supervise" not in ids[Role.STUDENT]
    # La administración y el soporte no conducen sesiones ni ven resultados.
    for role in (Role.ADMIN, Role.SUPERADMIN):
        assert not ids[role] & {"conduct", "after", "supervise", "material"}
    assert {"admin-accounts", "admin-stimuli"} <= ids[Role.ADMIN] and "support" in ids[Role.SUPERADMIN]
    assert len({topic.id for topic in GUIDE}) == len(GUIDE)


def test_los_nombres_entre_comillas_existen_en_la_interfaz():
    source = " ".join(path.read_text(encoding="utf-8") for path in WEB.rglob("*.ts*"))
    names = set(re.findall(r"«([^»]+)»", _all_text()))
    assert len(names) > 30
    missing = sorted(name for name in names if name not in source)
    assert missing == [], missing


def test_no_describe_funciones_congeladas_ni_promete_lo_que_no_hace():
    text = _all_text().lower()
    for word in ("postura", "actividad", "abstract", "examen", "puntaje de", "diagnóstico de"):
        assert word not in text, word
    # Nunca valora a la persona ni dice que EMOtv sabe lo que siente.
    for claim in ("detecta lo que siente", "evalúa a la persona", "diagnostica"):
        assert claim not in text
    # Sin identificadores internos ni papeles antiguos.
    assert "student" not in text and "psychologist" not in text and "estudiante" not in text


def test_emi_recibe_solo_los_temas_de_usuario_y_docente():
    text = guide_knowledge()
    assert "### Conducir una sesión (Usuario, Docente)" in text
    assert "### Después de la sesión (Usuario)" in text and "### Supervisar al grupo (Docente)" in text
    assert "Cuentas y grupos" not in text and "Soporte técnico" not in text
