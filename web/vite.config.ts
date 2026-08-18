/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // El backend de control. El AUDIO no pasa por acá: va directo a Gemini.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    // jsdom por `document`, `atob` y `btoa`. El Web Audio API NO lo trae:
    // los tests montan su propio doble (ver `audioContextFalso.ts`).
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
