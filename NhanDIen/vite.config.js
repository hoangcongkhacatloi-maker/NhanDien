import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  resolve: {
    // Đảm bảo chỉ dùng 1 bản react
    dedupe: ["react", "react-dom"],
  },

  server: {
    host: true,

    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },

      "/files": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
