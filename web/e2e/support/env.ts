import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** Configuración de las pruebas e2e. Las credenciales llegan solo por variables de entorno. */
export const env = {
  baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
  adminEmail: process.env.E2E_ADMIN_EMAIL ?? "",
  adminPassword: process.env.E2E_ADMIN_PASSWORD ?? "",
  /** Debe coincidir con LOGIN_MAX_FAILURES_PER_ACCOUNT del backend. */
  loginMaxFailures: Number(process.env.E2E_LOGIN_MAX_FAILURES ?? "5"),
  /** Activa las pruebas de Emi: el backend debe apuntar N8N_WEBHOOK_URL al n8n falso. */
  fakeN8n: process.env.E2E_FAKE_N8N === "1",
  fakeN8nPort: Number(process.env.E2E_FAKE_N8N_PORT ?? "5679"),
  /** Si se define, el n8n falso exige que X-EMOtv-Key coincida (la misma N8N_WEBHOOK_KEY del backend). */
  fakeN8nKey: process.env.E2E_FAKE_N8N_KEY ?? "",
};

export interface FakeCamera {
  has_face: boolean;
  face_seconds: number;
  empty_seconds: number;
}

/** Lee camera.json, que escribe scripts/e2e/make_fake_video.py junto al video. */
export function fakeCamera(): FakeCamera {
  const video = process.env.E2E_FAKE_VIDEO
    ?? fileURLToPath(new URL("../fixtures/generated/camera.y4m", import.meta.url));
  const metadata = video.replace(/\.y4m$/, ".json");
  if (!existsSync(video) || !existsSync(metadata)) return { has_face: false, face_seconds: 0, empty_seconds: 0 };
  return JSON.parse(readFileSync(metadata, "utf-8")) as FakeCamera;
}
