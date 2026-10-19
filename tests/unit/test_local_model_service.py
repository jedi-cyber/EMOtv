from datetime import datetime, timezone

import pytest

from emotv.application.local_model_service import (
    FERPLUS_MODEL_ID,
    HSEMOTION_MODEL_ID,
    LocalModelService,
    ModelNotAdmitted,
)
from emotv.domain import LocalModelSettings
from emotv.infrastructure.persistence import InMemoryLocalModelSettingsRepository
from emotv.infrastructure.vision.emotion_classifier import ClassifierCache

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def service(states, settings=None):
    repository = InMemoryLocalModelSettingsRepository(settings)
    return LocalModelService(repository, lambda model_id: dict(model_id=model_id, state=states[model_id], reasons=[]),
                             clock=lambda: NOW), repository


def test_initial_default_is_hsemotion():
    models, _ = service({HSEMOTION_MODEL_ID: "SUPPORTED", FERPLUS_MODEL_ID: "SUPPORTED"})
    assert models.resolve().model_id == HSEMOTION_MODEL_ID


def test_set_default_records_who_and_when_and_clears_the_fallback():
    previous = LocalModelSettings(HSEMOTION_MODEL_ID, fallback_model_id=FERPLUS_MODEL_ID, fallback_at=NOW)
    models, repository = service({HSEMOTION_MODEL_ID: "SUPPORTED", FERPLUS_MODEL_ID: "WARNING"}, previous)
    saved = models.set_default(FERPLUS_MODEL_ID, "admin-1")
    assert (saved.default_model_id, saved.changed_by_user_id, saved.changed_at) == (FERPLUS_MODEL_ID, "admin-1", NOW)
    assert saved.fallback_model_id is None and repository.get() == saved


def test_set_default_requires_an_evaluated_admission():
    unevaluated = LocalModelService(InMemoryLocalModelSettingsRepository())
    with pytest.raises(ModelNotAdmitted):
        unevaluated.set_default(FERPLUS_MODEL_ID, "admin-1")


def test_fallback_is_recorded_only_when_the_backup_is_admitted():
    models, repository = service({HSEMOTION_MODEL_ID: "BLOCKED", FERPLUS_MODEL_ID: "BLOCKED"})
    choice = models.resolve()
    assert (choice.model_id, choice.admitted, choice.fallback) == (FERPLUS_MODEL_ID, False, True)
    assert repository.get() is None


def test_requested_model_is_returned_without_touching_the_settings():
    models, repository = service({HSEMOTION_MODEL_ID: "SUPPORTED", FERPLUS_MODEL_ID: "BLOCKED"})
    choice = models.resolve(FERPLUS_MODEL_ID)
    assert (choice.model_id, choice.admitted, choice.fallback) == (FERPLUS_MODEL_ID, False, False)
    assert repository.get() is None


def test_classifier_cache_loads_once_and_retries_after_a_failure():
    calls = []

    def load(model_id):
        calls.append(model_id)
        if len(calls) == 1:
            raise FileNotFoundError("pesos ausentes")
        return object()

    cache = ClassifierCache(load)
    with pytest.raises(FileNotFoundError):
        cache.get(FERPLUS_MODEL_ID)
    first = cache.get(FERPLUS_MODEL_ID)
    assert cache.get(FERPLUS_MODEL_ID) is first
    assert calls == [FERPLUS_MODEL_ID, FERPLUS_MODEL_ID]
