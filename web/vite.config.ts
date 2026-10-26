import { defineConfig } from "vite";
import type { ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

// Algunas rutas existen en la SPA y en la API (/sessions,
// /participant-view...). La navegación del navegador pide text/html y recibe la
// SPA; las llamadas a la API van al backend (igual que en docker/nginx.conf).
const api: ProxyOptions = {
  target: "http://127.0.0.1:8000",
  bypass: (request) => (request.headers.accept?.includes("text/html") ? "/index.html" : undefined),
};
const apiPrefixes = [
  "/auth", "/sessions", "/students", "/users", "/activities", "/analysis", "/expressions", "/recommendations",
  "/chat", "/consent-policy", "/consent-policies", "/health", "/commitment", "/audit", "/admin",
  "/session-deletions", "/stimuli", "/protocols", "/questionnaires", "/guided-sessions", "/participant-view",
  "/reports", "/mobile",
];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      ...Object.fromEntries(apiPrefixes.map((prefix) => [prefix, api])),
      "/ws": { target: "ws://127.0.0.1:8000", ws: true }
    }
  }
});
