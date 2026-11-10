"""Las imágenes abstractas están congeladas: solo se suben y aplican con
ABSTRACT_STIMULI_ENABLED=true."""
from __future__ import annotations

import pytest

from emotv.config import get_abstract_stimuli_enabled


def test_las_abstractas_estan_apagadas_por_defecto():
    assert get_abstract_stimuli_enabled({}) is False
    assert get_abstract_stimuli_enabled({"ABSTRACT_STIMULI_ENABLED": " "}) is False


def test_las_abstractas_se_activan_solo_de_forma_expresa():
    assert get_abstract_stimuli_enabled({"ABSTRACT_STIMULI_ENABLED": "true"}) is True
    assert get_abstract_stimuli_enabled({"ABSTRACT_STIMULI_ENABLED": "FALSE"}) is False


def test_un_valor_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="ABSTRACT_STIMULI_ENABLED"):
        get_abstract_stimuli_enabled({"ABSTRACT_STIMULI_ENABLED": "si"})
