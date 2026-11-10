export interface Activity {
  id: string;
  name: string;
  description: string;
  required_posture: string;
  duration_seconds: number;
  repetitions: number;
  steps?: ActivityStep[];
}

export interface ActivityStep {
  posture: string;
  instruction: string;
  duration_seconds: number;
}

export interface Student {
  id: string;
  user_id: string;
  student_code: string;
}

export interface AssignedStudent extends Student {
  assigned_at: string;
}

export type SessionState = "created" | "in_progress" | "recognized" | "completed" | "cancelled";
export type ActivityOutcome = "completed" | "skipped" | "cancelled";
/** Con quién es la sesión: conmigo, con una persona adulta o con un niño o niña. */
export type SessionType = "propia" | "adulto" | "infantil";

export interface EmotionalSession {
  id: string;
  state: SessionState;
  student_id: string | null;
  started_at: string;
  completed_at: string | null;
  initial_emotion: string | null;
  emotion_confidence: number | null;
  activity_id: string | null;
  exercise_result: string | null;
  exercise_duration_seconds: number | null;
  emotion_model_id: string | null;
  emotion_model_version: string | null;
  recognized_at?: string | null;
  exercise_steps_completed?: number | null;
  exercise_steps_total?: number | null;
  exercise_repetitions?: number | null;
  session_type?: SessionType;
  /** Cuenta que conduce la sesión; solo ella puede cancelarla. */
  owner_user_id?: string | null;
  protocol_id?: string | null;
  /** Versiones exactas de los cuestionarios previo y posterior. */
  pre_questionnaire_id?: string | null;
  post_questionnaire_id?: string | null;
  /** Código aleatorio (S-XXXXXX) que se anota en el formato firmado. */
  code?: string | null;
  authorization_confirmed_at?: string | null;
  deletion_requested_at?: string | null;
}

/** Modelo local que puede probar quien conduce la sesión (GET /analysis/models). */
export interface LocalModelOption {
  model_id: string;
  state: "SUPPORTED" | "WARNING" | "BLOCKED";
  is_default: boolean;
  reasons?: string[];
}

export type StimulusKind = "emotional" | "abstract";
export type StimulusIntensity = "mild" | "moderate";
/** «Para niños» sirve con niños y con adultos; «Para adultos», solo con adultos. */
export type ImageAudience = "children" | "adults";

/** Imagen del banco de estímulos; nunca una foto de una persona evaluada. */
export interface Stimulus {
  id: string;
  title: string;
  kind: StimulusKind;
  category: string;
  expected_expression: string | null;
  intensity: StimulusIntensity;
  min_age: number;
  origin: string;
  license: string;
  scope: "group" | "institution" | "user";
  audience: ImageAudience;
  created_at: string;
  approved: boolean;
  active: boolean;
  can_manage: boolean;
}

export type StepKind = "stimulus" | "practice" | "recognition" | "drawing" | "game";

export interface ProtocolStep {
  /** «practice»: se pide una expresión y se sostiene; la imagen es una ilustración opcional.
   * «recognition»: se muestra una imagen emocional y la persona elige qué emoción es.
   * «drawing»: la persona dibuja una cara y señala qué emoción quiso representar.
   * «game»: juego de emparejar cada imagen con el nombre de su emoción. */
  kind?: StepKind;
  stimulus_id: string | null;
  exposure_seconds: number;
  capture_after_seconds: number;
  record_verbal_response: boolean;
  /** Solo imágenes abstractas: se muestran antes de la calibración, sin capturas. */
  shown_before_analyzer: boolean;
  /** En un reconocimiento la pone el servidor: la expresión esperada de la imagen. */
  target_expression?: string | null;
  hold_seconds?: number | null;
  /** Solo un reconocimiento: cuántas opciones se muestran (2 a 4). */
  option_count?: number | null;
  /** Solo un reconocimiento: historia corta; la pregunta pasa a «¿Qué emoción muestra la cara?». */
  situation?: string | null;
  /** Solo una práctica con imagen: la imagen es el modelo («Haz la misma cara»)
   * y la expresión pedida la pone el servidor, la de la imagen. */
  imitate?: boolean;
  /** Solo un juego: tipo, rondas e imagen de cada ronda (las elige el servidor). */
  game_type?: GameType | null;
  rounds?: number | null;
  game_stimulus_ids?: string[];
}

/** Pausa tras cada reconocimiento o ejercicio: normal, el doble o hasta «Seguir». */
export type PauseMode = "normal" | "long" | "wait";

/** Apoyos de la pantalla de la persona, por protocolo. */
export interface ProtocolSupports {
  pictograms: boolean;
  large_controls: boolean;
  read_aloud: boolean;
  no_time_limit: boolean;
  pause: PauseMode;
}

export interface Protocol {
  id: string;
  family_id: string;
  version: number;
  name: string;
  description: string;
  for_children: boolean;
  /** Tiene algún apoyo (el modo accesible de antes es un preajuste). */
  accessible?: boolean;
  supports?: ProtocolSupports;
  pre_questionnaire_id: string | null;
  post_questionnaire_id: string | null;
  steps: ProtocolStep[];
  created_at: string;
  owned_by_me: boolean;
  /** Plantilla que el docente comparte con su grupo; sus usuarios la copian. */
  shared_with_group?: boolean;
  used: boolean;
  /** Una imagen fue eliminada o reclasificada por el docente: hay que reemplazarla. */
  needs_image: boolean;
  /** Falso si todos sus pasos son reconocimientos: la sesión no pide la cámara. Si falta, se asume verdadero. */
  uses_camera?: boolean;
}

/** Imagen propia de un usuario: pendiente («En revisión») hasta que su docente la revisa. */
export interface UserImage {
  id: string;
  title: string;
  origin: string;
  audience: ImageAudience;
  status: "pending" | "approved";
  possible_person: boolean;
  batch_id: string | null;
  created_at: string;
  expires_at: string | null;
  uploaded_by: string | null;
}

export interface ImageUploadResult {
  batch_id: string;
  results: { title: string; accepted: boolean; message: string | null; image: UserImage | null }[];
}

export interface ImageReviewBatch {
  batch_id: string;
  uploaded_by: string;
  uploaded_at: string;
  images: UserImage[];
}

export interface ImageReview {
  pending: ImageReviewBatch[];
  approved: UserImage[];
}

export interface UserNotice {
  id: string;
  message: string;
  created_at: string;
}

/** Acta de eliminación de una sesión: sin datos personales. */
export interface DeletionCertificate {
  id: string;
  session_code: string;
  deleted_at: string;
  counts: Record<string, number>;
  verified: boolean;
}

export interface AuditEntry {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  actor_role: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: "success" | "denied" | "failure";
}

export type QuestionKind = "scale" | "single_choice" | "multiple_choice" | "short_text" | "faces";

export interface Question {
  id: string;
  kind: QuestionKind;
  text: string;
  required: boolean;
  options: string[];
  scale_points: number | null;
  min_label: string | null;
  max_label: string | null;
}

/** Cuestionario creado por quien conduce la sesión. EMOtv no lo valida ni lo puntúa. */
export interface Questionnaire {
  id: string;
  family_id: string;
  version: number;
  title: string;
  instructions: string;
  questions: Question[];
  created_at: string;
  shared_with_group: boolean;
  owned_by_me: boolean;
  used: boolean;
}

export type AnswerValue = number | string | string[];
export type Answers = Record<string, AnswerValue>;
export type QuestionnaireMoment = "pre" | "post";

/** Respuestas tal como se dieron, con la versión exacta del cuestionario. */
export interface QuestionnaireAnswers {
  id: string;
  moment: QuestionnaireMoment;
  entry_mode: "participant" | "conductor";
  submitted_at: string;
  questionnaire: Questionnaire;
  answers: Answers;
}

export type GuidedPhase = "pre_questionnaire" | "before_analyzer" | "calibration" | "stimuli"
  | "post_questionnaire" | "live" | "waiting" | "ready" | "exam" | "finished" | "stopped";
export type MarkerKind = "distracted" | "laughed" | "asked_to_stop" | "cried" | "note";

export interface GuidedStep {
  index: number;
  stimulus_id: string | null;
  title: string;
  kind: "emotional" | "abstract" | "";
  exposure_seconds: number;
  capture_after_seconds: number;
  record_verbal_response: boolean;
  shown_before_analyzer: boolean;
  step_kind?: StepKind;
  target_expression?: string | null;
  hold_seconds?: number | null;
  option_count?: number | null;
  imitate?: boolean;
}

/** Ejercicio en curso para quien conduce: la expresión pedida y el nivel en vivo. */
export interface GuidedPractice {
  target_expression: string;
  hold_seconds: number;
  imitate?: boolean;
  level: number | null;
  achieved: boolean;
}

export interface GuidedPracticeResult {
  step_index: number;
  target_expression: string;
  outcome: "achieved" | "timed_out" | "skipped" | "stopped";
  seconds_to_achieve: number | null;
  peak_level: number;
  relative_to_calibration: boolean;
  feedback_visible: boolean;
}

export type RecognitionOutcome = "answered" | "timed_out" | "skipped" | "stopped";

/** Reconocimiento en curso para quien conduce: las opciones, la de la imagen y la elegida. */
export interface GuidedRecognition {
  target_expression: string;
  situation?: string | null;
  options: string[];
  chosen_expression: string | null;
  outcome: RecognitionOutcome | null;
}

/** Dibujo en curso para quien conduce: las emociones para registrar y la elegida. */
export interface GuidedDrawing {
  options: string[];
  chosen_expression: string | null;
  outcome: RecognitionOutcome | null;
}

export type GameOutcome = "completed" | "timed_out" | "skipped" | "stopped";
/** «matching»: imagen con el nombre de su emoción; «similar»: imagen modelo con otra de la misma emoción. */
export type GameType = "matching" | "similar";
export type GameState = "playing" | "retry" | "matched" | "shown" | "finished";

/** Juego en curso para quien conduce: la ronda, la emoción de la imagen y los contadores. */
export interface GuidedGame {
  round: number;
  rounds: number;
  game_type?: GameType;
  /** La imagen de la ronda (la modelo, al buscar la misma emoción). */
  stimulus_id: string | null;
  target_expression: string | null;
  /** Claves de las opciones: la emoción, o el lugar («1», «2»…) al buscar la misma emoción. */
  options: string[];
  option_details?: { key: string; expression: string; stimulus_id: string | null }[];
  tried: string[];
  removed: string | null;
  state: GameState;
  helped: boolean;
  rounds_done: number;
  matched: number;
  first_try: number;
  help_used: number;
  outcome: GameOutcome | null;
}

/** Solo contadores del juego: no es un puntaje. */
export interface GuidedGameResult {
  step_index: number;
  game_type: GameType;
  outcome: GameOutcome;
  rounds_total: number;
  rounds_done: number;
  matched: number;
  first_try: number;
  help_used: number;
  by_conductor: number;
}

/** Solo la emoción que la persona señaló; el dibujo nunca llega al servidor. */
export interface GuidedDrawingResult {
  step_index: number;
  outcome: RecognitionOutcome;
  chosen_expression: string | null;
  seconds_to_answer: number | null;
  answered_by: "participant" | "conductor" | null;
}

export interface GuidedRecognitionResult {
  step_index: number;
  stimulus_id: string;
  target_expression: string;
  options: string[];
  outcome: RecognitionOutcome;
  chosen_expression: string | null;
  matched: boolean | null;
  seconds_to_answer: number | null;
  answered_by: "participant" | "conductor" | null;
}

export interface GuidedCapture {
  id: string;
  captured_at: string;
  step_index: number;
  stimulus_id: string | null;
  seconds_since_stimulus: number;
  emotion: string | null;
  confidence: number | null;
  calibrated_emotion: string | null;
  quality: "good" | "flagged";
  quality_issues: string[];
  emotion_model_id: string;
}

/** Estado para quien conduce la sesión (nunca llega a la pantalla de la persona). */
export interface GuidedState {
  session_id: string;
  /** El protocolo tiene algún apoyo. */
  accessible?: boolean;
  supports?: ProtocolSupports | null;
  /** «Esperar a quien conduce»: el paso terminó y sigue al pulsar «Seguir». */
  waiting_for_conductor?: boolean;
  /** Dónde está abierta la pantalla de la persona y si hay un código de Android sin canjear. */
  screen?: GuidedScreen;
  /** Intento del reconocimiento o del ejercicio en curso (1 el primero). */
  attempt?: number | null;
  /** El paso terminó y todavía se puede repetir. */
  can_repeat?: boolean;
  max_attempts?: number;
  /** Código para anotar en el formato firmado. */
  session_code: string | null;
  phase: GuidedPhase;
  audience: SessionType;
  has_protocol: boolean;
  /** Falso en un protocolo solo de reconocimientos: no se calibra ni se usa la cámara. Si falta, se asume verdadero. */
  uses_camera?: boolean;
  /** Quien conduce siguió sin cámara: no se calibra y se saltan los pasos que la necesitan. */
  camera_off?: boolean;
  /** Motivo que informó la pantalla de la persona al no poder usar la cámara. */
  camera_problem?: "insecure" | "denied" | "busy" | "not_found" | "unknown" | null;
  stop_reason: "participant" | "guardian" | "conductor" | null;
  step_index: number | null;
  step_count: number;
  steps: GuidedStep[];
  remaining_seconds: number | null;
  /** reason "no_camera": el paso se saltó porque la sesión siguió sin cámara. */
  steps_log: { step_index: number; skipped: boolean; reason?: "no_camera" }[];
  calibration: { state: "none" | "calibrating" | "calibrated"; progress: number; notice: string | null };
  capture_status: string[];
  pre_questionnaire_id: string | null;
  post_questionnaire_id: string | null;
  abstract_notice: string | null;
  captures: GuidedCapture[];
  markers: { id: string; kind: MarkerKind; occurred_at: string; step_index: number | null; note: string | null }[];
  verbal_responses: { step_index: number; stimulus_id: string; text: string; recorded_at: string }[];
  /** Si la persona ve la señal del nivel en los ejercicios. */
  practice_feedback?: boolean;
  practice?: GuidedPractice | null;
  practice_results?: GuidedPracticeResult[];
  recognition?: GuidedRecognition | null;
  recognition_results?: GuidedRecognitionResult[];
  drawing?: GuidedDrawing | null;
  drawing_results?: GuidedDrawingResult[];
  game?: GuidedGame | null;
  game_results?: GuidedGameResult[];
  /** Repeticiones (intento 2 en adelante): se describen aparte y no cuentan en las métricas. */
  repeated_attempts?: GuidedRepeatedAttempt[];
}

export interface GuidedRepeatedAttempt {
  step_index: number;
  attempt: number;
  step_kind: "practice" | "recognition" | "drawing" | "game";
  /** Nulo en un dibujo o un juego: no hay expresión pedida. */
  target_expression: string | null;
  outcome: PracticeOutcome | RecognitionOutcome | GameOutcome;
  /** Solo en un juego: contadores del intento. */
  rounds_total?: number;
  rounds_done?: number;
  matched?: number;
  first_try?: number;
  help_used?: number;
  seconds_to_achieve?: number | null;
  chosen_expression?: string | null;
  seconds_to_answer?: number | null;
  answered_by?: "participant" | "conductor" | null;
}

/** Lo único que recibe la pantalla de la persona evaluada. */
/** Ejercicio de práctica en la pantalla de la persona: nunca la expresión detectada ni probabilidades. */
export interface ParticipantPractice {
  instruction: string;
  /** Entre 0 y 1; nulo si quien conduce apagó la señal. */
  level: number | null;
  achieved: boolean;
  message: string | null;
  frame_interval_ms: number;
}

/** Reconocimiento en la pantalla de la persona: la pregunta, las opciones y, al
 * terminar, el nombre de la emoción de la imagen (sin decir si acertó). */
export interface ParticipantRecognition {
  question: string;
  situation?: string | null;
  options: { key: string; label: string }[];
  chosen: string | null;
  message: string | null;
  /** Al terminar el paso: explicación sencilla del catálogo revisable. */
  explanation?: string | null;
  /** Al terminar un paso con situación: que cada persona puede sentir algo distinto. */
  note?: string | null;
}

/** Dibujo en la pantalla de la persona: el dibujo se queda en el dispositivo;
 * solo se envía la emoción que eligió. */
export interface ParticipantDrawing {
  instruction: string;
  question: string;
  options: { key: string; label: string }[];
  /** Cambia con cada intento: se empieza un lienzo nuevo. */
  round: string;
  /** El paso terminó: respondido o sin tiempo. */
  finished: boolean;
  chosen: string | null;
  message: string | null;
}

/** Una ronda del juego en la pantalla de la persona: sin puntaje. */
export interface ParticipantGame {
  /** Cambia con cada ronda e intento. */
  round: string;
  number: number;
  total: number;
  /** Sin él, «matching». Al buscar la misma emoción, cada opción es una imagen. */
  game_type?: GameType;
  question: string;
  /** «ended»: venció el tiempo del juego. */
  state: GameState | "ended";
  options: { key: string; label: string; available: boolean }[];
  /** La clave de la opción correcta, solo al terminar la ronda. */
  answer: string | null;
  message: string | null;
  explanation?: string | null;
  can_help: boolean;
  last_round: boolean;
}

export interface ParticipantViewState {
  phase: GuidedPhase;
  message: string | null;
  stimulus: { exposure: string } | null;
  remaining_seconds: number | null;
  capture_frames: boolean;
  frame_interval_ms: number;
  abstract_notice: string | null;
  practice?: ParticipantPractice | null;
  recognition?: ParticipantRecognition | null;
  drawing?: ParticipantDrawing | null;
  game?: ParticipantGame | null;
  /** Solo aparece si hay pictogramas o botones grandes. */
  accessible?: boolean;
  /** Solo aparece, como falso, si la sesión no usa la cámara. */
  uses_camera?: boolean;
  /** Solo aparece si el protocolo tiene algún apoyo que cambia la pantalla. */
  supports?: { pictograms: boolean; large_controls: boolean; read_aloud: boolean };
  /** La actividad de ahora, sin respuestas (la usa Android). */
  activity?: ParticipantActivity | null;
}

export interface ParticipantActivity {
  kind: "waiting" | "questionnaire" | "stimulus" | "practice" | "recognition" | "drawing" | "game" | "live" | "finished";
  name: string;
  number: number | null;
  total: number | null;
}

/** La pantalla de la persona: en la web (enlace) o en Android (código de un solo uso). */
export interface GuidedScreen {
  device: "web" | "android" | null;
  /** Hay un código para Android sin canjear hasta esa hora. */
  pairing_expires_at: string | null;
  /** Falso si la sesión usa la cámara, es un examen o ya terminó. */
  can_pair_android: boolean;
}

export interface AndroidCode {
  code: string;
  expires_at: string;
  expires_in: number;
}

/** Un solo eje de tiempo, en segundos desde el inicio de la sesión. */
export interface SessionTimeline {
  session_id: string;
  session_code?: string | null;
  started_at: string;
  duration_seconds: number;
  lanes: {
    questionnaires: { time: number; moment: QuestionnaireMoment; title: string; answers: { question: string; kind: QuestionKind; answer: AnswerValue | null }[] }[];
    stimuli: { step_index: number; title: string; kind: string; start: number | null; end: number | null; skipped: boolean;
      /** Solo en un ejercicio de práctica (kind «practice») o un reconocimiento (kind «recognition»). */
      target_expression?: string | null; outcome?: PracticeOutcome | RecognitionOutcome | GameOutcome | null;
      imitate?: boolean;
      /** Solo en un juego (kind «game»). */
      game_type?: GameType | null;
      seconds_to_achieve?: number | null; chosen_expression?: string | null; seconds_to_answer?: number | null;
      /** Solo en un juego (kind «game»): rondas y lo que ocurrió, en una frase. */
      rounds?: number | null; sentence?: string | null;
      /** Repeticiones del paso (intento 2 en adelante); el resultado de arriba es el primero. */
      repeats?: { attempt: number; outcome: PracticeOutcome | RecognitionOutcome | GameOutcome;
        seconds_to_achieve?: number | null; chosen_expression?: string | null; seconds_to_answer?: number | null;
        sentence?: string | null }[] }[];
    captures: { time: number; step_index: number; emotion: string | null; probability: number | null; quality: "good" | "flagged" }[];
    said: { time: number; step_index: number; title: string; text: string }[];
    markers: { time: number; kind: MarkerKind; note: string | null }[];
    /** Reservado para el ritmo cardíaco, cuando exista el sensor. */
    heart_rate: never[];
  };
}

export interface MetricCapture {
  id: string;
  captured_at: string;
  emotion: string | null;
  probability: number | null;
  seconds_since_stimulus: number;
  quality: "good" | "flagged";
  quality_issues: string[];
  counted: boolean;
  matches_expected?: boolean | null;
}

/** Métricas descriptivas: describen, no interpretan. */
export type PracticeOutcome = "achieved" | "timed_out" | "skipped" | "stopped";

/** Totales de ejercicios de práctica: describen lo ocurrido, sin valorar a la persona. */
export interface PracticeTotals {
  applied: number;
  achieved: number;
  skipped: number;
  stopped: number;
  average_seconds_to_achieve: number | null;
  feedback_visible: number;
  sentence: string;
  average_sentence: string | null;
  feedback_sentence: string | null;
}

export interface PracticeRow {
  applied: number;
  achieved: number;
  skipped: number;
  stopped: number;
  average_seconds_to_achieve: number | null;
}

export interface SessionPractice {
  exercises: { step_index: number; target_expression: string; hold_seconds: number; max_seconds: number;
    /** «Haz la misma cara»: imitó la imagen del modelo. */
    imitate?: boolean;
    /** null: la sesión no llegó a este ejercicio. */
    outcome: PracticeOutcome | null; seconds_to_achieve: number | null; peak_level: number | null;
    relative_to_calibration: boolean | null; feedback_visible: boolean | null }[];
  totals: PracticeTotals & { exercises: number; not_reached: number };
  by_target: (PracticeRow & { target_expression: string })[];
  notice: string;
}

/** Totales de reconocimiento: describen las respuestas, sin valorar a la persona. */
export interface RecognitionTotals {
  applied: number;
  matched: number;
  timed_out: number;
  skipped: number;
  stopped: number;
  average_seconds_to_answer: number | null;
  sentence: string;
}

export interface RecognitionRow {
  target_expression: string;
  applied: number;
  matched: number;
  timed_out: number;
  skipped: number;
  stopped: number;
  /** Lo que se eligió en lugar de la emoción de la imagen, contado. */
  other_choices: { expression: string; count: number }[];
}

export interface SessionRecognition {
  exercises: { step_index: number; stimulus_id: string; target_expression: string; max_seconds: number;
    /** null: la sesión no llegó a este paso. */
    options: string[] | null; outcome: RecognitionOutcome | null; chosen_expression: string | null;
    matched: boolean | null; seconds_to_answer: number | null; answered_by: "participant" | "conductor" | null }[];
  totals: RecognitionTotals & { exercises: number; not_reached: number };
  by_target: RecognitionRow[];
  notice: string;
}

export interface SessionDrawing {
  exercises: { step_index: number; max_seconds: number; outcome: RecognitionOutcome | null;
    chosen_expression: string | null; seconds_to_answer: number | null; answered_by: "participant" | "conductor" | null }[];
  totals: { exercises: number; answered: number; timed_out: number; skipped: number; stopped: number;
    not_reached: number; sentence: string };
  notice: string;
}

export interface SessionGame {
  exercises: { step_index: number; game_type: GameType; rounds: number; option_count: number;
    /** null: la sesión no llegó a este paso. */
    outcome: GameOutcome | null; rounds_done: number | null; matched: number | null; first_try: number | null;
    help_used: number | null; by_conductor: number | null; sentence: string | null }[];
  totals: { games: number; completed: number; timed_out: number; skipped: number; stopped: number;
    not_reached: number; rounds_total: number; rounds_done: number; matched: number; first_try: number;
    help_used: number; sentence: string | null };
  notice: string;
}

export interface SessionMetrics {
  session_id: string;
  emotional: { step_index: number; title: string; category: string; skipped: boolean; expected_expression: string;
    captures: MetricCapture[]; counted: boolean; matches_expected: boolean | null; excluded_captures: number }[];
  abstract: { step_index: number; title: string; category: string; skipped: boolean; captures: MetricCapture[]; said: string | null }[];
  totals: { emotional_stimuli: number; counted: number; matched: number; excluded_captures: number; sentence: string };
  abstract_notice: string | null;
  /** Ejercicios de práctica, aparte de la coincidencia de estímulos; null si no hubo. */
  practice?: SessionPractice | null;
  /** Reconocimientos, también aparte; null si no hubo. */
  recognition?: SessionRecognition | null;
  /** Dibujos: solo la emoción señalada; null si no hubo. */
  drawing?: SessionDrawing | null;
  /** Juegos de emparejar: solo contadores de rondas; null si no hubo. */
  game?: SessionGame | null;
  /** Resultados educativos separados por tipo de actividad; null si no hubo actividades. */
  educational?: SessionEducational | null;
}

/** Una actividad que no llegó a su final: omitida, interrumpida o sin aplicar. */
export interface NotCompletedActivity {
  step_index: number;
  kind: "recognition" | "drawing" | "game" | "practice";
  activity: string;
  status: "skipped" | "stopped" | "not_reached";
  label: string;
}

/** Resumen por tipo de actividad: solo cuenta y nombra; no es un puntaje. */
export interface SessionEducational {
  recognition: { exercises: number; applied: number; matched: number; timed_out: number; sentence: string } | null;
  drawing: { exercises: number; completed: number; timed_out: number;
    indicated: { expression: string; count: number }[]; sentence: string } | null;
  games: { games: number; played: number; attempts: number; rounds_total: number; rounds_done: number;
    matched: number; first_try: number; help_used: number; sentence: string } | null;
  practice: { exercises: number; applied: number; achieved: number; sentence: string } | null;
  not_completed: { items: NotCompletedActivity[]; skipped: number; stopped: number; not_reached: number; sentence: string };
  notice: string;
}

export type ReportStatus = "draft" | "submitted" | "changes_requested" | "approved";
export type ReportSection = "timeline" | "metrics" | "questionnaires" | "narrative" | "general";

/** Reporte de una sesión: redacta quien la condujo, revisa su docente. */
export interface SessionReport {
  id: string;
  version: number;
  status: ReportStatus;
  current: boolean;
  narrative: string;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  session: { id: string; code: string | null; started_at: string; session_type: SessionType; emotion_model_id: string | null; emotion_model_version: string | null };
  /** Código de la sesión, para cruzarlo con el formato firmado. */
  session_code: string | null;
  estimates_notice: string;
  abstract_notice: string | null;
  timeline: SessionTimeline;
  metrics: SessionMetrics;
  authored_by_me?: boolean;
  requires_review?: boolean;
  can_edit?: boolean;
  can_review?: boolean;
  can_new_version?: boolean;
  comments?: { id: string; section: ReportSection; text: string; created_at: string }[];
  history?: { action: string; occurred_at: string; version: number | null; by: "author" | "docente" }[];
  versions?: { id: string; version: number; status: ReportStatus }[];
}

/** Estadísticas agregadas: cuentan sesiones, no personas (GET /statistics). */
export interface CountRow {
  label: string;
  count: number;
}

export interface QuestionStatistics {
  text: string;
  kind: "scale" | "single_choice" | "multiple_choice" | "short_text" | "faces";
  answered: number;
  unanswered: number;
  /** Nulo en las preguntas de texto: solo se informa cuántas respuestas hubo. */
  counts: CountRow[] | null;
  min_label?: string | null;
  max_label?: string | null;
}

export interface StatisticsGameRow {
  games: number; attempts: number; completed: number; timed_out: number; skipped: number; stopped: number;
  rounds_total: number; rounds_done: number; matched: number; first_try: number; help_used: number; sentence: string;
}

export interface SessionStatistics {
  scope: "mine" | "group";
  notice: string;
  few_sessions: boolean;
  few_sessions_notice: string | null;
  sessions: { total: number; completed: number; interrupted: number; average_duration_seconds: number | null };
  expressions: {
    counted_captures: number;
    excluded_captures: number;
    rows: { expression: string; captures: number; percent: number; sessions: number }[];
  };
  coincidence: { compared: number; matched: number };
  protocols: { family_id: string; name: string }[];
  questionnaires: { id: string; title: string; version: number; responses: number }[];
  questionnaire: { id: string; title: string; version: number; responses: number; questions: QuestionStatistics[] } | null;
  by_user?: { email: string; sessions: number; completed: number; interrupted: number }[];
  /** Ejercicios de práctica, sin mezclar con la coincidencia de estímulos; null si no hubo. */
  practice?: {
    sessions: number;
    totals: PracticeTotals;
    by_protocol: (PracticeRow & { family_id: string; name: string; sessions: number })[];
    by_target: (PracticeRow & { target_expression: string })[];
    by_user?: (PracticeRow & { email: string })[];
    notice: string;
  } | null;
  /** Reconocimientos de emociones, aparte; null si no hubo. */
  recognition?: { sessions: number; totals: RecognitionTotals; by_target: RecognitionRow[]; notice: string } | null;
  /** Dibujos: cuántos terminaron con una emoción señalada y cuáles; null si no hubo. */
  drawing?: { sessions: number; totals: { exercises: number; answered: number; timed_out: number; skipped: number;
    stopped: number; sentence: string }; by_expression: { expression: string; count: number }[]; notice: string } | null;
  /** Juegos: contadores de rondas e intentos, en total y por tipo; null si no hubo. */
  games?: { sessions: number; totals: StatisticsGameRow; by_type: (StatisticsGameRow & { game_type: GameType })[];
    notice: string } | null;
}

/** Examen simulado: lo crea un docente; cada estación es una sesión con su código. */
export type ExamState = "open" | "in_progress" | "closed";

/** Solo el estado de la estación: nunca imágenes ni expresiones. */
export interface ExamStation {
  code: string;
  joined_at: string;
  consent_confirmed: boolean;
  phase: GuidedPhase | null;
  finished: boolean;
}

export interface ExamSummary {
  id: string;
  join_code: string;
  state: ExamState;
  created_at: string;
  consent_confirmed_at: string | null;
  started_at: string | null;
  closed_at: string | null;
  station_count: number;
  waiting_consent: number;
}

export interface ExamDetail extends ExamSummary {
  stations: ExamStation[];
}

/** Lo que recibe una estación al unirse con el código del examen. */
export interface ExamStationJoin {
  view_token: string;
  session_code: string;
}
