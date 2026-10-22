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
