"""El examen simulado está congelado: su API solo se monta con EXAMS_ENABLED=true."""
from __future__ import annotations

import pytest

from emotv.config import get_exams_enabled


def test_el_examen_esta_apagado_por_defecto():
    assert get_exams_enabled({}) is False
    assert get_exams_enabled({"EXAMS_ENABLED": " "}) is False


def test_el_examen_se_activa_solo_de_forma_expresa():
    assert get_exams_enabled({"EXAMS_ENABLED": "true"}) is True
    assert get_exams_enabled({"EXAMS_ENABLED": "FALSE"}) is False


def test_un_valor_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="EXAMS_ENABLED"):
        get_exams_enabled({"EXAMS_ENABLED": "si"})
