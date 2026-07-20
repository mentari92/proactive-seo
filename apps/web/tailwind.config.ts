import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--bg-page)",
        surface: "var(--bg-surface)",
        sunken: "var(--bg-sunken)",
        ink: "var(--ink-primary)",
        muted: "var(--ink-secondary)",
        border: "var(--border-default)",
        primary: "var(--primary-600)"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"]
      },
      boxShadow: { raised: "0 1px 2px rgba(0,0,0,.05)" }
    }
  },
  plugins: []
};

export default config;

