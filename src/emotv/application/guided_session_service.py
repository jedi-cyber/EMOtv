"""Sesión guiada: confirmación, cuestionario previo, imágenes abstractas antes
del analizador, calibración neutral, estímulos del protocolo con capturas
controladas por calidad, y cuestionario posterior.

El servidor lleva el tiempo de cada exposición, así la vista de quien conduce y
la del participante pueden estar en dispositivos distintos. Los cuadros de la
cámara se analizan en memoria y se descartan; la base neutral también vive solo
en memoria. La vista del participante nunca recibe resultados.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any, Protocol as Interface
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.neutral_calibration import CALIBRATED, CALIBRATING, NeutralCalibration
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.guided_session import (
    ABSTRACT_CAPTURE_INTERVAL,
    QUALITY_RETRY_SECONDS,
    CaptureQuality,
    ExpressionCapture,
    FrameAssessment,
    GuidedPhase,
    GuidedRun,
    MarkerKind,
    QualityIssue,
    SessionMarker,
    StopReason,
    VerbalResponse,
)
from emotv.domain.participant import Participant, ParticipantKind
from emotv.domain.protocol import Protocol, ProtocolStep
from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState
from emotv.domain.stimulus import Stimulus, StimulusKind
from emotv.domain.user import User

RESOURCE = "guided_session"
CAPTURES = "expression_capture"
MARKER = "session_marker"
VERBAL = "verbal_response"
FRAME_INTERVAL_MS = 500

Assess = Callable[[Any], FrameAssessment]


class GuidedRepository(Interface):
    def save_run(self, run: GuidedRun) -> GuidedRun: ...
    def get_run(self, session_id: str) -> GuidedRun | None: ...
    def get_run_by_token_hash(self, token_hash: str) -> GuidedRun | None: ...
    def add_capture(self, capture: ExpressionCapture) -> ExpressionCapture: ...
    def list_captures(self, session_id: str) -> tuple[ExpressionCapture, ...]: ...
    def add_marker(self, marker: SessionMarker) -> SessionMarker: ...
    def list_markers(self, session_id: str) -> tuple[SessionMarker, ...]: ...
    def save_verbal(self, response: VerbalResponse) -> VerbalResponse: ...
    def list_verbal(self, session_id: str) -> tuple[VerbalResponse, ...]: ...


class GuidedNotFound(LookupError):
    pass


class GuidedConflict(Exception):
    """La acción no corresponde a la fase actual de la sesión."""


@dataclass(slots=True)
class _Live:
    """Estado en memoria de una sesión: calibración y último problema de calidad."""

    calibration: NeutralCalibration | None = None
    calibration_notice: str | None = None
    pending: FrameAssessment | None = None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GuidedSessionService:
    def __init__(
        self,
        repository: GuidedRepository,
        sessions,                                   # SessionService
        protocols: Callable[[str], Protocol | None],
        stimuli: Callable[[str], Stimulus | None],
        participants: Callable[[str], Participant | None],
        participant_ready: Callable[[Participant], bool],
        questionnaire_answered: Callable[[str, str], bool],
        resolve_model: Callable[[], tuple[str, str]],
        assess_factory: Callable[[str], Assess],
        audit: AuditService,
        session_access: Callable[[User, EmotionalSession], bool],
        calibration_seconds: float = 3.0,
        calibration_min_increase: float = 0.10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.sessions = sessions
        self.protocols = protocols
        self.stimuli = stimuli
        self.participants = participants
        self.participant_ready = participant_ready
        self.questionnaire_answered = questionnaire_answered
        self.resolve_model = resolve_model
        self.assess_factory = assess_factory
        self.audit = audit
        self.session_access = session_access
        self.calibration_seconds = calibration_seconds
        self.calibration_min_increase = calibration_min_increase
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._live: dict[str, _Live] = {}
        self._assessors: dict[str, Assess] = {}
        self._viewed: set[tuple[str, str]] = set()

    # --- Utilidades -----------------------------------------------------------------

    def _session(self, session_id: str) -> EmotionalSession:
        session = self.sessions.get_session(session_id)
        if session is None:
            raise GuidedNotFound(session_id)
        return session

    def _protocol(self, session: EmotionalSession) -> Protocol:
        protocol = self.protocols(session.protocol_id) if session.protocol_id else None
        if protocol is None:
            raise GuidedConflict("La sesión guiada sigue un protocolo")
        return protocol

    def _conducted(self, user: User, session_id: str) -> tuple[GuidedRun, EmotionalSession]:
        run = self.repository.get_run(session_id)
        if run is None:
            raise GuidedNotFound(session_id)
        if run.owner_user_id != user.id or not user.is_active:
            raise PermissionError("Solo quien conduce la sesión la controla")
        return run, self._session(session_id)

    def _live_of(self, session_id: str) -> _Live:
        return self._live.setdefault(session_id, _Live())

    def _seconds(self, start: datetime | None) -> float:
        return 0.0 if start is None else max(0.0, (self.clock() - start).total_seconds())

    @staticmethod
    def _group(protocol: Protocol, before: bool) -> list[int]:
        return [index for index, step in enumerate(protocol.steps) if step.shown_before_analyzer == before]

    def _first_due(self, step: ProtocolStep, phase: GuidedPhase) -> float | None:
        return float(step.capture_after_seconds) if phase is GuidedPhase.STIMULI else None

    def _start_step(self, run: GuidedRun, protocol: Protocol, phase: GuidedPhase, index: int) -> GuidedRun:
        step = protocol.steps[index]
        return replace(run, phase=phase, step_index=index, step_started_at=self.clock(),
                       next_capture_due=self._first_due(step, phase))

    def _log_step(self, run: GuidedRun, skipped: bool) -> GuidedRun:
        entry = {"step_index": run.step_index, "phase": run.phase.value,
                 "started_at": run.step_started_at.isoformat() if run.step_started_at else None,
                 "ended_at": self.clock().isoformat(), "skipped": skipped}
        return replace(run, steps_log=(*run.steps_log, entry))

    # --- Avance entre fases ----------------------------------------------------------

    def _after_pre(self, run: GuidedRun, protocol: Protocol) -> GuidedRun:
        before = self._group(protocol, True)
        if before:
            return self._start_step(run, protocol, GuidedPhase.BEFORE_ANALYZER, before[0])
        return replace(run, phase=GuidedPhase.CALIBRATION, step_started_at=None, next_capture_due=None)

    def _after_stimuli(self, run: GuidedRun, session: EmotionalSession) -> GuidedRun:
        if session.post_questionnaire_id:
            return replace(run, phase=GuidedPhase.POST_QUESTIONNAIRE, step_started_at=None, next_capture_due=None)
        return self._finish(run, session)

    def _finish(self, run: GuidedRun, session: EmotionalSession) -> GuidedRun:
        if session.state is SessionState.IN_PROGRESS:
            self.sessions.finish_guided(session.id)
        self._live.pop(session.id, None)
        return replace(run, phase=GuidedPhase.FINISHED, ended_at=self.clock(), step_started_at=None,
                       next_capture_due=None, view_token_hash=None)

    def _next_step(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol, skipped: bool) -> GuidedRun:
        run = self._log_step(run, skipped)
        group = self._group(protocol, run.phase is GuidedPhase.BEFORE_ANALYZER)
        later = [index for index in group if index > run.step_index]
        if later:
            return self._start_step(run, protocol, run.phase, later[0])
        if run.phase is GuidedPhase.BEFORE_ANALYZER:
            return replace(run, phase=GuidedPhase.CALIBRATION, step_started_at=None, next_capture_due=None)
        return self._after_stimuli(run, session)

    def _tick(self, run: GuidedRun) -> GuidedRun:
        """Avanza según el reloj del servidor: fin de exposición y capturas sin cuadros."""
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            return run
        session = self._session(run.session_id)
        protocol = self._protocol(session)
        changed = False
        while run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            step = protocol.steps[run.step_index]
            elapsed = self._seconds(run.step_started_at)
            # Una captura vencida sin cuadros (o sin uno válido) se guarda marcada.
            while (run.next_capture_due is not None
                   and (elapsed >= run.next_capture_due + QUALITY_RETRY_SECONDS or elapsed >= step.exposure_seconds)):
                run = self._store_capture(run, session, protocol, self._live_of(run.session_id).pending,
                                          min(elapsed, step.exposure_seconds), timed_out=True)
                changed = True
            if elapsed < step.exposure_seconds:
                break
            run = self._next_step(run, session, protocol, skipped=False)
            changed = True
        return self.repository.save_run(run) if changed else run

    # --- Capturas -----------------------------------------------------------------------

    def _store_capture(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol,
                       assessment: FrameAssessment | None, elapsed: float, timed_out: bool) -> GuidedRun:
        step = protocol.steps[run.step_index]
        live = self._live_of(run.session_id)
        if assessment is None:
            assessment = FrameAssessment((QualityIssue.NO_FRAME,))
        calibrated = None
        calibration = live.calibration
        if assessment.distribution and calibration is not None and calibration.state == CALIBRATED:
            _, calibrated = calibration.compare(assessment.distribution)
        good = assessment.ok and not timed_out
        self.repository.add_capture(ExpressionCapture(
            id=str(uuid4()), session_id=session.id, captured_at=self.clock(),
            emotion_model_id=session.emotion_model_id or "", emotion_model_version=session.emotion_model_version or "",
            quality=CaptureQuality.GOOD if good else CaptureQuality.FLAGGED,
            quality_issues=() if good else (assessment.issues or (QualityIssue.NO_FRAME,)),
            step_index=run.step_index, stimulus_id=step.stimulus_id, seconds_since_stimulus=round(elapsed, 2),
            emotion=assessment.emotion, confidence=assessment.confidence, distribution=assessment.distribution,
            calibrated_emotion=calibrated, participant_id=run.participant_id))
        live.pending = None
        stimulus = self.stimuli(step.stimulus_id)
        next_due = None
        if run.next_capture_due is not None and stimulus is not None and stimulus.kind is StimulusKind.ABSTRACT:
            candidate = run.next_capture_due + ABSTRACT_CAPTURE_INTERVAL
            next_due = candidate if candidate < step.exposure_seconds else None
        return replace(run, next_capture_due=next_due)

    def _assess(self, session: EmotionalSession, frame) -> FrameAssessment:
        model_id = session.emotion_model_id or ""
        if model_id not in self._assessors:
            self._assessors[model_id] = self.assess_factory(model_id)
        return self._assessors[model_id](frame)

    # --- Quien conduce la sesión -------------------------------------------------------

    def create(self, user: User, session_id: str) -> tuple[GuidedRun, str]:
        """Prepara la sesión guiada y entrega una sola vez el enlace de la vista del participante."""
        session = self._session(session_id)
        if session.owner_user_id != user.id:
            raise PermissionError("Solo quien conduce la sesión la prepara")
        self._protocol(session)
        if session.state is not SessionState.IN_PROGRESS:
            raise GuidedConflict("La sesión no está en progreso")
        if self.repository.get_run(session_id) is not None:
            raise GuidedConflict("La sesión guiada ya está preparada")
        token = secrets.token_urlsafe(32)
        run = self.repository.save_run(GuidedRun(
            session_id=session.id, owner_user_id=user.id, created_at=self.clock(),
            participant_id=session.participant_id, view_token_hash=hash_token(token)))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, session.id)
        return run, token

    def new_view_link(self, user: User, session_id: str) -> str:
        """Reemplaza el enlace de la vista del participante (el anterior deja de valer)."""
        run, _ = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        token = secrets.token_urlsafe(32)
        self.repository.save_run(replace(run, view_token_hash=hash_token(token)))
        return token

    def confirm(self, user: User, session_id: str, *, commitment_reminder: bool, authorization_confirmed: bool = False,
                guardian_present: bool = False, child_assent: bool = False) -> GuidedRun:
        """Sin la confirmación de quien conduce la sesión, no empieza."""
        run, session = self._conducted(user, session_id)
        if run.phase is not GuidedPhase.CONFIRMATION:
            raise GuidedConflict("La confirmación ya se registró")
        if not commitment_reminder:
            raise ValueError("Confirma que leíste el recordatorio del compromiso de confidencialidad")
        if session.participant_id is not None:
            participant = self.participants(session.participant_id)
            if participant is None or not self.participant_ready(participant):
                raise GuidedConflict("El participante ya no tiene sus autorizaciones vigentes")
            if participant.kind is ParticipantKind.CHILD:
                if not (guardian_present and child_assent):
                    raise ValueError("Confirma que el padre, la madre o el tutor está presente y que el niño o la "
                                     "niña dio su asentimiento")
            elif not authorization_confirmed:
                raise ValueError("Confirma que el participante dio su autorización")
        model_id, version = self.resolve_model()
        session = self.sessions.record_emotion_model(session.id, model_id, version)
        protocol = self._protocol(session)
        run = replace(run, confirmed_at=self.clock())
        run = (replace(run, phase=GuidedPhase.PRE_QUESTIONNAIRE) if session.pre_questionnaire_id
               else self._after_pre(run, protocol))
        self.audit.record(user, AuditAction.APPROVE, RESOURCE, session.id)
        return self.repository.save_run(run)

    def advance(self, user: User, session_id: str) -> GuidedRun:
        """Continúa tras un cuestionario: el previo debe estar respondido."""
        run, session = self._conducted(user, session_id)
        if run.phase is GuidedPhase.PRE_QUESTIONNAIRE:
            if not self.questionnaire_answered(session.id, "pre"):
                raise GuidedConflict("Falta responder el cuestionario previo")
            return self.repository.save_run(self._after_pre(run, self._protocol(session)))
        if run.phase is GuidedPhase.POST_QUESTIONNAIRE:
            if not self.questionnaire_answered(session.id, "post"):
                raise GuidedConflict("Falta responder el cuestionario posterior")
            return self.repository.save_run(self._finish(run, session))
        raise GuidedConflict("No hay nada que continuar en esta fase")

    def start_calibration(self, user: User, session_id: str) -> GuidedRun:
        run, _ = self._conducted(user, session_id)
        if run.phase is not GuidedPhase.CALIBRATION:
            raise GuidedConflict("La calibración va después del cuestionario previo")
        live = self._live_of(session_id)
        live.calibration = NeutralCalibration(seconds=self.calibration_seconds,
                                              min_increase=self.calibration_min_increase,
                                              clock=lambda: self.clock().timestamp())
        live.calibration.start()
        live.calibration_notice = None
        return run

    def skip(self, user: User, session_id: str) -> GuidedRun:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            raise GuidedConflict("No hay un estímulo en curso")
        self._live_of(session_id).pending = None
        return self.repository.save_run(self._next_step(replace(run, next_capture_due=None), session,
                                                        self._protocol(session), skipped=True))

    def _stop(self, run: GuidedRun, reason: StopReason, actor: User | None) -> GuidedRun:
        if not run.active:
            return run
        session = self._session(run.session_id)
        if session.state in (SessionState.CREATED, SessionState.IN_PROGRESS, SessionState.RECOGNIZED):
            self.sessions.cancel_session(session.id)
        if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            run = self._log_step(run, skipped=True)
        self._live.pop(run.session_id, None)
        stopped = self.repository.save_run(replace(
            run, phase=GuidedPhase.STOPPED, stop_reason=reason, ended_at=self.clock(), step_started_at=None,
            next_capture_due=None, view_token_hash=None))
        self.audit.record(actor, AuditAction.UPDATE, RESOURCE, run.session_id)
        return stopped

    def stop(self, user: User, session_id: str, reason: StopReason | str) -> GuidedRun:
        """El participante o su tutor pidieron parar, o quien conduce terminó: termina de inmediato."""
        run, _ = self._conducted(user, session_id)
        return self._stop(run, StopReason(reason), user)

    def add_marker(self, user: User, session_id: str, kind: MarkerKind | str, note: str | None = None) -> SessionMarker:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if not run.active and run.phase is not GuidedPhase.STOPPED:
            raise GuidedConflict("La sesión ya terminó")
        kind = MarkerKind(kind)
        in_step = run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI)
        marker = self.repository.add_marker(SessionMarker(
            id=str(uuid4()), session_id=session.id, kind=kind, occurred_at=self.clock(),
            recorded_by_user_id=user.id, step_index=run.step_index if in_step else None,
            note=note if kind is MarkerKind.NOTE else None, participant_id=run.participant_id))
        self.audit.record(user, AuditAction.CREATE, MARKER, marker.id)
        if kind is MarkerKind.ASKED_TO_STOP:
            # Si el participante pide parar, la sesión termina de inmediato.
            self._stop(run, StopReason.PARTICIPANT, user)
        return marker

    def record_verbal(self, user: User, session_id: str, step_index: int, text: str) -> VerbalResponse:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        protocol = self._protocol(session)
        if not 0 <= step_index < len(protocol.steps) or not protocol.steps[step_index].record_verbal_response:
            raise ValueError("Ese estímulo no registra lo que el participante dice ver")
        shown = {item["step_index"] for item in run.steps_log} | (
            {run.step_index} if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI) else set())
        if step_index not in shown:
            raise GuidedConflict("Ese estímulo todavía no se mostró")
        response = self.repository.save_verbal(VerbalResponse(
            id=str(uuid4()), session_id=session.id, step_index=step_index,
            stimulus_id=protocol.steps[step_index].stimulus_id, text=text, recorded_at=self.clock(),
            recorded_by_user_id=user.id, participant_id=run.participant_id))
        self.audit.record(user, AuditAction.CREATE, VERBAL, response.id)
        return response

    def conductor_state(self, user: User, session_id: str) -> dict[str, Any]:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if (user.id, session_id) not in self._viewed:
            self._viewed.add((user.id, session_id))
            self.audit.record(user, AuditAction.VIEW, RESOURCE, session_id)
        return self._summary(run, session, include_results=True)

    def results(self, user: User, session_id: str) -> dict[str, Any]:
        """Capturas, marcadores y respuestas: quien condujo y su docente; se audita."""
        session = self._session(session_id)
        run = self.repository.get_run(session_id)
        if run is None:
            raise GuidedNotFound(session_id)
        if not self.session_access(user, session):
            self.audit.record(user, AuditAction.VIEW, CAPTURES, session_id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta sesión")
        self.audit.record(user, AuditAction.VIEW, CAPTURES, session_id)
        return self._summary(run, session, include_results=True)

    def _summary(self, run: GuidedRun, session: EmotionalSession, include_results: bool) -> dict[str, Any]:
        protocol = self._protocol(session)
        stimuli = {step.stimulus_id: self.stimuli(step.stimulus_id) for step in protocol.steps}
        live = self._live.get(session.id)
        calibration = live.calibration if live else None
        step = protocol.steps[run.step_index] if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI) else None
        participant = self.participants(session.participant_id) if session.participant_id else None
        summary: dict[str, Any] = {
            "session_id": session.id,
            "phase": run.phase.value,
            "participant_kind": participant.kind.value if participant else None,
            "stop_reason": run.stop_reason.value if run.stop_reason else None,
            "step_index": run.step_index if step else None,
            "step_count": len(protocol.steps),
            "steps": [{"index": index, "stimulus_id": item.stimulus_id,
                       "title": stimuli[item.stimulus_id].title if stimuli[item.stimulus_id] else "",
                       "kind": stimuli[item.stimulus_id].kind.value if stimuli[item.stimulus_id] else "",
                       "exposure_seconds": item.exposure_seconds, "capture_after_seconds": item.capture_after_seconds,
                       "record_verbal_response": item.record_verbal_response,
                       "shown_before_analyzer": item.shown_before_analyzer} for index, item in enumerate(protocol.steps)],
            "remaining_seconds": (max(0.0, step.exposure_seconds - self._seconds(run.step_started_at))
                                  if step else None),
            "steps_log": list(run.steps_log),
            "calibration": {"state": calibration.state if calibration else ("calibrated" if run.calibrated_at else "none"),
                            "progress": round(calibration.progress, 2) if calibration else (1.0 if run.calibrated_at else 0.0),
                            "notice": live.calibration_notice if live else None},
            "capture_status": ([item.value for item in live.pending.issues] if live and live.pending else []),
            "pre_questionnaire_id": session.pre_questionnaire_id,
            "post_questionnaire_id": session.post_questionnaire_id,
            "has_abstract": any(item and item.kind is StimulusKind.ABSTRACT for item in stimuli.values()),
        }
        if include_results:
            summary["captures"] = [{
                "id": item.id, "captured_at": item.captured_at.isoformat(), "step_index": item.step_index,
                "stimulus_id": item.stimulus_id, "seconds_since_stimulus": item.seconds_since_stimulus,
                "emotion": item.emotion, "confidence": item.confidence, "calibrated_emotion": item.calibrated_emotion,
                "quality": item.quality.value, "quality_issues": [issue.value for issue in item.quality_issues],
                "emotion_model_id": item.emotion_model_id,
            } for item in self.repository.list_captures(session.id)]
            summary["markers"] = [{
                "id": item.id, "kind": item.kind.value, "occurred_at": item.occurred_at.isoformat(),
                "step_index": item.step_index, "note": item.note,
            } for item in self.repository.list_markers(session.id)]
            summary["verbal_responses"] = [{
                "step_index": item.step_index, "stimulus_id": item.stimulus_id, "text": item.text,
                "recorded_at": item.recorded_at.isoformat(),
            } for item in self.repository.list_verbal(session.id)]
        return summary

    # --- Vista del participante (enlace propio, sin cuenta) ---------------------------

    def _by_token(self, token: str) -> GuidedRun:
        run = self.repository.get_run_by_token_hash(hash_token(token)) if token else None
        if run is None or not run.active:
            raise GuidedNotFound("view")
        return run

    def participant_state(self, token: str) -> dict[str, Any]:
        """Solo lo que se muestra al participante: nunca expresiones, probabilidades,
        calidad ni notas."""
        run = self._tick(self._by_token(token))
        if not run.active:
            return {"phase": run.phase.value, "message": "La sesión terminó. Gracias.", "stimulus": None,
                    "remaining_seconds": None, "capture_frames": False, "frame_interval_ms": FRAME_INTERVAL_MS,
                    "abstract_notice": False}
        session = self._session(run.session_id)
        protocol = self._protocol(session)
        stimulus = None
        remaining = None
        abstract = False
        if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            step = protocol.steps[run.step_index]
            item = self.stimuli(step.stimulus_id)
            # Un identificador de exposición, no el del estímulo, para pedir la imagen.
            stimulus = {"exposure": f"{run.step_index}-{int(run.step_started_at.timestamp()) if run.step_started_at else 0}"}
            remaining = max(0.0, step.exposure_seconds - self._seconds(run.step_started_at))
            abstract = item is not None and item.kind is StimulusKind.ABSTRACT
        live = self._live.get(run.session_id)
        calibrating = run.phase is GuidedPhase.CALIBRATION and live is not None and live.calibration is not None \
            and live.calibration.state == CALIBRATING
        messages = {
            GuidedPhase.CONFIRMATION: "La sesión empezará en un momento.",
            GuidedPhase.PRE_QUESTIONNAIRE: "Primero, unas preguntas.",
            GuidedPhase.CALIBRATION: ("Mira a la pantalla con el rostro relajado." if calibrating
                                      else "En un momento empieza la calibración."),
            GuidedPhase.POST_QUESTIONNAIRE: "Para terminar, unas preguntas.",
        }
        return {
            "phase": run.phase.value,
            "message": messages.get(run.phase),
            "stimulus": stimulus,
            "remaining_seconds": remaining,
            "capture_frames": calibrating or run.phase is GuidedPhase.STIMULI,
            "frame_interval_ms": FRAME_INTERVAL_MS,
            "abstract_notice": abstract,
        }

    def participant_stimulus(self, token: str) -> str:
        """El estímulo que se está mostrando ahora (y solo ese)."""
        run = self._tick(self._by_token(token))
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            raise GuidedNotFound("stimulus")
        session = self._session(run.session_id)
        return self._protocol(session).steps[run.step_index].stimulus_id

    def participant_stop(self, token: str) -> None:
        """El botón visible de la vista del participante: termina de inmediato."""
        self._stop(self._by_token(token), StopReason.PARTICIPANT, None)

    def receive_frame(self, token: str, frame) -> None:
        """Analiza un cuadro en memoria (calibración o captura) y lo descarta."""
        run = self._tick(self._by_token(token))
        if frame is None:
            return
        session = self._session(run.session_id)
        live = self._live_of(run.session_id)
        if run.phase is GuidedPhase.CALIBRATION:
            calibration = live.calibration
            if calibration is None or calibration.state != CALIBRATING:
                return
            assessment = self._assess(session, frame)
            notice = calibration.add(assessment.distribution if assessment.emotion is not None else None)
            if notice:
                live.calibration_notice = notice
            elif calibration.state == CALIBRATED:
                protocol = self._protocol(session)
                during = self._group(protocol, False)
                run = replace(run, calibrated_at=self.clock())
                run = (self._start_step(run, protocol, GuidedPhase.STIMULI, during[0]) if during
                       else self._after_stimuli(run, session))
                self.repository.save_run(run)
            return
        if run.phase is not GuidedPhase.STIMULI or run.next_capture_due is None:
            return
        elapsed = self._seconds(run.step_started_at)
        if elapsed < run.next_capture_due:
            return
        assessment = self._assess(session, frame)
        if assessment.ok:
            self.repository.save_run(self._store_capture(run, session, self._protocol(session), assessment,
                                                         elapsed, timed_out=False))
        elif elapsed >= run.next_capture_due + QUALITY_RETRY_SECONDS:
            # No se logró una captura de buena calidad: se guarda marcada con su problema.
            self.repository.save_run(self._store_capture(run, session, self._protocol(session), assessment,
                                                         elapsed, timed_out=True))
        else:
            live.pending = assessment  # se reintenta con el próximo cuadro
