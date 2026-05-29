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
        sans:    ["IBM Plex Sans", "system-ui", "sans-serif"],
        display: ["Bricolage Grotesque", "system-ui", "sans-serif"],
        mono:    ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "8px",
        md: "10px",
        lg: "12px",
        xl: "16px",
      },
      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          "0%":   { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "badge-in": {
          "0%":   { opacity: "0", transform: "scale(0.75)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "row-in": {
          "0%":   { opacity: "0", transform: "translateY(-6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.3" },
        },
      },
      animation: {
        "fade-up":        "fade-up 0.4s cubic-bezier(0.16,1,0.3,1) both",
        "slide-in-left":  "slide-in-left 0.35s cubic-bezier(0.16,1,0.3,1) both",
        "badge-in":       "badge-in 0.25s cubic-bezier(0.34,1.56,0.64,1) both",
        "row-in":         "row-in 0.3s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-dot":      "pulse-dot 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default config;
