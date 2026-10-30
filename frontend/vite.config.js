import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Saat `npm run dev`, semua request /api diteruskan ke backend FastAPI.
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true, timeout: 0, proxyTimeout: 0 },
    },
  },
});
