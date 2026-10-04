import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2020",
    sourcemap: false,
    assetsInlineLimit: 0,
  },
  server: {
    // Local development: API runs on :8000 (ENV=dev, BOT_MODE=polling).
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "node",
  },
});
