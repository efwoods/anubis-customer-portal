import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    // 5173 is reserved for another local app; portal uses 5171.
    port: 5171,
  },
});
