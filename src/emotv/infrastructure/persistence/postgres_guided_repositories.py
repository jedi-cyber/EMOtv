"""Persistencia de la sesión guiada: estado, capturas, marcadores (nota
cifrada) y lo que el participante dice ver (cifrado)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.guided_session import ExpressionCapture, GuidedRun, SessionMarker, VerbalResponse
from emotv.infrastructure.persistence.models import (
    ExpressionCaptureRecord,
    GuidedRunRecord,
    SessionMarkerRecord,
    VerbalResponseRecord,
)
from emotv.shared.security.field_encryption import FieldCipher


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class PostgresGuidedSessionRepository:
    def __init__(self, factory: sessionmaker[Session], cipher: FieldCipher) -> None:
        self._factory = factory
        self._cipher = cipher

    # --- Estado -------------------------------------------------------------------

    @staticmethod
    def _run(row: GuidedRunRecord) -> GuidedRun:
        return GuidedRun(
            session_id=row.session_id, owner_user_id=row.owner_user_id, created_at=_aware(row.created_at),
            phase=row.phase, participant_id=row.participant_id, confirmed_at=_aware(row.confirmed_at),
            step_index=row.step_index, step_started_at=_aware(row.step_started_at),
            next_capture_due=row.next_capture_due, steps_log=tuple(row.steps_log or ()),
            calibrated_at=_aware(row.calibrated_at), view_token_hash=row.view_token_hash,
            ended_at=_aware(row.ended_at), stop_reason=row.stop_reason)

    def save_run(self, run: GuidedRun) -> GuidedRun:
        with self._factory.begin() as db:
            row = db.get(GuidedRunRecord, run.session_id)
            if row is None:
                row = GuidedRunRecord(session_id=run.session_id)
                db.add(row)
            row.participant_id = run.participant_id
            row.owner_user_id = run.owner_user_id
            row.phase = run.phase.value
            row.created_at = run.created_at
            row.confirmed_at = run.confirmed_at
            row.step_index = run.step_index
            row.step_started_at = run.step_started_at
            row.next_capture_due = run.next_capture_due
            row.steps_log = [dict(item) for item in run.steps_log]
            row.calibrated_at = run.calibrated_at
            row.view_token_hash = run.view_token_hash
            row.ended_at = run.ended_at
            row.stop_reason = run.stop_reason.value if run.stop_reason else None
        return run

    def get_run(self, session_id: str) -> GuidedRun | None:
        with self._factory() as db:
            row = db.get(GuidedRunRecord, session_id)
            return None if row is None else self._run(row)

    def get_run_by_token_hash(self, token_hash: str) -> GuidedRun | None:
        with self._factory() as db:
            row = db.scalars(select(GuidedRunRecord).where(GuidedRunRecord.view_token_hash == token_hash)).first()
            return None if row is None else self._run(row)

    # --- Capturas -----------------------------------------------------------------

    def add_capture(self, capture: ExpressionCapture) -> ExpressionCapture:
        with self._factory.begin() as db:
            db.add(ExpressionCaptureRecord(
                id=capture.id, session_id=capture.session_id, participant_id=capture.participant_id,
                captured_at=capture.captured_at, emotion_model_id=capture.emotion_model_id,
                emotion_model_version=capture.emotion_model_version, emotion=capture.emotion,
                confidence=capture.confidence, distribution=capture.distribution,
                calibrated_emotion=capture.calibrated_emotion, quality=capture.quality.value,
                quality_issues=[item.value for item in capture.quality_issues], step_index=capture.step_index,
                stimulus_id=capture.stimulus_id, seconds_since_stimulus=capture.seconds_since_stimulus))
        return capture

    def list_captures(self, session_id: str) -> tuple[ExpressionCapture, ...]:
        with self._factory() as db:
            rows = db.scalars(select(ExpressionCaptureRecord).where(ExpressionCaptureRecord.session_id == session_id)
                              .order_by(ExpressionCaptureRecord.captured_at, ExpressionCaptureRecord.id)).all()
            return tuple(ExpressionCapture(
                id=row.id, session_id=row.session_id, captured_at=_aware(row.captured_at),
                emotion_model_id=row.emotion_model_id, emotion_model_version=row.emotion_model_version,
                quality=row.quality, quality_issues=tuple(row.quality_issues or ()), step_index=row.step_index,
                stimulus_id=row.stimulus_id, seconds_since_stimulus=row.seconds_since_stimulus, emotion=row.emotion,
                confidence=row.confidence, distribution=row.distribution, calibrated_emotion=row.calibrated_emotion,
                participant_id=row.participant_id) for row in rows)

    # --- Marcadores y respuestas verbales (cifradas) ---------------------------------

    def add_marker(self, marker: SessionMarker) -> SessionMarker:
        with self._factory.begin() as db:
            db.add(SessionMarkerRecord(
                id=marker.id, session_id=marker.session_id, participant_id=marker.participant_id,
                kind=marker.kind.value, note_encrypted=self._cipher.encrypt(marker.note),
                occurred_at=marker.occurred_at, step_index=marker.step_index,
                recorded_by_user_id=marker.recorded_by_user_id))
        return marker

    def list_markers(self, session_id: str) -> tuple[SessionMarker, ...]:
        with self._factory() as db:
            rows = db.scalars(select(SessionMarkerRecord).where(SessionMarkerRecord.session_id == session_id)
                              .order_by(SessionMarkerRecord.occurred_at, SessionMarkerRecord.id)).all()
            return tuple(SessionMarker(
                id=row.id, session_id=row.session_id, kind=row.kind, occurred_at=_aware(row.occurred_at),
                recorded_by_user_id=row.recorded_by_user_id, step_index=row.step_index,
                note=self._cipher.decrypt(row.note_encrypted), participant_id=row.participant_id) for row in rows)

    def save_verbal(self, response: VerbalResponse) -> VerbalResponse:
        """Una por paso: registrar de nuevo reemplaza el texto."""
        with self._factory.begin() as db:
            row = db.scalars(select(VerbalResponseRecord).where(
                VerbalResponseRecord.session_id == response.session_id,
                VerbalResponseRecord.step_index == response.step_index)).first()
            if row is None:
                row = VerbalResponseRecord(id=response.id, session_id=response.session_id,
                                           step_index=response.step_index)
                db.add(row)
            row.participant_id = response.participant_id
            row.stimulus_id = response.stimulus_id
            row.text_encrypted = self._cipher.encrypt(response.text)
            row.recorded_at = response.recorded_at
            row.recorded_by_user_id = response.recorded_by_user_id
        return response

    def list_verbal(self, session_id: str) -> tuple[VerbalResponse, ...]:
        with self._factory() as db:
            rows = db.scalars(select(VerbalResponseRecord).where(VerbalResponseRecord.session_id == session_id)
                              .order_by(VerbalResponseRecord.step_index)).all()
            return tuple(VerbalResponse(
                id=row.id, session_id=row.session_id, step_index=row.step_index, stimulus_id=row.stimulus_id,
                text=self._cipher.decrypt(row.text_encrypted), recorded_at=_aware(row.recorded_at),
                recorded_by_user_id=row.recorded_by_user_id, participant_id=row.participant_id) for row in rows)
