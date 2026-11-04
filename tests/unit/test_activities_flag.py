"""Las actividades corporales están congeladas: solo se inician con
ACTIVITIES_ENABLED=true."""
from __future__ import annotations

import pytest

from emotv.config import get_activities_enabled


def test_las_actividades_estan_apagadas_por_defecto():
    assert get_activities_enabled({}) is False
    assert get_activities_enabled({"ACTIVITIES_ENABLED": " "}) is False


def test_las_actividades_se_activan_solo_de_forma_expresa():
    assert get_activities_enabled({"ACTIVITIES_ENABLED": "true"}) is True
    assert get_activities_enabled({"ACTIVITIES_ENABLED": "FALSE"}) is False


def test_un_valor_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="ACTIVITIES_ENABLED"):
        get_activities_enabled({"ACTIVITIES_ENABLED": "si"})
