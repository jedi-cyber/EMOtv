export interface Activity {
  id: string;
  name: string;
  description: string;
  required_posture: string;
  duration_seconds: number;
  repetitions: number;
}

export type SessionState = "created" | "in_progress" | "completed" | "cancelled";

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
}
