import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// This server only talks to the disposable QA backend, never production storage.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8001", changeOrigin: true } },
  },
});
