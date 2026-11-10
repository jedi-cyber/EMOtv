"""Protocolos: recetas guardadas que dicen qué aplicar en una sesión
(cuestionario previo, imágenes con sus segundos y cuestionario posterior), para
un público de adultos o de niños.

El protocolo y sus cuestionarios no necesitan aprobación del docente. Uno para
niños solo admite imágenes «Para niños» (leves) y aprobadas; uno para adultos
admite las dos. Una imagen propia pendiente de revisión no se usa en ningún
protocolo. Una versión usada en una sesión no se edita: editarla crea una
versión nueva. Si el docente elimina o reclasifica una imagen que un protocolo
usa, el protocolo queda «Necesita una imagen» hasta que se reemplace.

El docente puede compartir un protocolo suyo con su grupo como plantilla: sus
usuarios lo ven y lo copian como protocolo propio, que editan y aplican. Una
plantilla no se aplica sin copiarla.

Un juego de emparejar no pide imágenes a quien lo arma: al guardar, el servicio
elige una imagen emocional aprobada por ronda (del público del protocolo),
procurando emociones distintas. Al editar se conservan las que siguen sirviendo
y se reemplazan las que no.

En «Busca la misma emoción», cada ronda lleva una imagen modelo, otra de la
misma emoción y una de otra emoción por cada opción restante. Para que se
resuelva por la emoción y no por reconocer la misma imagen, la pareja no puede
ser la misma imagen guardada otra vez (mismo archivo o casi igual de aspecto) y
al menos otra opción se parece más a la modelo que la pareja (colores y
composición). La emoción de cada imagen es la que indicó quien la subió y
aprobó el docente: EMOtv no la comprueba.

Los protocolos de examen simulado no pasan por aquí: no se listan, no se editan
ni se aplican desde el Analizador. Los gestiona ExamService.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import random
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.chat_safety import has_identifier
from emotv.application.practice_validation_service import VALIDATION_PROTOCOL_NAME, is_validation_protocol
from emotv.application.ports.practice_repositories import ProtocolRepository
from emotv.application.questionnaire_service import QuestionnaireNotFound, QuestionnaireService
from emotv.application.stimulus_service import INITIAL_BANK_CATEGORY, StimulusNotFound, StimulusService
from emotv.domain.audit import AuditAction
from emotv.domain.guided_session import RECOGNITION_DISTRACTORS
from emotv.domain.protocol import GAME_SIMILAR, Protocol, ProtocolKind, ProtocolStep, ProtocolSupports
from emotv.domain.role import Role
from emotv.domain.stimulus import Stimulus, StimulusKind, StimulusScope
from emotv.domain.user import User

RESOURCE = "protocol"
DocenteOf = Callable[[str], str | None]
GroupUserIds = Callable[[str], Iterable[str]]
# Aspecto de una imagen (miniatura) para compararla con otra; None si no se lee.
Appearance = Callable[[bytes], tuple[int, ...] | None]
# Diferencia media de aspecto (0 a 255) bajo la cual dos imágenes son la misma
# imagen guardada otra vez. Con el banco inicial: la misma recodificada da menos
# de 1; dos caras con la misma emoción y otro color, 28 o más.
SAME_IMAGE_DISTANCE = 8.0


class ProtocolNotFound(LookupError):
    pass


class ProtocolUnavailable(Exception):
    """El protocolo no se puede usar en esta sesión."""


@dataclass(frozen=True, slots=True)
class ProtocolDraft:
    name: str
    description: str
    for_children: bool
    steps: tuple[ProtocolStep, ...]
    pre_questionnaire_id: str | None = None
    post_questionnaire_id: str | None = None
    accessible: bool = False
    # Si se indica, manda sobre accessible.
    supports: ProtocolSupports | None = None


# Plantilla inicial: «¿Qué emoción es?» con los dibujos del banco inicial, para
# niños y en modo accesible. Se copia a la cuenta y cada quien la modifica.
STARTER_NAME = "Emociones básicas 4 a 6 años"
STARTER_DESCRIPTION = ("Reconocer seis emociones básicas en dibujos sencillos. Cada dibujo muestra dos "
                       "opciones; la persona elige y después escucha el nombre de la emoción.")
STARTER_EXPRESSIONS = ("happiness", "sadness", "anger", "fear", "surprise", "disgust")
STARTER_SECONDS = 30
STARTER_OPTIONS = 2


class ProtocolService:
    def __init__(
        self,
        repository: ProtocolRepository,
        stimuli: StimulusService,
        audit: AuditService,
        docente_of: DocenteOf,
        group_user_ids: GroupUserIds,
        questionnaires: QuestionnaireService | None = None,
        clock: Callable[[], datetime] | None = None,
        validation_usable: Callable[[Protocol], bool] | None = None,
        appearance: Appearance | None = None,
    ) -> None:
        self.repository = repository
        # Sin él no se puede comprobar «Busca la misma emoción» y no se guarda.
        self.appearance = appearance
        # El protocolo «Validación con adultos» solo se aplica en modo demo y con
        # cuentas de voluntarios (PracticeValidationService.usable).
        self.validation_usable = validation_usable or (lambda protocol: False)
        self.stimuli = stimuli
        self.audit = audit
        self.docente_of = docente_of
        self.group_user_ids = group_user_ids
        # Sin cuestionarios configurados no se acepta ninguno.
        self.questionnaires = questionnaires
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso --------------------------------------------------------------

    @staticmethod
    def _require_conductor(user: User) -> None:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("Los protocolos los arman usuarios y docentes")

    def _shared_by(self, user: User) -> tuple[str, ...]:
        """Docente cuyas plantillas ve la cuenta."""
        if user.role is Role.STUDENT:
            docente = self.docente_of(user.id)
            return (docente,) if docente else ()
        return ()

    def can_view(self, user: User, protocol: Protocol) -> bool:
        """Quien lo armó, el docente de esa cuenta y, si es una plantilla, los
        usuarios del grupo de su docente. Un examen no es un protocolo de práctica."""
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            return False
        if protocol.kind is not ProtocolKind.PRACTICE:
            return False
        if protocol.owner_user_id == user.id:
            return True
        if protocol.shared_with_group and protocol.owner_user_id in self._shared_by(user):
            return True
        return user.role is Role.PSYCHOLOGIST and self.docente_of(protocol.owner_user_id) == user.id

    def list_for(self, user: User) -> tuple[Protocol, ...]:
        self._require_conductor(user)
        owners = ((user.id, *self._shared_by(user)) if user.role is Role.STUDENT
                  else (user.id, *self.group_user_ids(user.id)))
        return tuple(item for item in self.repository.list_current(owners) if self.can_view(user, item))

    def get(self, user: User, protocol_id: str) -> Protocol:
        protocol = self.repository.get(protocol_id)
        if protocol is None or not self.can_view(user, protocol):
            raise ProtocolNotFound(protocol_id)
        return protocol

    def is_used(self, protocol: Protocol) -> bool:
        return self.repository.is_used(protocol.id)

    def _image_problem(self, protocol: Protocol, stimulus: Stimulus | None) -> str | None:
        """Por qué una imagen no sirve en este protocolo, o None si sirve."""
        if stimulus is None or stimulus.deleted_at is not None:
            return "Una imagen del protocolo fue eliminada"
        if stimulus.kind is StimulusKind.ABSTRACT and not self.stimuli.abstract_enabled:
            return f"Las imágenes abstractas ya no se aplican: reemplaza «{stimulus.title}»"
        if stimulus.scope is StimulusScope.USER and stimulus.owner_user_id != protocol.owner_user_id:
            return "Una imagen propia solo se usa en los protocolos de quien la subió"
        if stimulus.pending:
            return f"La imagen «{stimulus.title}» todavía está en revisión"
        if not stimulus.usable:
            return f"El estímulo «{stimulus.title}» fue retirado del banco"
        if protocol.for_children and not stimulus.suitable_for_children:
            return (f"Un protocolo para niños solo admite imágenes leves y aprobadas «Para niños»: "
                    f"«{stimulus.title}» no lo es")
        return None

    def needs_image(self, protocol: Protocol) -> bool:
        """Algún paso nombra una imagen eliminada, sin aprobar, retirada o que ya
        no corresponde al público del protocolo."""
        return any(self._image_problem(protocol, self.stimuli.repository.get(stimulus_id)) is not None
                   for step in protocol.steps for stimulus_id in step.image_ids)

    def _game_images(self, user: User, target: Protocol, step: ProtocolStep) -> ProtocolStep:
        if step.game_type == GAME_SIMILAR:
            return self._similar_images(user, target, step)
        return self._matching_images(user, target, step)

    def _game_fits(self, target: Protocol, item: Stimulus | None) -> bool:
        return (item is not None and item.kind is StimulusKind.EMOTIONAL
                and item.expected_expression in RECOGNITION_DISTRACTORS
                and self._image_problem(target, item) is None)

    def _similar_images(self, user: User, target: Protocol, step: ProtocolStep) -> ProtocolStep:
        """Por ronda: la modelo, la pareja (misma emoción, otro aspecto) y una de
        otra emoción por opción restante, distintas entre sí. Conserva las
        guardadas si todas siguen sirviendo; si no, las elige de nuevo."""
        if self.appearance is None:
            raise ValueError("Este servidor no puede comprobar las imágenes de «Busca la misma emoción»")
        looks: dict[str, tuple[str, tuple[int, ...] | None]] = {}

        def look(item: Stimulus) -> tuple[str, tuple[int, ...] | None]:
            if item.id not in looks:
                _, data = self.stimuli.image(user, item.id)
                looks[item.id] = (hashlib.sha256(data).hexdigest(), self.appearance(data))
            return looks[item.id]

        def distance(a: Stimulus, b: Stimulus) -> float | None:
            (hash_a, look_a), (hash_b, look_b) = look(a), look(b)
            if hash_a == hash_b:
                return 0.0
            if look_a is None or look_b is None or len(look_a) != len(look_b):
                return None
            return sum(abs(x - y) for x, y in zip(look_a, look_b)) / len(look_a)

        def round_ok(model: Stimulus, match: Stimulus, others: list[Stimulus]) -> bool:
            expressions = [item.expected_expression for item in others]
            if (match.id == model.id or match.expected_expression != model.expected_expression
                    or model.expected_expression in expressions or len(set(expressions)) != len(expressions)
                    or len({model.id, match.id, *(item.id for item in others)}) != len(others) + 2):
                return False
            apart = distance(model, match)
            if apart is None or apart < SAME_IMAGE_DISTANCE:
                return False  # La misma imagen otra vez, o no se pudo comparar.
            near = [distance(model, item) for item in others]
            # Otra opción se parece más a la modelo: el aspecto no lleva a la respuesta.
            return all(value is not None for value in near) and min(near) < apart

        size = step.images_per_round
        stored: list[Stimulus | None] = []
        for stimulus_id in step.game_stimulus_ids:
            try:
                item = self.stimuli.get(user, stimulus_id)
            except StimulusNotFound:
                item = None
            stored.append(item if self._game_fits(target, item) else None)
        if len(stored) == step.rounds * size and all(stored):
            blocks = [stored[index:index + size] for index in range(0, len(stored), size)]
            if all(round_ok(block[0], block[1], list(block[2:])) for block in blocks):
                return step

        chooser = random.Random()
        pool: defaultdict[str, list[Stimulus]] = defaultdict(list)
        for item in self.stimuli.list_for(user, target.for_children):
            if self._game_fits(target, item):
                pool[item.expected_expression].append(item)
        for items in pool.values():
            chooser.shuffle(items)
        used: set[str] = set()
        counts: Counter[str] = Counter()
        chosen: list[str] = []
        for _ in range(step.rounds):
            found = None
            for expression in sorted(pool, key=lambda key: (counts[key], chooser.random())):
                for model in pool[expression]:
                    if model.id in used:
                        continue
                    # Pareja: la de la misma emoción que menos se parece a la modelo.
                    matches = sorted((item for item in pool[expression] if item.id not in used | {model.id}),
                                     key=lambda item: -(distance(model, item) or 0.0))
                    # Otras opciones: de cada otra emoción, la que más se parece a la modelo.
                    others = []
                    for other in sorted(key for key in pool if key != expression):
                        candidates = [item for item in pool[other] if distance(model, item) is not None]
                        if candidates:
                            others.append(min(candidates, key=lambda item: distance(model, item)))
                    others.sort(key=lambda item: distance(model, item))
                    others = others[:step.option_count - 1]
                    if len(others) < step.option_count - 1:
                        continue
                    match = next((item for item in matches if round_ok(model, item, others)), None)
                    if match is not None:
                        found = (model, match, others)
                        break
                if found:
                    break
            if found is None:
                break
            model, match, others = found
            used |= {model.id, match.id}
            counts[model.expected_expression] += 1
            chosen.extend([model.id, match.id, *(item.id for item in others)])
        if len(chosen) < step.rounds * size:
            audience = " «Para niños»" if target.for_children else ""
            done = len(chosen) // size
            raise ValueError(
                f"«Busca la misma emoción» necesita, en cada una de sus {step.rounds} rondas, dos imágenes "
                f"emocionales aprobadas{audience} de la misma emoción que se vean distintas (otra cara, otros "
                f"colores) y {step.option_count - 1} de otras emociones; el banco alcanza para {done}. "
                "Agrega imágenes al banco, baja las rondas o las opciones")
        return replace(step, game_stimulus_ids=tuple(chosen))

    def _matching_images(self, user: User, target: Protocol, step: ProtocolStep) -> ProtocolStep:
        """Una imagen emocional aprobada por ronda. Conserva las indicadas que
        sirven y completa con otras del banco, primero de emociones que todavía no
        aparecen."""
        def fits(item: Stimulus | None) -> bool:
            return (item is not None and item.kind is StimulusKind.EMOTIONAL
                    and item.expected_expression in RECOGNITION_DISTRACTORS
                    and self._image_problem(target, item) is None)

        kept: list[Stimulus] = []
        for stimulus_id in step.game_stimulus_ids:
            try:
                item = self.stimuli.get(user, stimulus_id)
            except StimulusNotFound:
                continue
            if fits(item) and all(other.id != item.id for other in kept) and len(kept) < step.rounds:
                kept.append(item)
        chooser = random.Random()
        counts = Counter(item.expected_expression for item in kept)
        pool: defaultdict[str, list[Stimulus]] = defaultdict(list)
        for item in self.stimuli.list_for(user, target.for_children):
            if fits(item) and all(other.id != item.id for other in kept):
                pool[item.expected_expression].append(item)
        for items in pool.values():
            chooser.shuffle(items)
        while len(kept) < step.rounds and any(pool.values()):
            expression = min((key for key, items in pool.items() if items),
                             key=lambda key: (counts[key], chooser.random()))
            kept.append(pool[expression].pop())
            counts[expression] += 1
        if len(kept) < step.rounds:
            audience = " «Para niños»" if target.for_children else ""
            raise ValueError(f"El juego necesita {step.rounds} imágenes emocionales aprobadas{audience} y hay "
                             f"{len(kept)}: agrega imágenes al banco o baja las rondas")
        return replace(step, game_stimulus_ids=tuple(item.id for item in kept))

    # --- Armado y versiones --------------------------------------------------

    def _validate(self, user: User, draft: ProtocolDraft) -> ProtocolDraft:
        """Comprueba el borrador y lo devuelve con la respuesta correcta de cada
        reconocimiento: la expresión esperada de su imagen."""
        target = Protocol(id="validacion", family_id="validacion", version=1, owner_user_id=user.id,
                          name=draft.name or "validacion", description=draft.description,
                          for_children=draft.for_children, created_at=self.clock(), steps=draft.steps)
        for questionnaire_id in (draft.pre_questionnaire_id, draft.post_questionnaire_id):
            if questionnaire_id is None:
                continue
            try:
                if self.questionnaires is None:
                    raise QuestionnaireNotFound(questionnaire_id)
                self.questionnaires.get(user, questionnaire_id)
            except QuestionnaireNotFound as error:
                raise ValueError("Un cuestionario indicado no existe o no está disponible") from error
        steps = []
        for step in draft.steps:
            if step.is_game:
                steps.append(self._game_images(user, target, step))
                continue
            if step.stimulus_id is None:
                steps.append(step)
                continue  # Ejercicio de práctica sin ilustración.
            try:
                stimulus = self.stimuli.get(user, step.stimulus_id)
            except StimulusNotFound as error:
                raise ValueError("Un estímulo del protocolo no existe o no está disponible") from error
            problem = self._image_problem(target, stimulus)
            if problem is not None:
                raise ValueError(problem)
            if step.record_verbal_response and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Lo que la persona dice ver solo se registra en imágenes abstractas")
            if step.shown_before_analyzer and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Solo las imágenes abstractas se muestran antes del analizador")
            if step.situation is not None and has_identifier(step.situation):
                raise ValueError("La situación no puede incluir DNI, correos ni teléfonos: usa nombres inventados")
            if step.is_recognition:
                if stimulus.kind is not StimulusKind.EMOTIONAL or stimulus.expected_expression is None:
                    raise ValueError(f"Un reconocimiento usa una imagen emocional con su expresión esperada: "
                                     f"«{stimulus.title}» no la tiene")
                step = replace(step, target_expression=stimulus.expected_expression)
            if step.imitate:
                if stimulus.kind is not StimulusKind.EMOTIONAL or stimulus.expected_expression is None:
                    raise ValueError(f"«Haz la misma cara» usa una imagen emocional con su expresión esperada: "
                                     f"«{stimulus.title}» no la tiene")
                step = replace(step, target_expression=stimulus.expected_expression)
            steps.append(step)
        return replace(draft, steps=tuple(steps))

    @staticmethod
    def _reserved_name(name: str) -> None:
        if name.strip().casefold() == VALIDATION_PROTOCOL_NAME.casefold():
            raise ValueError(f"El nombre «{VALIDATION_PROTOCOL_NAME}» está reservado para el protocolo de validación")

    def create(self, user: User, draft: ProtocolDraft) -> Protocol:
        self._require_conductor(user)
        self._reserved_name(draft.name)
        draft = self._validate(user, draft)
        family = str(uuid4())
        protocol = self.repository.add(Protocol(
            id=family, family_id=family, version=1, owner_user_id=user.id, name=draft.name,
            description=draft.description, for_children=draft.for_children, created_at=self.clock(),
            steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id,
            post_questionnaire_id=draft.post_questionnaire_id, accessible=draft.accessible,
            supports=draft.supports))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, protocol.id)
        return protocol

    def edit(self, user: User, protocol_id: str, draft: ProtocolDraft) -> Protocol:
        """Una versión sin usar se reemplaza; una usada en una sesión no se
        toca y se crea la siguiente."""
        self._require_conductor(user)
        current = self.get(user, protocol_id)
        if current.owner_user_id != user.id:
            raise PermissionError("Solo quien armó el protocolo puede editarlo")
        if not current.current:
            raise ValueError("Esta versión ya fue reemplazada: edita la versión vigente")
        if not is_validation_protocol(current):
            self._reserved_name(draft.name)
        elif draft.name.strip().casefold() != VALIDATION_PROTOCOL_NAME.casefold():
            raise ValueError("El protocolo de validación conserva su nombre")
        draft = self._validate(user, draft)
        fields = dict(name=draft.name, description=draft.description, for_children=draft.for_children,
                      steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id,
                      post_questionnaire_id=draft.post_questionnaire_id, accessible=draft.accessible,
                      supports=draft.supports, approved_at=None, approved_by_user_id=None)
        if self.repository.is_used(current.id):
            now = self.clock()
            updated = self.repository.add_version(current.id, now, replace(
                current, id=str(uuid4()), version=current.version + 1, created_at=now, **fields))
        else:
            updated = self.repository.replace(replace(current, **fields))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, updated.id)
        return updated

    def share(self, user: User, protocol_id: str, shared: bool) -> Protocol:
        """El docente ofrece un protocolo suyo como plantilla a su grupo."""
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("Solo el docente comparte protocolos con su grupo")
        protocol = self.get(user, protocol_id)
        if protocol.owner_user_id != user.id or not protocol.current:
            raise PermissionError("Comparte la versión vigente de un protocolo tuyo")
        if protocol.shared_with_group == shared:
            return protocol
        updated = self.repository.replace(replace(protocol, shared_with_group=shared))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, protocol.id)
        return updated

    def copy(self, user: User, protocol_id: str) -> Protocol:
        """Copia propia y editable de un protocolo propio o de una plantilla del
        docente. La copia no se comparte. Un cuestionario que la cuenta no puede
        usar (el docente no lo comparte) no se copia."""
        self._require_conductor(user)
        source = self.get(user, protocol_id)
        if source.owner_user_id != user.id and not source.shared_with_group:
            raise PermissionError("Solo se copian los protocolos propios o las plantillas de tu docente")

        def usable(questionnaire_id: str | None) -> str | None:
            if questionnaire_id is None or self.questionnaires is None:
                return None
            try:
                self.questionnaires.get(user, questionnaire_id)
            except QuestionnaireNotFound:
                return None
            return questionnaire_id

        pre = usable(source.pre_questionnaire_id)
        # Las imágenes de un juego se vuelven a elegir entre las que ve la cuenta.
        steps = tuple(replace(step, game_stimulus_ids=()) if step.is_game else step for step in source.steps)
        return self.create(user, ProtocolDraft(
            name=source.name, description=source.description, for_children=source.for_children, steps=steps,
            pre_questionnaire_id=pre, post_questionnaire_id=usable(source.post_questionnaire_id) if pre else None,
            accessible=source.accessible, supports=source.supports))

    def create_starter(self, user: User) -> Protocol:
        """Copia a la cuenta la plantilla «Emociones básicas 4 a 6 años», armada con
        el primer dibujo vigente de cada emoción del banco inicial."""
        self._require_conductor(user)
        drawings: dict[str, Stimulus] = {}
        for item in sorted(self.stimuli.list_for(user, for_children=True), key=lambda item: item.title):
            if (item.scope is StimulusScope.INSTITUTION and item.category == INITIAL_BANK_CATEGORY
                    and item.expected_expression in STARTER_EXPRESSIONS):
                drawings.setdefault(item.expected_expression, item)
        if not drawings:
            raise ValueError("La plantilla usa el banco inicial de dibujos, que todavía no está en EMOtv: "
                             "pídele al administrador que lo agregue en «Estímulos institucionales»")
        steps = tuple(ProtocolStep.recognition(drawings[expression].id, STARTER_SECONDS, STARTER_OPTIONS)
                      for expression in STARTER_EXPRESSIONS if expression in drawings)
        return self.create(user, ProtocolDraft(name=STARTER_NAME, description=STARTER_DESCRIPTION,
                                               for_children=True, steps=steps, accessible=True))

    # --- Uso en una sesión ---------------------------------------------------

    def require_usable(self, user: User, protocol_id: str) -> Protocol:
        """Comprueba que quien conduce puede aplicar esta versión ahora. El
        público de la sesión es el del protocolo."""
        protocol = self.get(user, protocol_id)
        if protocol.owner_user_id != user.id:
            raise ProtocolUnavailable("Solo se aplican los protocolos que armaste")
        if not protocol.current:
            raise ProtocolUnavailable("Hay una versión más nueva de este protocolo")
        if is_validation_protocol(protocol) and not self.validation_usable(protocol):
            raise ProtocolUnavailable("El protocolo de validación solo se aplica en modo demo, con una cuenta "
                                      "de voluntario")
        for stimulus_id in (item for step in protocol.steps for item in step.image_ids):
            try:
                stimulus = self.stimuli.get(user, stimulus_id)
            except StimulusNotFound as error:
                raise ProtocolUnavailable("El protocolo necesita una imagen: una de sus imágenes ya no "
                                          "está disponible") from error
            problem = self._image_problem(protocol, stimulus)
            if problem is not None:
                raise ProtocolUnavailable(f"El protocolo necesita una imagen. {problem}")
        return protocol
