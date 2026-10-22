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
export type SessionType = "propia" | "participante_adulto" | "participante_infantil";

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
  participant_id?: string | null;
  protocol_id?: string | null;
  /** Versiones exactas de los cuestionarios previo y posterior. */
  pre_questionnaire_id?: string | null;
  post_questionnaire_id?: string | null;
}

/** Modelo local que puede probar quien conduce la sesión (GET /analysis/models). */
export interface LocalModelOption {
  model_id: string;
  state: "SUPPORTED" | "WARNING" | "BLOCKED";
  is_default: boolean;
  reasons?: string[];
}

export type ParticipantKind = "adult" | "child";

/** Participante sin cuenta, nombre ni foto: solo un código. */
export interface Participant {
  id: string;
  code: string;
  kind: ParticipantKind;
  created_at: string;
  expires_at: string;
  notes: string | null;
  registered_by_me: boolean;
  deletion_requested_at: string | null;
  age_years: number | null;
  authorization_status: AuthorizationStatus;
  authorization_revoked_at: string | null;
}

/** ready: puede iniciar sesiones; revoked: se retiró una autorización. */
export type AuthorizationStatus = "ready" | "missing" | "revoked" | "no_age";

/** Formato firmado en papel: sin nombres ni datos de quien firma. */
export interface ParticipantAuthorization {
  id: string;
  form_version: string;
  signed_on: string;
  grantor: "participant" | "guardian";
  participation: boolean;
  camera: boolean;
  child_assent: boolean | null;
  recorded_at: string;
  revoked_at: string | null;
  revoked_party: "participant" | "guardian" | null;
  revoked_scope: "participation" | "camera" | "assent" | null;
}

export type StimulusKind = "emotional" | "abstract";
export type StimulusIntensity = "mild" | "moderate";

/** Imagen del banco de estímulos; nunca una foto de un participante. */
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
  scope: "group" | "institution";
  created_at: string;
  approved: boolean;
  active: boolean;
  can_manage: boolean;
}

export interface ProtocolStep {
  stimulus_id: string;
  exposure_seconds: number;
  capture_after_seconds: number;
  record_verbal_response: boolean;
  /** Solo imágenes abstractas: se muestran antes de la calibración, sin capturas. */
  shown_before_analyzer: boolean;
}

export interface Protocol {
  id: string;
  family_id: string;
  version: number;
  name: string;
  description: string;
  for_children: boolean;
  pre_questionnaire_id: string | null;
  post_questionnaire_id: string | null;
  steps: ProtocolStep[];
  created_at: string;
  approved: boolean;
  approved_at: string | null;
  owned_by_me: boolean;
  can_approve: boolean;
  used: boolean;
}

/** Acta de eliminación: sin datos personales. */
export interface DeletionCertificate {
  id: string;
  participant_code: string;
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

export type GuidedPhase = "confirmation" | "pre_questionnaire" | "before_analyzer" | "calibration" | "stimuli"
  | "post_questionnaire" | "finished" | "stopped";
export type MarkerKind = "distracted" | "laughed" | "asked_to_stop" | "cried" | "note";

export interface GuidedStep {
  index: number;
  stimulus_id: string;
  title: string;
  kind: "emotional" | "abstract" | "";
  exposure_seconds: number;
  capture_after_seconds: number;
  record_verbal_response: boolean;
  shown_before_analyzer: boolean;
}

export interface GuidedCapture {
  id: string;
  captured_at: string;
  step_index: number;
  stimulus_id: string;
  seconds_since_stimulus: number;
  emotion: string | null;
  confidence: number | null;
  calibrated_emotion: string | null;
  quality: "good" | "flagged";
  quality_issues: string[];
  emotion_model_id: string;
}

/** Estado para quien conduce la sesión guiada (nunca llega a la vista del participante). */
export interface GuidedState {
  session_id: string;
  phase: GuidedPhase;
  participant_kind: "adult" | "child" | null;
  stop_reason: "participant" | "guardian" | "conductor" | null;
  step_index: number | null;
  step_count: number;
  steps: GuidedStep[];
  remaining_seconds: number | null;
  steps_log: { step_index: number; skipped: boolean }[];
  calibration: { state: "none" | "calibrating" | "calibrated"; progress: number; notice: string | null };
  capture_status: string[];
  pre_questionnaire_id: string | null;
  post_questionnaire_id: string | null;
  abstract_notice: string | null;
  captures: GuidedCapture[];
  markers: { id: string; kind: MarkerKind; occurred_at: string; step_index: number | null; note: string | null }[];
  verbal_responses: { step_index: number; stimulus_id: string; text: string; recorded_at: string }[];
}

/** Lo único que recibe la vista del participante. */
export interface ParticipantViewState {
  phase: GuidedPhase;
  message: string | null;
  stimulus: { exposure: string } | null;
  remaining_seconds: number | null;
  capture_frames: boolean;
  frame_interval_ms: number;
  abstract_notice: string | null;
}

/** Un solo eje de tiempo, en segundos desde el inicio de la sesión. */
export interface SessionTimeline {
  session_id: string;
  started_at: string;
  duration_seconds: number;
  lanes: {
    questionnaires: { time: number; moment: QuestionnaireMoment; title: string; answers: { question: string; kind: QuestionKind; answer: AnswerValue | null }[] }[];
    stimuli: { step_index: number; title: string; kind: string; start: number | null; end: number | null; skipped: boolean }[];
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
export interface SessionMetrics {
  session_id: string;
  emotional: { step_index: number; title: string; category: string; skipped: boolean; expected_expression: string;
    captures: MetricCapture[]; counted: boolean; matches_expected: boolean | null; excluded_captures: number }[];
  abstract: { step_index: number; title: string; category: string; skipped: boolean; captures: MetricCapture[]; said: string | null }[];
  totals: { emotional_stimuli: number; counted: number; matched: number; excluded_captures: number; sentence: string };
  abstract_notice: string | null;
}

export interface ParticipantTrends {
  participant_id: string;
  code: string;
  protocols: { protocol_family_id: string; protocol_name: string; comparable: boolean; message: string;
    sessions: { session_id: string; started_at: string; protocol_version: number; matched: number; counted: number; sentence: string }[] }[];
}
