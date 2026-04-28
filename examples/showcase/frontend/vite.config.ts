import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backendUrl =
  process.env.VITE_SHOWCASE_BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth/siwe/": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/api/showcase/": {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
  ssr: {
    noExternal: ["ethereum-identity-kit"],
  },
});
