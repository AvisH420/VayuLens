import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Minimal Vite config for the VayuLens React app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI gateway during local dev.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
