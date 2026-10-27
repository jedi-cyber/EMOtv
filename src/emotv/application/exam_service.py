"""Examen simulado: lo crea un docente con un clic, confirma de una vez los
consentimientos firmados de las estaciones unidas, lo inicia y lo termina.

El docente no configura nada más: el protocolo «Examen simulado» se crea solo
la primera vez y el código de unión lo genera EMOtv. Cada estación es una
sesión individual del examen; el consentimiento se registra en cada una. Una
estación que se une después de la confirmación espera una nueva. El docente
solo ve el estado de cada estación por su código, nunca imágenes ni
expresiones en vivo.

Una estación se une con el código del examen, sin cuenta: recibe el enlace de
su pantalla y el código de su sesión, que se anota en el consentimiento firmado.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
import secrets
from typing import Any, Protocol as Interface
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.commitment_service import CommitmentService
from emotv.application.ports.exam_repository import ExamRepository
from emotv.application.ports.practice_repositories import ProtocolRepository
from emotv.application.session_service import CODE_ALPHABET, SessionService
from emotv.domain.audit import AuditAction
from emotv.domain.exam import JOIN_CODE_LENGTH, Exam, ExamState
from emotv.domain.protocol import Protocol, ProtocolKind
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.session_type import SessionType
from emotv.domain.user import User

RESOURCE = "exam"
STATION_RESOURCE = "exam_station"
EXAM_PROTOCOL_NAME = "Examen simulado"
MAX_STATIONS = 40   # el piloto usa entre cuatro y ocho; el límite frena uniones masivas


class StationRuns(Interface):
    """La pantalla de cada estación (GuidedSessionService)."""

    def create_station(self, session: EmotionalSession) -> str: ...
    def station_phase(self, session_id: str) -> str | None: ...
    def close_station(self, session_id: str) -> None: ...


def random_exam_code() -> str:
    """Código que cada estación escribe para unirse, p. ej. K7Q2MX."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


class ExamNotFound(LookupError):
    pass


class ExamConflict(Exception):
    """La acción no corresponde al estado actual del examen."""


class ExamService:
    def __init__(
        self,
        repository: ExamRepository,
        protocols: ProtocolRepository,
        sessions: SessionService,
        audit: AuditService,
        commitments: CommitmentService | None = None,
        clock: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = random_exam_code,
        stations: StationRuns | None = None,
    ) -> None:
        self.repository = repository
        self.protocols = protocols
        self.sessions = sessions
        self.audit = audit
        self.commitments = commitments
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.code_factory = code_factory
        # Sin la sesión guiada (falta la clave de cifrado) las estaciones no se unen.
        self.stations = stations

    # --- Acceso --------------------------------------------------------------

    @staticmethod
    def _require_docente(user: User) -> None:
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("Los exámenes los crea y conduce un docente")

    def _owned(self, user: User, exam_id: str) -> Exam:
        self._require_docente(user)
        exam = self.repository.get(exam_id)
        if exam is None or exam.owner_user_id != user.id:
            raise ExamNotFound(exam_id)
        return exam

    # --- Creación ------------------------------------------------------------

    def _exam_protocol(self, user: User) -> Protocol:
        """El protocolo de examen del docente; se crea solo la primera vez."""
        for protocol in self.protocols.list_current((user.id,)):
            if protocol.kind is ProtocolKind.EXAM and protocol.owner_user_id == user.id:
                return protocol
        family = str(uuid4())
        return self.protocols.add(Protocol(
            id=family, family_id=family, version=1, owner_user_id=user.id, name=EXAM_PROTOCOL_NAME,
            description="EMOtv registra todo el examen; no hay pasos que configurar.", for_children=False,
            created_at=self.clock(), kind=ProtocolKind.EXAM))

    def _next_code(self) -> str:
        for _ in range(100):
            code = self.code_factory()
            if not self.repository.join_code_exists(code):
                return code
        raise RuntimeError("No se pudo generar un código de examen único")

    def create(self, user: User) -> Exam:
        self._require_docente(user)
        if self.commitments is not None:
            self.commitments.require(user)
        exam = self.repository.save(Exam(
            id=str(uuid4()), owner_user_id=user.id, protocol_id=self._exam_protocol(user).id,
            join_code=self._next_code(), created_at=self.clock()))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, exam.id)
        return exam

    # --- Consulta ------------------------------------------------------------

    def list_for(self, user: User) -> tuple[dict[str, Any], ...]:
        self._require_docente(user)
        return tuple(self._summary(exam, self.repository.list_sessions(exam.id))
                     for exam in self.repository.list_by_owner(user.id))

    def detail(self, user: User, exam_id: str) -> dict[str, Any]:
        exam = self._owned(user, exam_id)
        stations = self.repository.list_sessions(exam.id)
        return {**self._summary(exam, stations), "stations": [self._station(item) for item in stations]}

    def _station(self, session: EmotionalSession) -> dict[str, Any]:
        """Solo el estado de la estación: ni imágenes ni expresiones."""
        return {
            "code": session.code,
            "joined_at": session.started_at.isoformat(),
            "consent_confirmed": session.authorization_confirmed_at is not None,
            "phase": self.stations.station_phase(session.id) if self.stations else None,
            "finished": session.is_terminal,
        }

    # --- Estación ------------------------------------------------------------

    def join(self, join_code: str) -> dict[str, str]:
        """Una estación se une con el código del examen (sin cuenta). Espera el
        consentimiento: hasta entonces no se analiza ningún cuadro."""
        if self.stations is None:
            raise RuntimeError("Las estaciones no están disponibles: falta la clave de cifrado de datos sensibles")
        exam = self.repository.get_by_join_code(join_code)
        if exam is None or not exam.accepts_stations:
            raise ExamNotFound("join")
        if len(self.repository.list_sessions(exam.id)) >= MAX_STATIONS:
            raise ExamConflict(f"El examen ya tiene {MAX_STATIONS} estaciones")
        session = self.sessions.start_session(
            session_type=SessionType.ADULT, owner_user_id=exam.owner_user_id, protocol_id=exam.protocol_id,
            exam_id=exam.id)
        token = self.stations.create_station(session)
        self.audit.record(None, AuditAction.CREATE, STATION_RESOURCE, session.id)
        return {"view_token": token, "session_code": session.code}

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _summary(self, exam: Exam, stations: tuple[EmotionalSession, ...]) -> dict[str, Any]:
        waiting = sum(1 for item in stations if item.authorization_confirmed_at is None and not item.is_terminal)
        return {
            "id": exam.id,
            "join_code": exam.join_code,
            "state": exam.state.value,
            "created_at": exam.created_at.isoformat(),
            "consent_confirmed_at": self._iso(exam.consent_confirmed_at),
            "started_at": self._iso(exam.started_at),
            "closed_at": self._iso(exam.closed_at),
            "station_count": len(stations),
            "waiting_consent": waiting,
        }

    # --- Pasos del docente ---------------------------------------------------

    def confirm_consents(self, user: User, exam_id: str) -> int:
        """«Recibí los consentimientos de todos»: registra el consentimiento de
        cada estación unida que lo esperaba. Devuelve cuántas se confirmaron."""
        exam = self._owned(user, exam_id)
        if exam.state is ExamState.CLOSED:
            raise ExamConflict("El examen ya terminó")
        pending = [item for item in self.repository.list_sessions(exam.id)
                   if item.authorization_confirmed_at is None and not item.is_terminal]
        if not pending:
            raise ExamConflict("Ninguna estación espera la confirmación del consentimiento")
        for session in pending:
            self.sessions.confirm_authorization(session.id)
        self.repository.save(replace(exam, consent_confirmed_at=self.clock()))
        self.audit.record(user, AuditAction.AUTHORIZATION_CHANGE, RESOURCE, exam.id)
        return len(pending)

    def start(self, user: User, exam_id: str) -> Exam:
        exam = self._owned(user, exam_id)
        if exam.state is not ExamState.OPEN:
            raise ExamConflict("El examen ya se inició" if exam.state is ExamState.IN_PROGRESS
                               else "El examen ya terminó")
        stations = self.repository.list_sessions(exam.id)
        if not any(item.authorization_confirmed_at is not None for item in stations):
            raise ExamConflict("Confirma los consentimientos de las estaciones antes de iniciar")
        started = self.repository.save(replace(exam, state=ExamState.IN_PROGRESS, started_at=self.clock()))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, exam.id)
        return started

    def finish(self, user: User, exam_id: str) -> Exam:
        exam = self._owned(user, exam_id)
        if exam.state is ExamState.CLOSED:
            raise ExamConflict("El examen ya terminó")
        closed = self.repository.save(replace(exam, state=ExamState.CLOSED, closed_at=self.clock()))
        # Cada estación termina y muestra el debriefing.
        if self.stations is not None:
            for session in self.repository.list_sessions(exam.id):
                self.stations.close_station(session.id)
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, exam.id)
        return closed
