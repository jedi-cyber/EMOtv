import pytest

from emotv.infrastructure.chat import FlowiseClient


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"text": "Respuesta principal"}, "Respuesta principal"),
        ({"answer": "Respuesta alternativa"}, "Respuesta alternativa"),
        ("Respuesta directa", "Respuesta directa"),
        ({"text": "   "}, ""),
    ],
)
def test_extracts_supported_flowise_responses(payload, expected):
    assert FlowiseClient._extract_answer(payload) == expected


def test_rejects_invalid_url_and_timeout():
    with pytest.raises(ValueError, match="URL HTTP"):
        FlowiseClient("cloud.flowiseai.com/chat")
    with pytest.raises(ValueError, match="mayor que cero"):
        FlowiseClient("https://cloud.flowiseai.com/chat", timeout_seconds=0)
