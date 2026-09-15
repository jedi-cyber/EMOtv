import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/sessions": "http://127.0.0.1:8000",
      "/students": "http://127.0.0.1:8000",
      "/users": "http://127.0.0.1:8000",
      "/activities": "http://127.0.0.1:8000",
      "/emotion-models": "http://127.0.0.1:8000",
      "/video_feed": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true }
    }
  }
});
