import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the replay API runs on :8000 (uv run uvicorn second_look.api:app --port 8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
