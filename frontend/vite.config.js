import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/components/...`, `@/pages/...` etc. instead of long relative paths.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // Hybrid mode: forward API calls to the Flask dev server (make dev-backend),
    // so the browser only ever talks to one origin. "/api" covers both the
    // versioned module routes (/api/v1/...) and the unversioned /api/health and /api/docs.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    css: false,
  },
});
