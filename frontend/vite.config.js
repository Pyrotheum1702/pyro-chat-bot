import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the React app runs on :5173 and proxies API calls to the FastAPI
// backend on :8017. In prod the backend serves the built app, so the proxy
// is irrelevant.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8017",
    },
  },
});
