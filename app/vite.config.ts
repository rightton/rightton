import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Relative base so the built site works from any folder (GitHub Pages project site).
export default defineConfig({
  base: "./",
  plugins: [react()],
  worker: { format: "es" },
  build: { target: "es2022", chunkSizeWarningLimit: 900 },
});
