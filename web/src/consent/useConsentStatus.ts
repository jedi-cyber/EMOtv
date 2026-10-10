import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../api/http";
import type { Student } from "../api/types";
import { useAuth } from "../auth/useAuth";

export type ConsentPolicy = {
  id?: string | null; code?: string | null; version: string | null;
  title?: string | null; content?: string | null; effective_at?: string | null; is_demo?: boolean;
  mode?: "development" | "demo" | "production"; url: string | null; available: boolean;
};
export type ConsentRecord = { id: string; policy_version: string; granted_at: string; revoked_at?: string | null };

/**
 * active: hay consentimiento para la política vigente. outdated: el activo es
 * de otra versión. missing: no hay consentimiento activo. not_required: modo
 * de desarrollo. unavailable: no hay política activa. no_student: la cuenta no
 * tiene perfil de estudiante.
 */
export type ConsentState = "loading" | "active" | "outdated" | "missing" | "not_required" | "unavailable" | "no_student" | "error";

export interface ConsentStatus {
  state: ConsentState;
  policy: ConsentPolicy | null;
  student: Student | null;
  active: ConsentRecord | null;
  error: string;
  reload(): Promise<void>;
}

export function policyKey(policy: ConsentPolicy | null): string | null {
  return policy ? policy.id ?? policy.version : null;
}

/** "v0.3" o "EMOTV-CONSENT-DEMO-003:v0.3" → "Versión 0.3". */
export function versionLabel(version: string | null | undefined): string {
  const match = /v?(\d+(?:\.\d+)*)$/i.exec(version ?? "");
  return match ? `Versión ${match[1]}` : "Versión vigente";
}

export function formatLongDate(value: string): string {
  return new Date(value).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" });
}

/** Estado del consentimiento de la cuenta de estudiante con los endpoints existentes. */
export function useConsentStatus(enabled = true): ConsentStatus {
  const { token } = useAuth();
  const [state, setState] = useState<ConsentState>(enabled ? "loading" : "not_required");
  const [policy, setPolicy] = useState<ConsentPolicy | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [active, setActive] = useState<ConsentRecord | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    if (!enabled || !token) return;
    setState("loading"); setError("");
    try {
      const current = await apiRequest<ConsentPolicy>("/consent-policy", { token });
      setPolicy(current);
      const students = await apiRequest<Student[]>("/students", { token });
      const own = students?.[0] ?? null;
      setStudent(own);
      if (current?.mode === "development") { setActive(null); setState("not_required"); return; }
      if (!own) { setActive(null); setState("no_student"); return; }
      const record = await apiRequest<ConsentRecord | null>(`/students/${encodeURIComponent(own.id)}/consents/active`, { token });
      setActive(record ?? null);
      if (!current?.available) setState("unavailable");
      else if (!record) setState("missing");
      else setState(record.policy_version === policyKey(current) ? "active" : "outdated");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo consultar el consentimiento.");
      setState("error");
    }
  }, [enabled, token]);

  useEffect(() => { void reload(); }, [reload]);
  return { state, policy, student, active, error, reload };
}
