"""Sesión guiada en memoria: mismo contrato que PostgresGuidedSessionRepository,
para pruebas y para el proceso actual. Nada se cifra porque nada sale del proceso."""
from __future__ import annotations

from threading import RLock

from emotv.domain.guided_session import ExpressionCapture, GuidedRun, PracticeResult, SessionMarker, VerbalResponse


class InMemoryGuidedSessionRepository:
    def __init__(self) -> None:
        self._runs: dict[str, GuidedRun] = {}
        self._captures: dict[str, list[ExpressionCapture]] = {}
        self._markers: dict[str, list[SessionMarker]] = {}
        self._verbal: dict[tuple[str, int], VerbalResponse] = {}
        self._practice: dict[tuple[str, int], PracticeResult] = {}
        self._lock = RLock()

    # --- Estado -------------------------------------------------------------------

    def save_run(self, run: GuidedRun) -> GuidedRun:
        with self._lock:
            self._runs[run.session_id] = run
        return run

    def get_run(self, session_id: str) -> GuidedRun | None:
        with self._lock:
            return self._runs.get(session_id)

    def get_run_by_token_hash(self, token_hash: str) -> GuidedRun | None:
        with self._lock:
            return next((run for run in self._runs.values() if run.view_token_hash == token_hash), None)

    # --- Capturas y marcadores -------------------------------------------------------

    def add_capture(self, capture: ExpressionCapture) -> ExpressionCapture:
        with self._lock:
            self._captures.setdefault(capture.session_id, []).append(capture)
        return capture

    def list_captures(self, session_id: str) -> tuple[ExpressionCapture, ...]:
        with self._lock:
            return tuple(sorted(self._captures.get(session_id, ()), key=lambda item: (item.captured_at, item.id)))

    def add_marker(self, marker: SessionMarker) -> SessionMarker:
        with self._lock:
            self._markers.setdefault(marker.session_id, []).append(marker)
        return marker

    def list_markers(self, session_id: str) -> tuple[SessionMarker, ...]:
        with self._lock:
            return tuple(sorted(self._markers.get(session_id, ()), key=lambda item: (item.occurred_at, item.id)))

    # --- Respuestas verbales y resultados de las prácticas (uno por paso) ------------

    def save_verbal(self, response: VerbalResponse) -> VerbalResponse:
        with self._lock:
            self._verbal[(response.session_id, response.step_index)] = response
        return response

    def list_verbal(self, session_id: str) -> tuple[VerbalResponse, ...]:
        with self._lock:
            return tuple(sorted((item for (owner, _), item in self._verbal.items() if owner == session_id),
                                key=lambda item: item.step_index))

    def save_practice_result(self, result: PracticeResult) -> PracticeResult:
        with self._lock:
            self._practice[(result.session_id, result.step_index)] = result
        return result

    def list_practice_results(self, session_id: str) -> tuple[PracticeResult, ...]:
        with self._lock:
            return tuple(sorted((item for (owner, _), item in self._practice.items() if owner == session_id),
                                key=lambda item: item.step_index))
