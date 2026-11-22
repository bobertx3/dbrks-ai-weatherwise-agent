import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built assets are written to ../static and served by the FastAPI backend (dapp/app.py).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
