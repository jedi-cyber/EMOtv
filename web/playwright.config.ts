import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Stack de Docker por defecto; para backend y frontend locales: E2E_BASE_URL=http://localhost:5173
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8080";
const fakeVideo = process.env.E2E_FAKE_VIDEO
  ?? fileURLToPath(new URL("./e2e/fixtures/generated/camera.y4m", import.meta.url));

// Cámara simulada: Chromium concede el permiso sin diálogo y lee el video .y4m.
// Sin video, usa su patrón sintético (no hay persona en la imagen).
const cameraArgs = [
  "--use-fake-ui-for-media-stream",
  "--use-fake-device-for-media-stream",
  ...(existsSync(fakeVideo) ? [`--use-file-for-fake-video-capture=${fakeVideo}`] : []),
];

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  // Un solo worker: el límite de intentos de inicio de sesión cuenta por IP y
  // el n8n falso escucha en un puerto fijo.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    locale: "es-PE",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // E2E_BROWSER_CHANNEL=chrome o msedge usa el navegador instalado si el Chromium de Playwright no arranca.
        channel: process.env.E2E_BROWSER_CHANNEL || undefined,
        launchOptions: { args: cameraArgs },
      },
    },
  ],
});
