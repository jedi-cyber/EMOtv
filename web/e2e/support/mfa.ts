import { createHmac } from "node:crypto";

/**
 * Segundo factor de las cuentas de gestión en las pruebas e2e: códigos TOTP
 * (RFC 6238, como src/emotv/application/totp.py) a partir de la clave que la
 * prueba recibe al configurar la cuenta. Las claves viven solo en memoria y en
 * variables de entorno del proceso; nunca en archivos.
 */

const STEP_MS = 30_000;
const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function decode(secret: string): Buffer {
  let bits = "";
  for (const char of secret.replace(/=+$/, "").toUpperCase()) {
    const value = BASE32.indexOf(char);
    if (value < 0) throw new Error("La clave TOTP no está en base32.");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((byte) => parseInt(byte, 2)));
}

export function codeAt(secret: string, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", decode(secret)).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

const currentStep = () => Math.floor(Date.now() / STEP_MS);

interface Enrolled { secret: string; lastStep: number }
const enrolled = new Map<string, Enrolled>();

/** La clave de la cuenta de superadmin de pruebas llega de global-setup por el entorno. */
function load(email: string): Enrolled | undefined {
  const known = enrolled.get(email);
  if (known) return known;
  if (email === process.env.E2E_ADMIN_EMAIL && process.env.E2E_ADMIN_TOTP_SECRET) {
    const restored = { secret: process.env.E2E_ADMIN_TOTP_SECRET, lastStep: Number(process.env.E2E_ADMIN_TOTP_LAST_STEP ?? "0") };
    enrolled.set(email, restored);
    return restored;
  }
  return undefined;
}

export function registerSecret(email: string, secret: string): void {
  enrolled.set(email, { secret, lastStep: 0 });
}

export function lastStepOf(email: string): number {
  return load(email)?.lastStep ?? 0;
}

function required(email: string): Enrolled {
  const account = load(email);
  if (!account) {
    throw new Error(`La cuenta ${email} ya tiene configurada la aplicación autenticadora y la prueba no conoce su clave. `
      + "Define E2E_ADMIN_TOTP_SECRET o reinícialo con scripts/security/reset_mfa.py (docs/testing/e2e.md).");
  }
  return account;
}

/** Código para iniciar sesión: el servidor no acepta dos veces el mismo intervalo, así que espera al siguiente. */
export async function loginCode(email: string): Promise<string> {
  const account = required(email);
  let step = currentStep();
  if (step <= account.lastStep) {
    await new Promise((resolve) => setTimeout(resolve, (account.lastStep + 1) * STEP_MS - Date.now() + 200));
    step = currentStep();
  }
  account.lastStep = step;
  return codeAt(account.secret, step);
}

/** Cabecera con el código del momento para crear, cambiar o asignar cuentas. */
export function confirmationHeaders(email: string): Record<string, string> {
  const account = required(email);
  const step = Math.max(currentStep(), account.lastStep);
  account.lastStep = step;
  return { "X-Confirmation-Code": codeAt(account.secret, step) };
}
