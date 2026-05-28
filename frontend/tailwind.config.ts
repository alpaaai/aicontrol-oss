import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "ac-night":          "#0F1117",
        "ac-primary":        "#3B5BDB",
        "ac-primary-lt":     "#4F8EF7",
        "ac-primary-bg":     "#EEF2FF",
        "ac-allow":          "#1D9E75",
        "ac-allow-bg":       "#EDFAF3",
        "ac-deny":           "#E24B4A",
        "ac-deny-bg":        "#FCEBEB",
        "ac-review":         "#BA7517",
        "ac-review-bg":      "#FAEEDA",
        "ac-enterprise":     "#534AB7",
        "ac-enterprise-bg":  "#EEEDFE",
        "ac-surface":        "#F8F9FA",
        "ac-card":           "#FFFFFF",
        "ac-border":         "#E5E7EB",
        "ac-text-primary":   "#111827",
        "ac-text-muted":     "#6B7280",
      },
      fontFamily: {
        sans: ["Geist Sans", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "8px",
        md: "10px",
        lg: "12px",
        xl: "16px",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default config;
