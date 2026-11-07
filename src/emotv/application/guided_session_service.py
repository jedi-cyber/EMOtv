"""Sesión que ejecuta un protocolo: cuestionario previo, imágenes abstractas
antes del analizador, calibración neutral, estímulos con capturas controladas
por calidad, y cuestionario posterior. En el aplicativo móvil, una sesión sin
protocolo hace la calibración y después la fase live: una captura cada pocos
segundos hasta que quien conduce la termina.

La autorización se confirma una sola vez, al iniciar la sesión (POST /sessions);
aquí no se vuelve a pedir. El servidor lleva el tiempo de cada exposición, así
la vista de quien conduce y la pantalla de la persona pueden estar en
dispositivos distintos. Los cuadros de la cámara se analizan en memoria y se
descartan; la base neutral también vive solo en memoria. La pantalla de la
persona nunca recibe resultados.

La estación de un examen simulado usa la misma pantalla de la persona: espera
el consentimiento sin analizar nada, se calibra sola cuando el docente lo
confirma, espera el inicio y guarda una fila cada medio segundo, contada desde
que el docente inició el examen. Al terminar el examen muestra el debriefing.
Quien conduce no ve sus capturas mientras la estación sigue activa.

Un paso de reconocimiento muestra una imagen emocional y pregunta «¿Qué emoción
es?». La persona toca una opción en su pantalla (o quien conduce registra lo que
señaló); después lee unos segundos el nombre de la emoción de la imagen y el
paso avanza solo. Ese paso no analiza la cámara.

Un paso de dibujo pide dibujar una cara y después «¿Qué emoción quisiste
dibujar?». El dibujo vive solo en la pantalla de la persona: aquí llega la
emoción que señaló (o la que registra quien conduce), nunca el dibujo. No hay
respuesta correcta y no analiza la cámara.

Un juego de emparejar tiene varias rondas: en cada una, la persona relaciona una
imagen con el nombre de su emoción. Puede pedir ayuda (se quita una opción y se
lee la pregunta). Si elige otra emoción, se le invita a mirar otra vez; tras dos,
se le muestra cuál es con su explicación y el juego sigue. Pasa de ronda con
«Siguiente». Sin puntaje: solo se guardan contadores (GameResult).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import math
import random
import secrets
import threading
from typing import Any, Protocol as Interface
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.neutral_calibration import CALIBRATED, CALIBRATING, NOT_CALIBRATED, NeutralCalibration
from emotv.application.practice_tracker import PracticeTracker
from emotv.config import PracticeSettings
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.exam import Exam, ExamState
from emotv.domain.guided_session import (
    ABSTRACT_CAPTURE_INTERVAL,
    EXAM_CAPTURE_INTERVAL,
    EXAM_DEBRIEFING,
    EXAM_GAP_SECONDS,
    EXAM_STATION_PHASES,
    PRACTICE_ACHIEVED_MESSAGE,
    IMITATION_INSTRUCTION,
    PRACTICE_INSTRUCTIONS,
    QUALITY_RETRY_SECONDS,
    RECOGNITION_ANSWERS,
    RECOGNITION_DISTRACTORS,
    RECOGNITION_NAMES,
    RECOGNITION_QUESTION,
    SITUATION_ANSWERS,
    SITUATION_NOTE,
    SITUATION_QUESTION,
    CAMERA_PROBLEMS,
    DRAWING_ANSWERS,
    DRAWING_INSTRUCTION,
    DRAWING_OPTIONS,
    DRAWING_QUESTION,
    GAME_FINISHED,
    GAME_FOUND,
    GAME_MISSES_BEFORE_ANSWER,
    GAME_QUESTION,
    GAME_RETRY,
    GAME_SHOWN,
    GAME_TIME_UP,
    MAX_STEP_ATTEMPTS,
    NO_CAMERA_SKIP,
    CaptureQuality,
    DrawingResult,
    ExpressionCapture,
    FrameAssessment,
    GameOutcome,
    GameResult,
    GuidedPhase,
    GuidedRun,
    MarkerKind,
    PracticeOutcome,
    PracticeResult,
    QualityIssue,
    RecognitionAnswerer,
    RecognitionOutcome,
    RecognitionResult,
    SessionMarker,
    StopReason,
    VerbalResponse,
)
from emotv.domain.protocol import (ACCESSIBLE_PAUSE_FACTOR, NO_TIME_LIMIT_SECONDS, WAIT_PAUSE_SECONDS, PauseMode,
                                   Protocol, ProtocolStep)
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
    # Uno por paso de práctica: guardar de nuevo el mismo paso lo reemplaza.
    def save_practice_result(self, result: PracticeResult) -> PracticeResult: ...
    def list_practice_results(self, session_id: str) -> tuple[PracticeResult, ...]: ...
    def list_practice_attempts(self, session_id: str) -> tuple[PracticeResult, ...]: ...
    # Uno por paso de reconocimiento: guardar de nuevo el mismo paso lo reemplaza.
    def save_recognition_result(self, result: RecognitionResult) -> RecognitionResult: ...
    def list_recognition_results(self, session_id: str) -> tuple[RecognitionResult, ...]: ...
    def list_recognition_attempts(self, session_id: str) -> tuple[RecognitionResult, ...]: ...
    # Uno por paso de dibujo e intento: solo la emoción señalada y los tiempos.
    def save_drawing_result(self, result: DrawingResult) -> DrawingResult: ...
    def list_drawing_results(self, session_id: str) -> tuple[DrawingResult, ...]: ...
    def list_drawing_attempts(self, session_id: str) -> tuple[DrawingResult, ...]: ...
    # Uno por juego e intento: solo contadores.
    def save_game_result(self, result: GameResult) -> GameResult: ...
    def list_game_results(self, session_id: str) -> tuple[GameResult, ...]: ...
    def list_game_attempts(self, session_id: str) -> tuple[GameResult, ...]: ...


class GuidedNotFound(LookupError):
    pass


class GuidedConflict(Exception):
    """La acción no corresponde a la fase actual de la sesión."""


@dataclass(slots=True)
class _Live:
    """Estado en memoria de una sesión: calibración, último problema de calidad
    y el ejercicio de práctica en curso (de tamaño fijo)."""

    calibration: NeutralCalibration | None = None
    calibration_notice: str | None = None
    pending: FrameAssessment | None = None
    practice: PracticeTracker | None = None
    analyzing: bool = False   # un cuadro de práctica se está analizando
    camera_problem: str | None = None  # motivo que informó la pantalla de la persona


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GuidedSessionService:
    def __init__(
        self,
        repository: GuidedRepository,
        sessions,                                   # SessionService
        protocols: Callable[[str], Protocol | None],
        stimuli: Callable[[str], Stimulus | None],
        questionnaire_answered: Callable[[str, str], bool],
        resolve_model: Callable[[], tuple[str, str]],
        assess_factory: Callable[[str], Assess],
        audit: AuditService,
        session_access: Callable[[User, EmotionalSession], bool],
        calibration_seconds: float = 3.0,
        calibration_min_increase: float = 0.10,
        clock: Callable[[], datetime] | None = None,
        exam_of: Callable[[str], Exam | None] | None = None,
        practice: PracticeSettings | None = None,
        explanation_of: Callable[[str], str | None] | None = None,
    ) -> None:
        self.repository = repository
        self.sessions = sessions
        self.protocols = protocols
        self.stimuli = stimuli
        self.questionnaire_answered = questionnaire_answered
        self.resolve_model = resolve_model
        self.assess_factory = assess_factory
        self.audit = audit
        self.session_access = session_access
        self.calibration_seconds = calibration_seconds
        self.calibration_min_increase = calibration_min_increase
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        # Examen simulado de una estación; sin él no hay estaciones.
        self.exam_of = exam_of
        self.practice = practice or PracticeSettings()
        # Explicación sencilla y revisable de cada emoción (catálogo de expresiones).
        self.explanation_of = explanation_of
        self._live: dict[str, _Live] = {}
        # Protege el nivel de la práctica: los cuadros llegan en hilos distintos.
        self._practice_lock = threading.Lock()
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
            raise GuidedConflict("Esta acción corresponde a una sesión con protocolo")
        return protocol

    def _step_pause(self, protocol: Protocol) -> float:
        """Pausa tras un ejercicio o un reconocimiento según el apoyo del protocolo:
        la normal, el doble o hasta que quien conduce pulse «Seguir» (con tope)."""
        pause = protocol.supports.pause
        if pause is PauseMode.WAIT:
            return float(WAIT_PAUSE_SECONDS)
        factor = ACCESSIBLE_PAUSE_FACTOR if pause is PauseMode.LONG else 1
        return self.practice.step_pause_seconds * factor

    @staticmethod
    def _limit(protocol: Protocol, step: ProtocolStep) -> float:
        """Segundos máximos del paso. Sin límite de tiempo, un reconocimiento o un
        ejercicio solo termina al responder, al lograrlo o al saltarlo (con tope)."""
        timed = step.is_timed
        return float(NO_TIME_LIMIT_SECONDS) if timed and protocol.supports.no_time_limit else step.seconds_limit

    def _unlimited(self, session: EmotionalSession, step: ProtocolStep | None) -> bool:
        return (step is not None and step.is_timed and session.protocol_id is not None
                and self._protocol(session).supports.no_time_limit)

    def _uses_camera(self, session: EmotionalSession) -> bool:
        """Sin protocolo (registro en vivo) siempre; con protocolo, según sus pasos."""
        return session.protocol_id is None or self._protocol(session).uses_camera

    def _camera_active(self, run: GuidedRun, session: EmotionalSession) -> bool:
        """Si la sesión usa la cámara desde ahora: no si quien conduce siguió sin ella."""
        return run.camera_off_at is None and self._uses_camera(session)

    def _steps(self, session: EmotionalSession) -> tuple[ProtocolStep, ...]:
        """Los pasos del protocolo; ninguno en una sesión sin protocolo."""
        return self._protocol(session).steps if session.protocol_id else ()

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
        # En una práctica o un reconocimiento, next_capture_due solo marca cuándo
        # avanzar tras lograrla o responder.
        timed = step.is_timed
        return float(step.capture_after_seconds) if phase is GuidedPhase.STIMULI and not timed else None

    def _start_step(self, run: GuidedRun, protocol: Protocol, phase: GuidedPhase, index: int) -> GuidedRun:
        step = protocol.steps[index]
        return replace(run, phase=phase, step_index=index, step_started_at=self.clock(),
                       next_capture_due=self._first_due(step, phase), step_attempt=1, game_progress=None)

    def _log_step(self, run: GuidedRun, skipped: bool, reason: str | None = None) -> GuidedRun:
        # Un paso repetido se registra desde su primer intento.
        started = min((item.started_at for item in self._step_attempts(run.session_id, run.step_index)),
                      default=run.step_started_at)
        if run.step_started_at is not None and started is not None:
            started = min(started, run.step_started_at)
        entry = {"step_index": run.step_index, "phase": run.phase.value,
                 "started_at": started.isoformat() if started else None,
                 "ended_at": self.clock().isoformat(), "skipped": skipped}
        if reason:
            entry["reason"] = reason
        return replace(run, steps_log=(*run.steps_log, entry))

    def _start_during(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol,
                      candidates: list[int]) -> GuidedRun:
        """Empieza el primero de los pasos indicados. Sin cámara, los que la
        necesitan se registran como saltados (motivo no_camera) sin empezar."""
        for index in candidates:
            if run.camera_off_at is not None and protocol.steps[index].uses_camera:
                now = self.clock().isoformat()
                run = replace(run, steps_log=(*run.steps_log, {
                    "step_index": index, "phase": GuidedPhase.STIMULI.value, "started_at": now, "ended_at": now,
                    "skipped": True, "reason": NO_CAMERA_SKIP}))
                continue
            return self._start_step(run, protocol, GuidedPhase.STIMULI, index)
        return self._after_stimuli(run, session)

    # --- Avance entre fases ----------------------------------------------------------

    def _after_pre(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol) -> GuidedRun:
        before = self._group(protocol, True)
        if before:
            return self._start_step(run, protocol, GuidedPhase.BEFORE_ANALYZER, before[0])
        return self._to_analyzer(run, session, protocol)

    def _to_analyzer(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol) -> GuidedRun:
        """Con cámara, la calibración neutral; sin cámara (solo reconocimientos),
        la sesión queda lista (ready) hasta que quien conduce pulsa «Empezar»: no
        se calibra ni se envían cuadros, y el tiempo del primer paso no corre antes."""
        if self._camera_active(run, session):
            return replace(run, phase=GuidedPhase.CALIBRATION, step_started_at=None, next_capture_due=None)
        return replace(run, phase=GuidedPhase.READY, step_started_at=None, next_capture_due=None)

    def _first_step(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol) -> GuidedRun:
        return self._start_during(run, session, protocol, self._group(protocol, False))

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

    # --- Estación de examen ----------------------------------------------------------

    def _exam(self, session: EmotionalSession) -> Exam | None:
        return self.exam_of(session.exam_id) if session.exam_id and self.exam_of else None

    @staticmethod
    def _next_slot(elapsed: float) -> float:
        """El siguiente medio segundo del examen, estrictamente después de elapsed."""
        return (math.floor(round(elapsed / EXAM_CAPTURE_INTERVAL, 6)) + 1) * EXAM_CAPTURE_INTERVAL

    def _begin_calibration(self, session_id: str, keep_notice: bool = False) -> None:
        live = self._live_of(session_id)
        live.calibration = NeutralCalibration(seconds=self.calibration_seconds,
                                              min_increase=self.calibration_min_increase,
                                              clock=lambda: self.clock().timestamp())
        live.calibration.start()
        if not keep_notice:
            live.calibration_notice = None

    def _store_exam_capture(self, run: GuidedRun, session: EmotionalSession,
                            assessment: FrameAssessment | None, second: float) -> None:
        """Una fila del examen: segundo contado desde el inicio, expresión y confianza."""
        if assessment is None:
            assessment = FrameAssessment((QualityIssue.NO_FRAME,))
        calibration = self._live_of(run.session_id).calibration
        calibrated = None
        if assessment.distribution and calibration is not None and calibration.state == CALIBRATED:
            _, calibrated = calibration.compare(assessment.distribution)
        self.repository.add_capture(ExpressionCapture(
            id=str(uuid4()), session_id=session.id, captured_at=run.step_started_at + timedelta(seconds=second),
            emotion_model_id=session.emotion_model_id or "", emotion_model_version=session.emotion_model_version or "",
            quality=CaptureQuality.GOOD if assessment.ok else CaptureQuality.FLAGGED,
            quality_issues=assessment.issues, step_index=0, stimulus_id=None, seconds_since_stimulus=round(second, 2),
            emotion=assessment.emotion, confidence=assessment.confidence, distribution=assessment.distribution,
            calibrated_emotion=calibrated))

    def _fill_exam_gaps(self, run: GuidedRun, session: EmotionalSession, elapsed: float) -> GuidedRun:
        """Los medios segundos sin cuadros se guardan marcados: así se ven los tramos sin registro."""
        due = run.next_capture_due
        while due is not None and due + EXAM_GAP_SECONDS <= elapsed:
            self._store_exam_capture(run, session, None, due)
            due += EXAM_CAPTURE_INTERVAL
        return replace(run, next_capture_due=due)

    def _close_station(self, run: GuidedRun, session: EmotionalSession, exam: Exam) -> GuidedRun:
        """El docente terminó el examen: la estación termina y muestra el debriefing."""
        if run.phase is GuidedPhase.READY and exam.started_at is not None:
            # Calibrada, pero no volvió a comunicarse tras el inicio: sus huecos también se registran.
            ready_at = max(exam.started_at, run.calibrated_at or exam.started_at)
            run = replace(run, phase=GuidedPhase.EXAM, step_started_at=exam.started_at, next_capture_due=self._next_slot(
                (ready_at - exam.started_at).total_seconds() - EXAM_CAPTURE_INTERVAL))
        if run.phase is GuidedPhase.EXAM and exam.closed_at is not None:
            run = self._fill_exam_gaps(run, session, (exam.closed_at - run.step_started_at).total_seconds())
        if session.state is SessionState.IN_PROGRESS:
            if self.repository.list_captures(session.id):
                self.sessions.finish_guided(session.id)
            else:
                self.sessions.cancel_session(session.id)
        self._live.pop(session.id, None)
        return self.repository.save_run(replace(run, phase=GuidedPhase.FINISHED, ended_at=self.clock(),
                                                step_started_at=None, next_capture_due=None))

    def _tick_station(self, run: GuidedRun, session: EmotionalSession) -> GuidedRun:
        exam = self._exam(session)
        if exam is None or not run.active:
            return run
        if exam.state is ExamState.CLOSED:
            return self._close_station(run, session, exam)
        changed = False
        if run.phase is GuidedPhase.WAITING and session.authorization_confirmed_at is not None:
            # El docente confirmó el consentimiento: la calibración empieza sola.
            run = replace(run, phase=GuidedPhase.CALIBRATION, confirmed_at=session.authorization_confirmed_at)
            changed = True
        if run.phase is GuidedPhase.CALIBRATION:
            calibration = self._live_of(run.session_id).calibration
            if calibration is None or calibration.state == NOT_CALIBRATED:
                self._begin_calibration(run.session_id, keep_notice=True)
        if run.phase is GuidedPhase.READY and exam.state is ExamState.IN_PROGRESS:
            run = replace(run, phase=GuidedPhase.EXAM, step_index=0, step_started_at=exam.started_at,
                          next_capture_due=self._next_slot(self._seconds(exam.started_at) - EXAM_CAPTURE_INTERVAL))
            changed = True
        if run.phase is GuidedPhase.EXAM:
            before = run.next_capture_due
            run = self._fill_exam_gaps(run, session, self._seconds(run.step_started_at))
            changed = changed or run.next_capture_due != before
        return self.repository.save_run(run) if changed else run

    def create_station(self, session: EmotionalSession) -> str:
        """Prepara la estación que se unió a un examen y entrega su enlace una sola vez.
        Sin consentimiento confirmado espera: no se analiza ningún cuadro."""
        if session.exam_id is None or self._exam(session) is None:
            raise GuidedConflict("La sesión no pertenece a un examen")
        model_id, version = self.resolve_model()
        session = self.sessions.record_emotion_model(session.id, model_id, version)
        token = secrets.token_urlsafe(32)
        self.repository.save_run(GuidedRun(
            session_id=session.id, owner_user_id=session.owner_user_id, created_at=self.clock(),
            phase=GuidedPhase.WAITING, view_token_hash=hash_token(token)))
        self.audit.record(None, AuditAction.CREATE, RESOURCE, session.id)
        return token

    def station_phase(self, session_id: str) -> str | None:
        """Solo la fase de la estación, para la vista del docente."""
        run = self.repository.get_run(session_id)
        return None if run is None else self._tick(run).phase.value

    def close_station(self, session_id: str) -> None:
        """El examen terminó: cierra la estación (si existe) y deja el debriefing."""
        run = self.repository.get_run(session_id)
        if run is not None:
            self._tick(run)

    def _next_step(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol, skipped: bool,
                   reason: str | None = None) -> GuidedRun:
        run = self._log_step(run, skipped, reason)
        group = self._group(protocol, run.phase is GuidedPhase.BEFORE_ANALYZER)
        later = [index for index in group if index > run.step_index]
        if run.phase is GuidedPhase.STIMULI:
            return self._start_during(run, session, protocol, later)
        if later:
            return self._start_step(run, protocol, run.phase, later[0])
        return self._to_analyzer(run, session, protocol)

    def _tick(self, run: GuidedRun) -> GuidedRun:
        """Avanza según el reloj del servidor: fin de exposición y capturas sin cuadros."""
        if run.phase in EXAM_STATION_PHASES or (run.phase is GuidedPhase.CALIBRATION and self.exam_of):
            session = self._session(run.session_id)
            if session.exam_id is not None:
                return self._tick_station(run, session)
        if run.phase is GuidedPhase.LIVE:
            return self._tick_live(run)
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            return run
        session = self._session(run.session_id)
        protocol = self._protocol(session)
        changed = False
        while run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            step = protocol.steps[run.step_index]
            elapsed = self._seconds(run.step_started_at)
            if step.is_timed:
                advanced = self._tick_timed(run, session, protocol, step, elapsed)
                if advanced is None:
                    break
                run, changed = advanced, True
                continue
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

    # --- Apoyos del protocolo ----------------------------------------------------------------

    @staticmethod
    def _supports_payload(protocol: Protocol) -> dict[str, Any]:
        supports = protocol.supports
        return {"pictograms": supports.pictograms, "large_controls": supports.large_controls,
                "read_aloud": supports.read_aloud, "no_time_limit": supports.no_time_limit,
                "pause": supports.pause.value}

    def _screen_supports(self, session: EmotionalSession) -> dict[str, bool] | None:
        """Lo que la pantalla de la persona necesita saber de los apoyos."""
        if session.protocol_id is None:
            return None
        supports = self._protocol(session).supports
        shown = {"pictograms": supports.pictograms, "large_controls": supports.large_controls,
                 "read_aloud": supports.read_aloud}
        return shown if any(shown.values()) else None

    def _waiting_for_conductor(self, run: GuidedRun, session: EmotionalSession) -> bool:
        if run.phase is not GuidedPhase.STIMULI or run.next_capture_due is None or session.protocol_id is None:
            return False
        protocol = self._protocol(session)
        step = protocol.steps[run.step_index]
        return (protocol.supports.pause is PauseMode.WAIT and step.is_timed
                and self._seconds(run.step_started_at) < run.next_capture_due)

    # --- Repetir un paso ---------------------------------------------------------------------

    def _step_attempts(self, session_id: str,
                       step_index: int) -> list[PracticeResult | RecognitionResult | DrawingResult | GameResult]:
        """Los intentos ya guardados de un paso, de cualquier tipo."""
        items: list[PracticeResult | RecognitionResult | DrawingResult | GameResult] = [
            *self.repository.list_practice_attempts(session_id), *self.repository.list_recognition_attempts(session_id),
            *self.repository.list_drawing_attempts(session_id), *self.repository.list_game_attempts(session_id)]
        return [item for item in items if item.step_index == step_index]

    def _can_repeat(self, run: GuidedRun, session: EmotionalSession) -> bool:
        """En la pausa tras responder, lograrlo o vencer el tiempo, y con intentos libres."""
        if run.phase is not GuidedPhase.STIMULI or run.next_capture_due is None or session.protocol_id is None:
            return False
        step = self._protocol(session).steps[run.step_index]
        return (step.is_timed
                and self._seconds(run.step_started_at) < run.next_capture_due
                and run.step_attempt < MAX_STEP_ATTEMPTS)

    def repeat_step(self, user: User, session_id: str) -> GuidedRun:
        """«Repetir este paso»: el mismo reconocimiento o ejercicio empieza otra vez,
        con las mismas opciones. Cada intento se guarda; las métricas cuentan el primero."""
        run, session = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        run = self._tick(run)
        with self._practice_lock:
            fresh = self.repository.get_run(session_id) or run
            if not self._can_repeat(fresh, session):
                raise GuidedConflict("Este paso no se puede repetir ahora")
            self._live_of(session_id).practice = None
            run = self.repository.save_run(replace(fresh, step_started_at=self.clock(), next_capture_due=None,
                                                   step_attempt=fresh.step_attempt + 1, game_progress=None))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return run

    def continue_after_pause(self, user: User, session_id: str) -> GuidedRun:
        """«Seguir»: con la pausa «esperar a quien conduce», pasa al paso siguiente."""
        run, session = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        run = self._tick(run)
        with self._practice_lock:
            fresh = self.repository.get_run(session_id) or run
            if not self._waiting_for_conductor(fresh, session):
                raise GuidedConflict("No hay un paso esperando para seguir")
            elapsed = self._seconds(fresh.step_started_at)
            self.repository.save_run(replace(fresh, next_capture_due=elapsed))
        run = self._tick(self.repository.get_run(session_id) or fresh)
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return run

    # --- Práctica de expresiones ----------------------------------------------------------

    def _tick_timed(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol,
                    step: ProtocolStep, elapsed: float) -> GuidedRun | None:
        """Avanza un ejercicio o un reconocimiento por el reloj: tras la pausa del
        logro o de la respuesta, o al vencer el tiempo máximo. None si sigue."""
        limit_seconds = self._limit(protocol, step)
        if run.next_capture_due is None and elapsed < limit_seconds:
            return None
        if run.next_capture_due is not None and elapsed < run.next_capture_due:
            return None
        with self._practice_lock:
            # Un cuadro pudo lograrlo mientras tanto: se decide con el estado guardado.
            fresh = self.repository.get_run(run.session_id) or run
            if (fresh.phase, fresh.step_index, fresh.step_started_at) != (run.phase, run.step_index,
                                                                           run.step_started_at):
                return fresh
            run = fresh
            if run.next_capture_due is None:
                if elapsed < limit_seconds:
                    return None
                limit = run.step_started_at + timedelta(seconds=limit_seconds)
                if step.is_recognition:
                    self._store_recognition(run, session, step, RecognitionOutcome.TIMED_OUT, ended_at=limit)
                elif step.is_drawing:
                    self._store_drawing(run, session, RecognitionOutcome.TIMED_OUT, ended_at=limit)
                elif step.is_game:
                    self._store_game(run, session, step, GameOutcome.TIMED_OUT, ended_at=limit)
                else:
                    self._store_practice(run, session, step, PracticeOutcome.TIMED_OUT, ended_at=limit)
                # También sin lograrlo hay una pausa antes del paso siguiente (§14.5).
                pause = self._step_pause(protocol)
                pause_until = limit_seconds + pause
                if pause > 0 and elapsed < pause_until:
                    return self.repository.save_run(replace(run, next_capture_due=pause_until))
            elif elapsed < run.next_capture_due:
                return None
            return self.repository.save_run(self._next_step(replace(run, next_capture_due=None), session,
                                                            protocol, skipped=False))

    def _practice_tracker(self, run: GuidedRun, session: EmotionalSession, step: ProtocolStep) -> PracticeTracker:
        """El seguidor del ejercicio en curso; uno nuevo si cambió el paso."""
        live = self._live_of(run.session_id)
        started = run.step_started_at.timestamp()
        tracker = live.practice
        if tracker is None or tracker.step_index != run.step_index or tracker.started_at != started:
            calibration = live.calibration
            # Con base neutral, el nivel es relativo a ella; pedir neutral usa la probabilidad directa.
            relative = (calibration is not None and calibration.state == CALIBRATED
                        and step.target_expression != "neutral")
            tracker = live.practice = PracticeTracker(
                run.step_index, started, step.hold_seconds, relative,
                threshold=self.practice.threshold, release_threshold=self.practice.release_threshold,
                smoothing_seconds=self.practice.smoothing_seconds)
        if not run.practice_feedback:
            tracker.feedback_visible = False
        return tracker

    def _practice_value(self, live: _Live, tracker: PracticeTracker, step: ProtocolStep,
                        assessment: FrameAssessment) -> float | None:
        """Lo que aporta un cuadro al nivel; None si no sirve (sin rostro o con un problema de calidad)."""
        if not assessment.ok or not assessment.distribution:
            return None
        if tracker.relative and live.calibration is not None and live.calibration.state == CALIBRATED:
            return live.calibration.relative_level(assessment.distribution, step.target_expression)
        return float(assessment.distribution.get(step.target_expression, 0.0))

    def _store_practice(self, run: GuidedRun, session: EmotionalSession, step: ProtocolStep,
                        outcome: PracticeOutcome, ended_at: datetime, seconds: float | None = None) -> None:
        """Guarda el resultado del ejercicio y descarta su seguidor."""
        live = self._live_of(run.session_id)
        tracker = live.practice
        if tracker is not None and (tracker.step_index != run.step_index
                                    or tracker.started_at != run.step_started_at.timestamp()):
            tracker = None
        if tracker is None:
            tracker = self._practice_tracker(run, session, step)
        self.repository.save_practice_result(PracticeResult(
            id=str(uuid4()), session_id=session.id, step_index=run.step_index,
            target_expression=step.target_expression, outcome=outcome, peak_level=round(tracker.peak, 4),
            relative_to_calibration=tracker.relative,
            feedback_visible=tracker.feedback_visible and run.practice_feedback, analyzed_frames=tracker.analyzed, flagged_frames=tracker.flagged,
            emotion_model_id=session.emotion_model_id or "", emotion_model_version=session.emotion_model_version or "",
            started_at=run.step_started_at, ended_at=max(run.step_started_at, ended_at),
            seconds_to_achieve=seconds, attempt=run.step_attempt))
        live.practice = None

    def _end_practice(self, run: GuidedRun, session: EmotionalSession, outcome: PracticeOutcome) -> None:
        """Saltar o detener un ejercicio sin terminar: se registra cómo terminó.
        Si ya venció el tiempo, cuenta como no logrado; si ya se logró, no cambia."""
        if run.phase is not GuidedPhase.STIMULI or session.protocol_id is None:
            return
        step = self._protocol(session).steps[run.step_index]
        if not step.is_practice or run.next_capture_due is not None:
            return
        with self._practice_lock:
            fresh = self.repository.get_run(run.session_id) or run
            if fresh.next_capture_due is not None or fresh.step_started_at != run.step_started_at:
                return
            limit = run.step_started_at + timedelta(seconds=self._limit(self._protocol(session), step))
            if self.clock() >= limit:
                self._store_practice(run, session, step, PracticeOutcome.TIMED_OUT, ended_at=limit)
            else:
                self._store_practice(run, session, step, outcome, ended_at=self.clock())

    def _practice_frame(self, run: GuidedRun, session: EmotionalSession, step: ProtocolStep, frame) -> None:
        """Cada cuadro del ejercicio actualiza el nivel. Si ya hay un cuadro de esta
        sesión en análisis, este se descarta: el nivel tolera cuadros perdidos."""
        limit_seconds = self._limit(self._protocol(session), step)
        if run.next_capture_due is not None or self._seconds(run.step_started_at) >= limit_seconds:
            return  # logrado (en pausa) o vencido: no se analiza
        live = self._live_of(run.session_id)
        with self._practice_lock:
            if live.analyzing:
                return
            live.analyzing = True
        try:
            assessment = self._assess(session, frame)
        finally:
            live.analyzing = False
        with self._practice_lock:
            fresh = self.repository.get_run(run.session_id)
            if (fresh is None or fresh.phase is not GuidedPhase.STIMULI or fresh.step_index != run.step_index
                    or fresh.step_started_at != run.step_started_at or fresh.next_capture_due is not None):
                return  # el paso cambió mientras se analizaba
            elapsed = self._seconds(fresh.step_started_at)
            if elapsed >= limit_seconds:
                return
            tracker = self._practice_tracker(fresh, session, step)
            if tracker.add(self.clock().timestamp(), self._practice_value(live, tracker, step, assessment)):
                self._store_practice(fresh, session, step, PracticeOutcome.ACHIEVED, ended_at=self.clock(),
                                     seconds=round(elapsed, 2))
                # La persona ve el logro durante la pausa; después el paso avanza solo.
                self.repository.save_run(replace(fresh, next_capture_due=elapsed
                                                 + self._step_pause(self._protocol(session))))

    def set_practice_feedback(self, user: User, session_id: str, visible: bool) -> GuidedRun:
        """Quien conduce enciende o apaga la señal del nivel para toda la sesión.
        Si cambia a mitad de un ejercicio, ese ejercicio queda con la señal no
        visible todo el tiempo."""
        run, session = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        with self._practice_lock:
            run = self.repository.get_run(session_id) or run
            step = self._steps(session)[run.step_index] if run.phase is GuidedPhase.STIMULI else None
            if (step is not None and step.is_practice and run.next_capture_due is None
                    and bool(visible) != run.practice_feedback):
                self._practice_tracker(run, session, step).feedback_visible = False
            run = self.repository.save_run(replace(run, practice_feedback=bool(visible)))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return run

    def _participant_practice(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve la persona en un ejercicio: la instrucción, un nivel de 0 a 1
        (nulo con la señal apagada) y si lo logró. Nunca la expresión detectada,
        probabilidades ni calidad."""
        achieved = self._practice_achieved(run, step)
        level = None
        if run.practice_feedback:
            live = self._live.get(run.session_id)
            tracker = live.practice if live else None
            current = (tracker is not None and tracker.step_index == run.step_index
                       and run.step_started_at is not None and tracker.started_at == run.step_started_at.timestamp())
            level = 1.0 if achieved else round(tracker.level, 2) if current else 0.0
        instruction = IMITATION_INSTRUCTION if step.imitate else PRACTICE_INSTRUCTIONS[step.target_expression]
        return {"instruction": instruction, "level": level, "achieved": achieved,
                "message": PRACTICE_ACHIEVED_MESSAGE if achieved else None,
                "frame_interval_ms": self.practice.frame_interval_ms}

    def _practice_achieved(self, run: GuidedRun, step: ProtocolStep) -> bool:
        """En pausa tras un logro. La pausa tras vencer el tiempo empieza justo en
        exposure_seconds; la de un logro, antes (se logró antes de vencer)."""
        if run.next_capture_due is None:
            return False
        protocol = self._protocol(self._session(run.session_id))
        return run.next_capture_due < self._limit(protocol, step) + self._step_pause(protocol)

    def _conductor_practice(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve quien conduce en un ejercicio: la expresión pedida, el nivel
        en vivo (aunque la señal de la persona esté apagada) y si se logró."""
        participant = self._participant_practice(replace(run, practice_feedback=True), step)
        return {"target_expression": step.target_expression, "hold_seconds": step.hold_seconds,
                "imitate": step.imitate, "level": participant["level"], "achieved": participant["achieved"]}

    def practice_frame_drops_when_busy(self, token: str) -> bool:
        """Si el cuadro de esta pantalla es de un ejercicio de práctica en curso:
        sin cupo de análisis, ese cuadro se descarta en lugar de esperar."""
        run = self.repository.get_run_by_token_hash(hash_token(token)) if token else None
        if run is None or not run.active or run.phase is not GuidedPhase.STIMULI or run.next_capture_due is not None:
            return False
        session = self._session(run.session_id)
        return session.protocol_id is not None and self._protocol(session).steps[run.step_index].is_practice

    # --- Reconocimiento de emociones ------------------------------------------------------

    @staticmethod
    def _recognition_options(session_id: str, step_index: int, step: ProtocolStep) -> tuple[str, ...]:
        """La expresión de la imagen y distractoras elegidas al azar, en orden al
        azar. La semilla es la sesión y el paso: cada consulta da las mismas."""
        chooser = random.Random(f"{session_id}:{step_index}")
        pool = [item for item in RECOGNITION_DISTRACTORS if item != step.target_expression]
        options = [step.target_expression, *chooser.sample(pool, step.option_count - 1)]
        chooser.shuffle(options)
        return tuple(options)

    def _recognition_result(self, run: GuidedRun) -> RecognitionResult | None:
        """El resultado del paso en curso, si ya terminó (respondido o vencido)."""
        return next((item for item in self.repository.list_recognition_attempts(run.session_id)
                     if item.step_index == run.step_index and item.attempt == run.step_attempt
                     and run.step_started_at is not None), None)

    def _store_recognition(self, run: GuidedRun, session: EmotionalSession, step: ProtocolStep,
                           outcome: RecognitionOutcome, ended_at: datetime, chosen: str | None = None,
                           seconds: float | None = None, by: RecognitionAnswerer | None = None) -> None:
        self.repository.save_recognition_result(RecognitionResult(
            id=str(uuid4()), session_id=session.id, step_index=run.step_index, stimulus_id=step.stimulus_id,
            target_expression=step.target_expression,
            options=self._recognition_options(session.id, run.step_index, step), outcome=outcome,
            started_at=run.step_started_at, ended_at=max(run.step_started_at, ended_at),
            chosen_expression=chosen, seconds_to_answer=seconds, answered_by=by,
            attempt=run.step_attempt))

    def _end_recognition(self, run: GuidedRun, session: EmotionalSession, outcome: RecognitionOutcome) -> None:
        """Saltar o detener un reconocimiento sin respuesta: se registra cómo
        terminó. Si ya venció el tiempo, cuenta como vencido; si ya se respondió,
        no cambia."""
        if run.phase is not GuidedPhase.STIMULI or session.protocol_id is None:
            return
        step = self._protocol(session).steps[run.step_index]
        if not (step.is_recognition or step.is_drawing or step.is_game) or run.next_capture_due is not None:
            return
        with self._practice_lock:
            fresh = self.repository.get_run(run.session_id) or run
            if fresh.next_capture_due is not None or fresh.step_started_at != run.step_started_at:
                return
            limit = run.step_started_at + timedelta(seconds=self._limit(self._protocol(session), step))
            ended = (RecognitionOutcome.TIMED_OUT, limit) if self.clock() >= limit else (outcome, self.clock())
            if step.is_drawing:
                self._store_drawing(run, session, ended[0], ended_at=ended[1])
            elif step.is_game:
                self._store_game(fresh, session, step, GameOutcome(ended[0].value), ended_at=ended[1])
            else:
                self._store_recognition(run, session, step, ended[0], ended_at=ended[1])

    def _answer(self, run: GuidedRun, expression: str, by: RecognitionAnswerer) -> GuidedRun:
        """Registra la opción elegida. Después, la persona lee el nombre de la
        emoción de la imagen durante la pausa y el paso avanza solo."""
        session = self._session(run.session_id)
        if run.phase is not GuidedPhase.STIMULI or session.protocol_id is None:
            raise GuidedConflict("No hay un reconocimiento en curso")
        step = self._protocol(session).steps[run.step_index]
        if not (step.is_recognition or step.is_drawing):
            raise GuidedConflict("No hay un reconocimiento en curso")
        options = DRAWING_OPTIONS if step.is_drawing else self._recognition_options(session.id, run.step_index, step)
        if expression not in options:
            raise ValueError("Esa opción no se mostró en este paso")
        with self._practice_lock:
            fresh = self.repository.get_run(run.session_id) or run
            if (fresh.phase, fresh.step_index, fresh.step_started_at) != (run.phase, run.step_index,
                                                                           run.step_started_at):
                raise GuidedConflict("El paso cambió")
            elapsed = self._seconds(fresh.step_started_at)
            if fresh.next_capture_due is not None or elapsed >= self._limit(self._protocol(session), step):
                raise GuidedConflict("Este paso ya terminó")
            if step.is_drawing:
                self._store_drawing(fresh, session, RecognitionOutcome.ANSWERED, ended_at=self.clock(),
                                    chosen=expression, seconds=round(elapsed, 2), by=by)
            else:
                self._store_recognition(fresh, session, step, RecognitionOutcome.ANSWERED, ended_at=self.clock(),
                                        chosen=expression, seconds=round(elapsed, 2), by=by)
            return self.repository.save_run(replace(
                fresh, next_capture_due=elapsed + self._step_pause(self._protocol(session))))

    def participant_answer(self, token: str, expression: str) -> None:
        """La persona tocó una opción en su pantalla."""
        self._answer(self._tick(self._by_token(token)), expression, RecognitionAnswerer.PARTICIPANT)

    def record_recognition(self, user: User, session_id: str, expression: str) -> GuidedRun:
        """Quien conduce registra la opción que la persona señaló o dijo."""
        run, _ = self._conducted(user, session_id)
        run = self._answer(self._tick(run), expression, RecognitionAnswerer.CONDUCTOR)
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return run

    def _participant_recognition(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve la persona: la pregunta, las opciones y, al terminar el paso,
        el nombre de la emoción de la imagen. No dice si acertó."""
        result = self._recognition_result(run)
        target = step.target_expression
        answers = SITUATION_ANSWERS if step.situation else RECOGNITION_ANSWERS
        explanation = self.explanation_of(target) if result and self.explanation_of else None
        return {"question": SITUATION_QUESTION if step.situation else RECOGNITION_QUESTION,
                "situation": step.situation,
                "options": [{"key": item, "label": RECOGNITION_NAMES[item]}
                            for item in self._recognition_options(run.session_id, run.step_index, step)],
                "chosen": result.chosen_expression if result else None,
                "message": answers[target] if result else None,
                # Solo al terminar el paso: la explicación del catálogo y, con una
                # situación, que otras personas podrían sentir algo distinto.
                "explanation": explanation or None,
                "note": SITUATION_NOTE if result and step.situation else None}

    def _conductor_recognition(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve quien conduce: las opciones, la de la imagen y la elegida."""
        result = self._recognition_result(run)
        return {"target_expression": step.target_expression, "situation": step.situation,
                "options": list(self._recognition_options(run.session_id, run.step_index, step)),
                "chosen_expression": result.chosen_expression if result else None,
                "outcome": result.outcome.value if result else None}

    # --- Dibujo: solo la emoción señalada, nunca el dibujo -------------------------------

    def _drawing_result(self, run: GuidedRun) -> DrawingResult | None:
        """El resultado del intento en curso, si ya terminó (respondido o vencido)."""
        return next((item for item in self.repository.list_drawing_attempts(run.session_id)
                     if item.step_index == run.step_index and item.attempt == run.step_attempt
                     and run.step_started_at is not None), None)

    def _store_drawing(self, run: GuidedRun, session: EmotionalSession, outcome: RecognitionOutcome,
                       ended_at: datetime, chosen: str | None = None, seconds: float | None = None,
                       by: RecognitionAnswerer | None = None) -> None:
        self.repository.save_drawing_result(DrawingResult(
            id=str(uuid4()), session_id=session.id, step_index=run.step_index, outcome=outcome,
            started_at=run.step_started_at, ended_at=max(run.step_started_at, ended_at),
            chosen_expression=chosen, seconds_to_answer=seconds, answered_by=by, attempt=run.step_attempt))

    def _participant_drawing(self, run: GuidedRun) -> dict[str, Any]:
        """Lo que ve la persona: la consigna, la pregunta, las emociones para
        señalar y, al terminar, la que eligió. No se compara con el dibujo."""
        result = self._drawing_result(run)
        chosen = result.chosen_expression if result else None
        return {"instruction": DRAWING_INSTRUCTION, "question": DRAWING_QUESTION,
                "options": [{"key": item, "label": RECOGNITION_NAMES[item]} for item in DRAWING_OPTIONS],
                # Cambia con cada intento: la pantalla empieza un lienzo nuevo.
                "round": f"{run.step_index}-{run.step_attempt}",
                "finished": result is not None,
                "chosen": chosen,
                "message": DRAWING_ANSWERS[chosen] if chosen else None}

    def _conductor_drawing(self, run: GuidedRun) -> dict[str, Any]:
        """Lo que ve quien conduce: las emociones para registrar y la elegida."""
        result = self._drawing_result(run)
        return {"options": list(DRAWING_OPTIONS),
                "chosen_expression": result.chosen_expression if result else None,
                "outcome": result.outcome.value if result else None}

    # --- Juego de emparejar: rondas con contadores, sin puntaje --------------------------

    @staticmethod
    def _game_progress(run: GuidedRun) -> dict[str, Any]:
        """La ronda en curso y los contadores del intento; nuevos al empezar el
        paso o un intento. state: playing, retry (eligió otra emoción), matched
        (la encontró), shown (se le mostró) o finished (terminó el juego)."""
        key = f"{run.step_index}-{run.step_attempt}"
        if run.game_progress and run.game_progress.get("key") == key:
            return {**run.game_progress, "tried": list(run.game_progress.get("tried") or ())}
        return {"key": key, "round": 0, "tried": [], "removed": None, "helped": False, "state": "playing",
                "done": 0, "matched": 0, "first": 0, "help": 0, "by_conductor": 0}

    def _game_target(self, step: ProtocolStep, round_index: int) -> str | None:
        """La emoción de la imagen de la ronda: su expresión esperada en el banco."""
        item = self.stimuli(step.game_stimulus_ids[round_index]) if round_index < len(step.game_stimulus_ids) else None
        return item.expected_expression if item is not None else None

    @staticmethod
    def _game_options(run: GuidedRun, step: ProtocolStep, round_index: int, target: str) -> tuple[str, ...]:
        """La emoción de la imagen y distractoras al azar, en orden al azar. La
        semilla es la sesión, el paso, el intento y la ronda."""
        chooser = random.Random(f"{run.session_id}:{run.step_index}:{run.step_attempt}:{round_index}")
        pool = [item for item in RECOGNITION_DISTRACTORS if item != target]
        options = [target, *chooser.sample(pool, step.option_count - 1)]
        chooser.shuffle(options)
        return tuple(options)

    def _game_result(self, run: GuidedRun) -> GameResult | None:
        """El resultado del intento en curso, si ya terminó."""
        return next((item for item in self.repository.list_game_attempts(run.session_id)
                     if item.step_index == run.step_index and item.attempt == run.step_attempt
                     and run.step_started_at is not None), None)

    def _store_game(self, run: GuidedRun, session: EmotionalSession, step: ProtocolStep, outcome: GameOutcome,
                    ended_at: datetime, progress: dict[str, Any] | None = None) -> None:
        progress = progress or self._game_progress(run)
        self.repository.save_game_result(GameResult(
            id=str(uuid4()), session_id=session.id, step_index=run.step_index, game_type=step.game_type,
            outcome=outcome, started_at=run.step_started_at, ended_at=max(run.step_started_at, ended_at),
            rounds_total=step.rounds, rounds_done=progress["done"], matched=progress["matched"],
            first_try=progress["first"], help_used=progress["help"], by_conductor=progress["by_conductor"],
            attempt=run.step_attempt))

    def _game_act(self, run: GuidedRun, action: str, expression: str | None, by: RecognitionAnswerer) -> GuidedRun:
        """Una acción del juego: elegir una emoción (answer), pedir ayuda (help) o
        pasar a la ronda siguiente (next). Tras la última ronda, el paso termina y
        sigue la pausa de siempre."""
        session = self._session(run.session_id)
        if run.phase is not GuidedPhase.STIMULI or session.protocol_id is None:
            raise GuidedConflict("No hay un juego en curso")
        protocol = self._protocol(session)
        step = protocol.steps[run.step_index]
        if not step.is_game:
            raise GuidedConflict("No hay un juego en curso")
        with self._practice_lock:
            fresh = self.repository.get_run(run.session_id) or run
            if (fresh.phase, fresh.step_index, fresh.step_started_at) != (run.phase, run.step_index,
                                                                           run.step_started_at):
                raise GuidedConflict("El paso cambió")
            elapsed = self._seconds(fresh.step_started_at)
            if fresh.next_capture_due is not None or elapsed >= self._limit(protocol, step):
                raise GuidedConflict("Este paso ya terminó")
            progress = self._game_progress(fresh)
            target = self._game_target(step, progress["round"])
            if target is None:
                raise GuidedConflict("La imagen de esta ronda ya no está disponible: salta el paso")
            options = self._game_options(fresh, step, progress["round"], target)
            playing = progress["state"] in ("playing", "retry")
            if action == "answer":
                if not playing:
                    raise GuidedConflict("Esta ronda ya terminó")
                if expression not in options or expression in progress["tried"] or expression == progress["removed"]:
                    raise ValueError("Esa opción no se muestra ahora")
                if by is RecognitionAnswerer.CONDUCTOR:
                    progress["by_conductor"] += 1
                if expression == target:
                    progress.update(state="matched", done=progress["done"] + 1, matched=progress["matched"] + 1)
                    if not progress["tried"]:
                        progress["first"] += 1
                else:
                    progress["tried"] = [*progress["tried"], expression]
                    if len(progress["tried"]) >= GAME_MISSES_BEFORE_ANSWER:
                        progress.update(state="shown", done=progress["done"] + 1)
                    else:
                        progress["state"] = "retry"
            elif action == "help":
                if not playing:
                    raise GuidedConflict("Esta ronda ya terminó")
                if not progress["helped"]:
                    progress.update(helped=True, help=progress["help"] + 1)
                    # Se quita una opción que no es, si quedan al menos dos a la vista.
                    wrong = [item for item in options if item != target and item not in progress["tried"]]
                    if len(wrong) >= 2:
                        progress["removed"] = wrong[0]
            elif action == "next":
                if playing:
                    raise GuidedConflict("Primero termina esta ronda")
                if progress["round"] + 1 < step.rounds:
                    progress.update(round=progress["round"] + 1, tried=[], removed=None, helped=False,
                                    state="playing")
                else:
                    progress["state"] = "finished"
                    self._store_game(fresh, session, step, GameOutcome.COMPLETED, ended_at=self.clock(),
                                     progress=progress)
                    return self.repository.save_run(replace(
                        fresh, game_progress=progress, next_capture_due=elapsed + self._step_pause(protocol)))
            else:
                raise ValueError("Acción del juego desconocida")
            return self.repository.save_run(replace(fresh, game_progress=progress))

    def participant_game(self, token: str, action: str, expression: str | None = None) -> None:
        """La persona tocó una emoción, «Ayuda» o «Siguiente» en su pantalla."""
        self._game_act(self._tick(self._by_token(token)), action, expression, RecognitionAnswerer.PARTICIPANT)

    def conductor_game(self, user: User, session_id: str, action: str, expression: str | None = None) -> GuidedRun:
        """Quien conduce registra la emoción que la persona señaló, pide la ayuda o pasa de ronda."""
        run, _ = self._conducted(user, session_id)
        run = self._game_act(self._tick(run), action, expression, RecognitionAnswerer.CONDUCTOR)
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return run

    def _game_round(self, run: GuidedRun, step: ProtocolStep) -> tuple[dict[str, Any], int, str | None,
                                                                          tuple[str, ...]]:
        progress = self._game_progress(run)
        index = min(progress["round"], step.rounds - 1)
        target = self._game_target(step, index)
        options = self._game_options(run, step, index, target) if target else ()
        return progress, index, target, options

    def _participant_game(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve la persona: la ronda, las emociones que puede tocar y, al
        terminar la ronda, la emoción de la imagen con su explicación. Sin puntaje."""
        progress, index, target, options = self._game_round(run, step)
        result = self._game_result(run)
        state = progress["state"] if result is None or result.outcome is GameOutcome.COMPLETED else "ended"
        answer = RECOGNITION_ANSWERS.get(target or "", "")
        messages = {
            "retry": GAME_RETRY,
            "matched": GAME_FOUND.format(answer=answer[:1].lower() + answer[1:]),
            "shown": GAME_SHOWN.format(answer=answer),
            "finished": GAME_FINISHED,
            "ended": GAME_TIME_UP if result is not None and result.outcome is GameOutcome.TIMED_OUT else None,
        }
        revealed = state in ("matched", "shown")
        explanation = self.explanation_of(target) if revealed and target and self.explanation_of else None
        return {"round": f"{run.step_index}-{run.step_attempt}-{index}", "number": index + 1, "total": step.rounds,
                "question": GAME_QUESTION, "state": state,
                "options": [{"key": item, "label": RECOGNITION_NAMES[item],
                             "available": item not in progress["tried"] and item != progress["removed"]}
                            for item in options],
                "answer": target if revealed else None,
                "message": messages.get(state),
                "explanation": explanation or None,
                "can_help": state in ("playing", "retry") and not progress["helped"],
                "last_round": index + 1 == step.rounds}

    def _conductor_game(self, run: GuidedRun, step: ProtocolStep) -> dict[str, Any]:
        """Lo que ve quien conduce: la ronda, la emoción de la imagen, las opciones
        y los contadores del intento."""
        progress, index, target, options = self._game_round(run, step)
        result = self._game_result(run)
        return {"round": index + 1, "rounds": step.rounds, "stimulus_id": step.game_stimulus_ids[index],
                "target_expression": target, "options": list(options), "tried": list(progress["tried"]),
                "removed": progress["removed"], "state": progress["state"], "helped": progress["helped"],
                "rounds_done": progress["done"], "matched": progress["matched"], "first_try": progress["first"],
                "help_used": progress["help"], "outcome": result.outcome.value if result else None}

    def _tick_live(self, run: GuidedRun) -> GuidedRun:
        """Fase live: una captura vencida sin un cuadro válido se guarda marcada."""
        changed = False
        session = None
        elapsed = self._seconds(run.step_started_at)
        while run.next_capture_due is not None and elapsed >= run.next_capture_due + QUALITY_RETRY_SECONDS:
            session = session or self._session(run.session_id)
            run = self._store_capture(run, session, None, self._live_of(run.session_id).pending, elapsed,
                                      timed_out=True)
            changed = True
        return self.repository.save_run(run) if changed else run

    # --- Capturas -----------------------------------------------------------------------

    def _store_capture(self, run: GuidedRun, session: EmotionalSession, protocol: Protocol | None,
                       assessment: FrameAssessment | None, elapsed: float, timed_out: bool) -> GuidedRun:
        """Guarda una captura. Sin protocolo (fase live) no hay estímulo y la
        siguiente vence ABSTRACT_CAPTURE_INTERVAL segundos después."""
        step = protocol.steps[run.step_index] if protocol is not None else None
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
            step_index=run.step_index, stimulus_id=step.stimulus_id if step else None,
            seconds_since_stimulus=round(elapsed, 2), emotion=assessment.emotion, confidence=assessment.confidence,
            distribution=assessment.distribution, calibrated_emotion=calibrated))
        live.pending = None
        if step is None:
            return replace(run, next_capture_due=(run.next_capture_due or 0.0) + ABSTRACT_CAPTURE_INTERVAL)
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
        """Prepara la sesión y entrega una sola vez el enlace de la pantalla de la
        persona. La autorización ya se confirmó al iniciar la sesión: empieza en
        el cuestionario previo, en las imágenes previas o en la calibración."""
        session = self._session(session_id)
        if session.owner_user_id != user.id:
            raise PermissionError("Solo quien conduce la sesión la prepara")
        protocol = self.protocols(session.protocol_id) if session.protocol_id else None
        if session.protocol_id and protocol is None:
            raise GuidedConflict("El protocolo de la sesión ya no está disponible")
        if session.state is not SessionState.IN_PROGRESS:
            raise GuidedConflict("La sesión no está en progreso")
        if session.authorization_confirmed_at is None:
            raise GuidedConflict("La sesión empieza con la confirmación de la autorización")
        if self.repository.get_run(session_id) is not None:
            raise GuidedConflict("La sesión guiada ya está preparada")
        if protocol is None or protocol.uses_camera:
            # Sin cámara no se analiza ningún cuadro: no se necesita el modelo facial.
            model_id, version = self.resolve_model()
            session = self.sessions.record_emotion_model(session.id, model_id, version)
        token = secrets.token_urlsafe(32)
        run = GuidedRun(session_id=session.id, owner_user_id=user.id, created_at=self.clock(),
                        confirmed_at=session.authorization_confirmed_at, view_token_hash=hash_token(token))
        if protocol is None:
            run = replace(run, phase=GuidedPhase.CALIBRATION)
        elif session.pre_questionnaire_id:
            run = replace(run, phase=GuidedPhase.PRE_QUESTIONNAIRE)
        else:
            run = self._after_pre(run, session, protocol)
        run = self.repository.save_run(run)
        self.audit.record(user, AuditAction.CREATE, RESOURCE, session.id)
        return run, token

    def new_view_link(self, user: User, session_id: str) -> str:
        """Reemplaza el enlace de la pantalla de la persona (el anterior deja de valer)."""
        run, _ = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        token = secrets.token_urlsafe(32)
        self.repository.save_run(replace(run, view_token_hash=hash_token(token)))
        return token

    def advance(self, user: User, session_id: str) -> GuidedRun:
        """Continúa tras un cuestionario: el previo debe estar respondido."""
        run, session = self._conducted(user, session_id)
        if run.phase is GuidedPhase.PRE_QUESTIONNAIRE:
            if not self.questionnaire_answered(session.id, "pre"):
                raise GuidedConflict("Falta responder el cuestionario previo")
            return self.repository.save_run(self._after_pre(run, session, self._protocol(session)))
        if run.phase is GuidedPhase.POST_QUESTIONNAIRE:
            if not self.questionnaire_answered(session.id, "post"):
                raise GuidedConflict("Falta responder el cuestionario posterior")
            return self.repository.save_run(self._finish(run, session))
        raise GuidedConflict("No hay nada que continuar en esta fase")

    def start(self, user: User, session_id: str) -> GuidedRun:
        """«Empezar» en una sesión sin cámara: el tiempo del primer paso corre desde ahora."""
        run, session = self._conducted(user, session_id)
        if session.exam_id is not None or self._camera_active(run, session):
            raise GuidedConflict("Esta sesión empieza con la calibración")
        if run.phase is not GuidedPhase.READY:
            raise GuidedConflict("La sesión ya empezó o todavía tiene el cuestionario previo")
        return self.repository.save_run(self._first_step(run, session, self._protocol(session)))

    def continue_without_camera(self, user: User, session_id: str) -> GuidedRun:
        """La cámara no está disponible (permiso denegado, sin cámara o falla): la
        sesión sigue sin ella. Desde ahora no se calibra; si se estaba calibrando,
        empieza el primer paso. Un paso en curso que la necesita se salta, y los
        siguientes que la necesitan se saltan sin empezar. Los reconocimientos siguen."""
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if session.exam_id is not None or session.protocol_id is None:
            raise GuidedConflict("Esta sesión necesita la cámara")
        if not self._uses_camera(session):
            raise GuidedConflict("Esta sesión no usa la cámara")
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        if run.camera_off_at is not None:
            return run
        live = self._live_of(session_id)
        live.calibration, live.calibration_notice, live.pending = None, None, None
        protocol = self._protocol(session)
        run = replace(run, camera_off_at=self.clock())
        if run.phase is GuidedPhase.CALIBRATION:
            run = self._first_step(run, session, protocol)
        elif run.phase is GuidedPhase.STIMULI and protocol.steps[run.step_index].uses_camera:
            self._end_practice(run, session, PracticeOutcome.SKIPPED)
            run = self._next_step(replace(run, next_capture_due=None), session, protocol, skipped=True,
                                  reason=NO_CAMERA_SKIP)
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session_id)
        return self.repository.save_run(run)

    def participant_camera_problem(self, token: str, reason: str) -> None:
        """La pantalla de la persona no pudo usar la cámara: quien conduce lo ve y decide."""
        if reason not in CAMERA_PROBLEMS:
            raise ValueError("Motivo no válido")
        run = self._by_token(token)
        self._live_of(run.session_id).camera_problem = reason

    def start_calibration(self, user: User, session_id: str) -> GuidedRun:
        run, session = self._conducted(user, session_id)
        if not self._camera_active(run, session):
            raise GuidedConflict("Esta sesión no usa la cámara: no se calibra")
        if run.phase is not GuidedPhase.CALIBRATION:
            raise GuidedConflict("La calibración va antes de las imágenes y después del cuestionario previo")
        self._begin_calibration(session_id)
        return run

    def skip(self, user: User, session_id: str) -> GuidedRun:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            raise GuidedConflict("No hay un estímulo en curso")
        self._end_practice(run, session, PracticeOutcome.SKIPPED)
        self._end_recognition(run, session, RecognitionOutcome.SKIPPED)
        self._live_of(session_id).pending = None
        return self.repository.save_run(self._next_step(replace(run, next_capture_due=None), session,
                                                        self._protocol(session), skipped=True))

    def _stop(self, run: GuidedRun, reason: StopReason, actor: User | None) -> GuidedRun:
        if not run.active:
            return run
        session = self._session(run.session_id)
        if session.state in (SessionState.CREATED, SessionState.IN_PROGRESS, SessionState.RECOGNIZED):
            self.sessions.cancel_session(session.id)
        self._end_practice(run, session, PracticeOutcome.STOPPED)
        self._end_recognition(run, session, RecognitionOutcome.STOPPED)
        if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            run = self._log_step(run, skipped=True)
        self._live.pop(run.session_id, None)
        # La estación de un examen conserva su enlace para mostrar el debriefing.
        token_hash = run.view_token_hash if session.exam_id is not None else None
        stopped = self.repository.save_run(replace(
            run, phase=GuidedPhase.STOPPED, stop_reason=reason, ended_at=self.clock(), step_started_at=None,
            next_capture_due=None, view_token_hash=token_hash))
        self.audit.record(actor, AuditAction.UPDATE, RESOURCE, run.session_id)
        return stopped

    def stop(self, user: User, session_id: str, reason: StopReason | str) -> GuidedRun:
        """La persona o su tutor pidieron parar, o quien conduce terminó: termina de inmediato."""
        run, _ = self._conducted(user, session_id)
        return self._stop(run, StopReason(reason), user)

    def finish_live(self, user: User, session_id: str) -> GuidedRun:
        """Quien conduce termina el registro sin protocolo. Como en el analizador
        web, la sesión conserva una expresión registrada: la de la última captura
        de buena calidad. Sin ninguna, la sesión queda cancelada."""
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        if run.phase is not GuidedPhase.LIVE:
            raise GuidedConflict("Solo se termina así el registro sin protocolo")
        good = [item for item in self.repository.list_captures(session.id)
                if item.quality is CaptureQuality.GOOD and item.emotion is not None]
        if good:
            last = good[-1]
            self.sessions.record_recognition(session.id, last.emotion, last.confidence,
                                             session.emotion_model_id or last.emotion_model_id,
                                             session.emotion_model_version or last.emotion_model_version)
            self.sessions.finish_without_activity(session.id)
        else:
            self.sessions.cancel_session(session.id)
        self._live.pop(session.id, None)
        finished = self.repository.save_run(replace(run, phase=GuidedPhase.FINISHED, ended_at=self.clock(),
                                                    step_started_at=None, next_capture_due=None,
                                                    view_token_hash=None))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, session.id)
        return finished

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
            note=note if kind is MarkerKind.NOTE else None))
        self.audit.record(user, AuditAction.CREATE, MARKER, marker.id)
        if kind is MarkerKind.ASKED_TO_STOP:
            # Si la persona pide parar, la sesión termina de inmediato.
            self._stop(run, StopReason.PARTICIPANT, user)
        return marker

    def record_verbal(self, user: User, session_id: str, step_index: int, text: str) -> VerbalResponse:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        protocol = self._protocol(session)
        if not 0 <= step_index < len(protocol.steps) or not protocol.steps[step_index].record_verbal_response:
            raise ValueError("Ese estímulo no registra lo que la persona dice ver")
        shown = {item["step_index"] for item in run.steps_log} | (
            {run.step_index} if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI) else set())
        if step_index not in shown:
            raise GuidedConflict("Ese estímulo todavía no se mostró")
        response = self.repository.save_verbal(VerbalResponse(
            id=str(uuid4()), session_id=session.id, step_index=step_index,
            stimulus_id=protocol.steps[step_index].stimulus_id, text=text, recorded_at=self.clock(),
            recorded_by_user_id=user.id))
        self.audit.record(user, AuditAction.CREATE, VERBAL, response.id)
        return response

    @staticmethod
    def _require_station_finished(run: GuidedRun, session: EmotionalSession) -> None:
        """Sin monitoreo en vivo: las capturas de una estación se ven al terminar."""
        if session.exam_id is not None and run.active:
            raise GuidedConflict("Los resultados del examen se ven cuando la estación termina")

    def conductor_state(self, user: User, session_id: str) -> dict[str, Any]:
        run, session = self._conducted(user, session_id)
        run = self._tick(run)
        self._require_station_finished(run, session)
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
        run = self._tick(run)
        self._require_station_finished(run, session)
        self.audit.record(user, AuditAction.VIEW, CAPTURES, session_id)
        return self._summary(run, session, include_results=True)

    def _summary(self, run: GuidedRun, session: EmotionalSession, include_results: bool) -> dict[str, Any]:
        steps = self._steps(session)
        stimuli = {step.stimulus_id: self.stimuli(step.stimulus_id) if step.stimulus_id else None for step in steps}
        live = self._live.get(session.id)
        calibration = live.calibration if live else None
        step = steps[run.step_index] if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI) else None
        summary: dict[str, Any] = {
            "session_id": session.id,
            "accessible": session.protocol_id is not None and self._protocol(session).accessible,
            # Código para anotar en el formato firmado.
            "session_code": session.code,
            "phase": run.phase.value,
            "audience": session.session_type.value,
            "has_protocol": session.protocol_id is not None,
            "uses_camera": self._uses_camera(session),
            # Quien conduce siguió sin cámara, y el motivo que informó la pantalla de la persona.
            "camera_off": run.camera_off_at is not None,
            "camera_problem": live.camera_problem if live else None,
            "stop_reason": run.stop_reason.value if run.stop_reason else None,
            "step_index": run.step_index if step else None,
            "step_count": len(steps),
            "steps": [{"index": index, "stimulus_id": item.stimulus_id,
                       "title": stimuli[item.stimulus_id].title if stimuli[item.stimulus_id] else "",
                       "kind": stimuli[item.stimulus_id].kind.value if stimuli[item.stimulus_id] else "",
                       "exposure_seconds": item.exposure_seconds, "capture_after_seconds": item.capture_after_seconds,
                       "record_verbal_response": item.record_verbal_response,
                       "shown_before_analyzer": item.shown_before_analyzer,
                       "step_kind": item.kind.value, "target_expression": item.target_expression,
                       "hold_seconds": item.hold_seconds, "option_count": item.option_count,
                       "situation": item.situation, "imitate": item.imitate,
                       "game_type": item.game_type, "rounds": item.rounds}
                      for index, item in enumerate(steps)],
            # Nulo sin límite de tiempo: el paso no vence.
            "remaining_seconds": (max(0.0, step.seconds_limit - self._seconds(run.step_started_at))
                                  if step and not self._unlimited(session, step) else None),
            "supports": (self._supports_payload(self._protocol(session)) if session.protocol_id else None),
            # «Esperar a quien conduce»: el paso terminó y sigue cuando pulse «Seguir».
            "waiting_for_conductor": self._waiting_for_conductor(run, session),
            # Intento del paso en curso (1 el primero) y si se puede repetir ahora.
            "attempt": run.step_attempt if step is not None and step.is_timed
            and run.phase is GuidedPhase.STIMULI else None,
            "can_repeat": self._can_repeat(run, session),
            "max_attempts": MAX_STEP_ATTEMPTS,
            "steps_log": list(run.steps_log),
            "calibration": {"state": calibration.state if calibration else ("calibrated" if run.calibrated_at else "none"),
                            "progress": round(calibration.progress, 2) if calibration else (1.0 if run.calibrated_at else 0.0),
                            "notice": live.calibration_notice if live else None},
            "capture_status": ([item.value for item in live.pending.issues] if live and live.pending else []),
            "pre_questionnaire_id": session.pre_questionnaire_id,
            "post_questionnaire_id": session.post_questionnaire_id,
            "has_abstract": any(item and item.kind is StimulusKind.ABSTRACT for item in stimuli.values()),
            "practice_feedback": run.practice_feedback,
            "practice": (self._conductor_practice(run, step)
                         if step is not None and step.is_practice and run.phase is GuidedPhase.STIMULI else None),
            "recognition": (self._conductor_recognition(run, step)
                            if step is not None and step.is_recognition and run.phase is GuidedPhase.STIMULI
                            else None),
            "drawing": (self._conductor_drawing(run)
                        if step is not None and step.is_drawing and run.phase is GuidedPhase.STIMULI else None),
            "game": (self._conductor_game(run, step)
                     if step is not None and step.is_game and run.phase is GuidedPhase.STIMULI else None),
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
            summary["practice_results"] = [{
                "step_index": item.step_index, "target_expression": item.target_expression,
                "outcome": item.outcome.value, "seconds_to_achieve": item.seconds_to_achieve,
                "peak_level": item.peak_level, "relative_to_calibration": item.relative_to_calibration,
                "feedback_visible": item.feedback_visible,
            } for item in self.repository.list_practice_results(session.id)]
            summary["recognition_results"] = [{
                "step_index": item.step_index, "stimulus_id": item.stimulus_id,
                "target_expression": item.target_expression, "options": list(item.options),
                "outcome": item.outcome.value, "chosen_expression": item.chosen_expression,
                "matched": item.matched, "seconds_to_answer": item.seconds_to_answer,
                "answered_by": item.answered_by.value if item.answered_by else None,
            } for item in self.repository.list_recognition_results(session.id)]
            # Solo la emoción que la persona señaló; el dibujo nunca llega al servidor.
            summary["drawing_results"] = [{
                "step_index": item.step_index, "outcome": item.outcome.value,
                "chosen_expression": item.chosen_expression, "seconds_to_answer": item.seconds_to_answer,
                "answered_by": item.answered_by.value if item.answered_by else None,
            } for item in self.repository.list_drawing_results(session.id)]
            # Solo contadores: no es un puntaje.
            summary["game_results"] = [{
                "step_index": item.step_index, "game_type": item.game_type, "outcome": item.outcome.value,
                "rounds_total": item.rounds_total, "rounds_done": item.rounds_done, "matched": item.matched,
                "first_try": item.first_try, "help_used": item.help_used, "by_conductor": item.by_conductor,
            } for item in self.repository.list_game_results(session.id)]
            # Las repeticiones (intento 2 en adelante), aparte: no cuentan en las métricas.
            summary["repeated_attempts"] = sorted([
                *({"step_index": item.step_index, "attempt": item.attempt, "step_kind": "practice",
                   "target_expression": item.target_expression, "outcome": item.outcome.value,
                   "seconds_to_achieve": item.seconds_to_achieve}
                  for item in self.repository.list_practice_attempts(session.id) if item.attempt > 1),
                *({"step_index": item.step_index, "attempt": item.attempt, "step_kind": "recognition",
                   "target_expression": item.target_expression, "outcome": item.outcome.value,
                   "chosen_expression": item.chosen_expression, "seconds_to_answer": item.seconds_to_answer,
                   "answered_by": item.answered_by.value if item.answered_by else None}
                  for item in self.repository.list_recognition_attempts(session.id) if item.attempt > 1),
                *({"step_index": item.step_index, "attempt": item.attempt, "step_kind": "drawing",
                   "target_expression": None, "outcome": item.outcome.value,
                   "chosen_expression": item.chosen_expression, "seconds_to_answer": item.seconds_to_answer,
                   "answered_by": item.answered_by.value if item.answered_by else None}
                  for item in self.repository.list_drawing_attempts(session.id) if item.attempt > 1),
                *({"step_index": item.step_index, "attempt": item.attempt, "step_kind": "game",
                   "target_expression": None, "outcome": item.outcome.value, "rounds_total": item.rounds_total,
                   "rounds_done": item.rounds_done, "matched": item.matched, "first_try": item.first_try,
                   "help_used": item.help_used}
                  for item in self.repository.list_game_attempts(session.id) if item.attempt > 1),
            ], key=lambda item: (item["step_index"], item["attempt"]))
            summary["verbal_responses"] = [{
                "step_index": item.step_index, "stimulus_id": item.stimulus_id, "text": item.text,
                "recorded_at": item.recorded_at.isoformat(),
            } for item in self.repository.list_verbal(session.id)]
        return summary

    # --- Pantalla de la persona (enlace propio, sin cuenta) ---------------------------

    def _by_token(self, token: str, include_finished: bool = False) -> GuidedRun:
        """Solo una sesión activa; con include_finished, también una estación de
        examen que terminó (para leer el debriefing)."""
        run = self.repository.get_run_by_token_hash(hash_token(token)) if token else None
        if run is None or not (run.active or include_finished):
            raise GuidedNotFound("view")
        return run

    def participant_state(self, token: str) -> dict[str, Any]:
        """Solo lo que se muestra a la persona: nunca expresiones, probabilidades,
        calidad ni notas."""
        run = self._tick(self._by_token(token, include_finished=True))
        session = self._session(run.session_id)
        if not run.active:
            message = EXAM_DEBRIEFING if session.exam_id is not None else "La sesión terminó. Gracias."
            return {"phase": run.phase.value, "message": message, "stimulus": None,
                    "remaining_seconds": None, "capture_frames": False, "frame_interval_ms": FRAME_INTERVAL_MS,
                    "abstract_notice": False, "practice": None, "recognition": None, "drawing": None,
                    "game": None, "accessible": False,
                    "uses_camera": self._camera_active(run, session)}
        stimulus = None
        remaining = None
        abstract = False
        practice = None
        recognition = None
        drawing = None
        game = None
        if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            step = self._protocol(session).steps[run.step_index]
            item = self.stimuli(step.stimulus_id) if step.stimulus_id else None
            # Un identificador de exposición, no el del estímulo, para pedir la imagen.
            # Una práctica sin ilustración no muestra imagen.
            stimulus = ({"exposure": f"{run.step_index}-{int(run.step_started_at.timestamp()) if run.step_started_at else 0}"
                                     + (f"-{run.step_attempt}" if run.step_attempt > 1 else "")}
                        if step.stimulus_id else None)
            remaining = (None if self._unlimited(session, step)
                         else max(0.0, step.seconds_limit - self._seconds(run.step_started_at)))
            abstract = item is not None and item.kind is StimulusKind.ABSTRACT and not step.is_practice
            if step.is_practice:
                practice = self._participant_practice(run, step)
            if step.is_recognition:
                recognition = self._participant_recognition(run, step)
            if step.is_drawing:
                drawing = self._participant_drawing(run)
            if step.is_game:
                game = self._participant_game(run, step)
                # La imagen de la ronda: el identificador cambia con cada ronda.
                stimulus = {"exposure": f"{run.step_index}-{int(run.step_started_at.timestamp())}-{game['round']}"}
        live = self._live.get(run.session_id)
        calibrating = run.phase is GuidedPhase.CALIBRATION and live is not None and live.calibration is not None \
            and live.calibration.state == CALIBRATING
        if session.exam_id is not None:
            # La persona sabe que se la analiza, pero no qué se mide ni en qué momento.
            station_messages = {
                GuidedPhase.WAITING: "Espera un momento: tu docente confirmará el inicio.",
                GuidedPhase.CALIBRATION: ((live.calibration_notice if live and live.calibration_notice else None)
                                          or "Mira a la pantalla unos segundos, con el rostro relajado."),
                GuidedPhase.READY: "Todo listo. El examen empieza cuando tu docente lo indique.",
                GuidedPhase.EXAM: "Examen en curso.",
            }
            return {"phase": run.phase.value, "message": station_messages.get(run.phase), "stimulus": None,
                    "remaining_seconds": None,
                    "capture_frames": calibrating or run.phase is GuidedPhase.EXAM,
                    "frame_interval_ms": FRAME_INTERVAL_MS, "abstract_notice": False, "practice": None,
                    "recognition": None, "drawing": None, "game": None}
        messages = {
            GuidedPhase.PRE_QUESTIONNAIRE: "Primero, unas preguntas.",
            GuidedPhase.CALIBRATION: ("Mira a la pantalla con el rostro relajado." if calibrating
                                      else "En un momento empieza la calibración."),
            GuidedPhase.POST_QUESTIONNAIRE: "Para terminar, unas preguntas.",
            GuidedPhase.READY: "En un momento empezamos.",
            GuidedPhase.LIVE: "Mira a la pantalla con naturalidad.",
        }
        return {
            "phase": run.phase.value,
            "message": messages.get(run.phase),
            "stimulus": stimulus,
            "remaining_seconds": remaining,
            # Un reconocimiento o un dibujo no analiza la cámara: la pantalla no envía cuadros.
            "capture_frames": self._camera_active(run, session) and (
                calibrating or (run.phase in (GuidedPhase.STIMULI, GuidedPhase.LIVE)
                                and recognition is None and drawing is None and game is None)),
            "frame_interval_ms": FRAME_INTERVAL_MS,
            "abstract_notice": abstract,
            "practice": practice,
            "recognition": recognition,
            "drawing": drawing,
            "game": game,
            # Pantalla accesible: algún apoyo que cambia la pantalla.
            "accessible": bool(supports := self._screen_supports(session))
            and (supports["pictograms"] or supports["large_controls"]),
            # Solo los apoyos que cambian la pantalla; nulo si no hay ninguno.
            "supports": supports,
            # Sin cámara, la pantalla no la pide (o deja de pedirla si se siguió sin ella).
            "uses_camera": self._camera_active(run, session),
        }

    def participant_stimulus(self, token: str) -> str:
        """El estímulo que se está mostrando ahora (y solo ese)."""
        run = self._tick(self._by_token(token))
        if run.phase not in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI):
            raise GuidedNotFound("stimulus")
        session = self._session(run.session_id)
        step = self._protocol(session).steps[run.step_index]
        stimulus_id = step.stimulus_id
        if step.is_game:
            stimulus_id = step.game_stimulus_ids[min(self._game_progress(run)["round"], step.rounds - 1)]
        if stimulus_id is None:
            raise GuidedNotFound("stimulus")
        return stimulus_id

    def participant_stop(self, token: str) -> None:
        """El botón visible de la pantalla de la persona: termina de inmediato."""
        self._stop(self._by_token(token), StopReason.PARTICIPANT, None)

    def receive_frame(self, token: str, frame) -> None:
        """Un cuadro de la pantalla de la persona (enlace propio)."""
        self._receive(self._tick(self._by_token(token)), frame)

    # --- Aplicativo móvil: quien conduce y la cámara están en el mismo dispositivo -----

    def conductor_frame(self, user: User, session_id: str, frame) -> dict[str, Any]:
        """Un cuadro enviado por quien conduce la sesión. Sigue el mismo control de
        calidad y modelo local que la pantalla de la persona; la imagen se descarta.
        Devuelve solo la fase y los problemas de calidad, nunca la expresión."""
        run, _ = self._conducted(user, session_id)
        if not run.active:
            raise GuidedConflict("La sesión ya terminó")
        self._receive(self._tick(run), frame)
        run = self._tick(self.repository.get_run(session_id) or run)
        live = self._live.get(session_id)
        return {"phase": run.phase.value,
                "capture_status": [item.value for item in live.pending.issues] if live and live.pending else []}

    def _receive(self, run: GuidedRun, frame) -> None:
        """Analiza un cuadro en memoria (calibración o captura) y lo descarta."""
        if frame is None:
            return
        session = self._session(run.session_id)
        if not self._camera_active(run, session):
            return  # sin cámara: el cuadro se descarta sin analizarlo
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
                run = replace(run, calibrated_at=self.clock())
                if session.exam_id is not None:
                    # Estación calibrada: espera que el docente inicie el examen.
                    live.calibration_notice = None
                    self.repository.save_run(replace(run, phase=GuidedPhase.READY))
                    return
                if session.protocol_id is None:
                    # Sin protocolo: registro periódico desde ahora.
                    run = replace(run, phase=GuidedPhase.LIVE, step_index=0, step_started_at=self.clock(),
                                  next_capture_due=0.0)
                else:
                    run = self._first_step(run, session, self._protocol(session))
                self.repository.save_run(run)
            return
        if run.phase is GuidedPhase.EXAM:
            elapsed = self._seconds(run.step_started_at)
            if run.next_capture_due is None or elapsed < run.next_capture_due:
                return
            # Cada medio segundo se guarda lo que haya, bueno o marcado: sin reintentos.
            self._store_exam_capture(run, session, self._assess(session, frame), run.next_capture_due)
            self.repository.save_run(replace(run, next_capture_due=self._next_slot(elapsed)))
            return
        if run.phase is GuidedPhase.STIMULI:
            step = self._protocol(session).steps[run.step_index]
            if step.is_practice:
                self._practice_frame(run, session, step, frame)
                return
            if step.is_recognition or step.is_drawing or step.is_game:
                return  # un reconocimiento, un dibujo o un juego no analiza la cámara
        if run.phase not in (GuidedPhase.STIMULI, GuidedPhase.LIVE) or run.next_capture_due is None:
            return
        elapsed = self._seconds(run.step_started_at)
        if elapsed < run.next_capture_due:
            return
        protocol = self._protocol(session) if run.phase is GuidedPhase.STIMULI else None
        assessment = self._assess(session, frame)
        if assessment.ok:
            self.repository.save_run(self._store_capture(run, session, protocol, assessment, elapsed,
                                                         timed_out=False))
        elif elapsed >= run.next_capture_due + QUALITY_RETRY_SECONDS:
            # No se logró una captura de buena calidad: se guarda marcada con su problema.
            self.repository.save_run(self._store_capture(run, session, protocol, assessment, elapsed,
                                                         timed_out=True))
        else:
            live.pending = assessment  # se reintenta con el próximo cuadro
