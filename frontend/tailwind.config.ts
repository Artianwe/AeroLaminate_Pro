// AeroLaminate Pro design tokens - graphite / ivory with a single amber accent. Author: Anwesh Ajitabh Dash.
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ivory: { 50: "#fcfbf7", 100: "#f7f4ec", 200: "#efeadc", 300: "#e2dccb" },
        graphite: { 400: "#8a8780", 500: "#6b6963", 600: "#52514e", 700: "#3a3a38", 800: "#262624", 900: "#1a1a19" },
        amber: { 400: "#e9a92a", 500: "#d69214", 600: "#b07408", 700: "#8a5a05" },
        rule: "#d9d3c2",
        ok: "#2f7d4a", warn: "#b07408", bad: "#b3372f",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', '"JetBrains Mono"', "Consolas", '"Cascadia Mono"', "monospace"],
      },
      fontSize: { xxs: ["10.5px", "14px"] },
    },
  },
  plugins: [],
} satisfies Config;
