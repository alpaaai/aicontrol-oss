import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "ac-night":          "#0A1418",
        "ac-peacock": {
          50:  "#E3F4F8",
          100: "#C7E9F1",
          200: "#9AD8E5",
          300: "#6CC3D6",
          400: "#4FB8D4",
          500: "#0284A8",
          600: "#06647F",
          700: "#054A5C",
          800: "#043B49",
          900: "#032B37",
        },
        "ac-primary":        "var(--ac-primary)",
        "ac-primary-lt":     "var(--ac-primary-lt)",
        "ac-primary-bg":     "var(--ac-primary-bg)",
        "ac-allow":          "var(--ac-allow)",
        "ac-allow-bg":       "var(--ac-allow-bg)",
        "ac-deny":           "var(--ac-deny)",
        "ac-deny-bg":        "var(--ac-deny-bg)",
        "ac-review":         "var(--ac-review)",
        "ac-review-bg":      "var(--ac-review-bg)",
        "ac-enterprise":     "var(--ac-enterprise)",
        "ac-enterprise-bg":  "var(--ac-enterprise-bg)",
        "ac-surface":        "var(--ac-surface)",
        "ac-card":           "var(--ac-card)",
        "ac-border":         "var(--ac-border)",
        "ac-text-primary":   "var(--ac-text-primary)",
        "ac-text-muted":     "var(--ac-text-muted)",
      },
      backgroundImage: {
        "ac-gradient-feather": "linear-gradient(135deg, #0284A8 0%, #14B8A6 50%, #6C63FF 100%)",
      },
      fontFamily: {
        sans:    ["Geist", "system-ui", "sans-serif"],
        display: ["Geist", "system-ui", "sans-serif"],
        mono:    ["Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "10px",
        md: "10px",
        lg: "16px",
        xl: "16px",
      },
      boxShadow: {
        "ac-card":     "0 3px 6px rgba(3,66,84,0.06)",
        "ac-card-lg":  "0 12px 24px rgba(3,66,84,0.10)",
        "ac-modal":    "0 24px 48px rgba(3,66,84,0.14)",
        "ac-focus":    "0 0 0 3px rgba(2,132,168,0.35)",
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
        "fade-up":        "fade-up 0.3s cubic-bezier(0.25,1,0.5,1) both",
        "slide-in-left":  "slide-in-left 0.3s cubic-bezier(0.25,1,0.5,1) both",
        "badge-in":       "badge-in 0.25s cubic-bezier(0.34,1.56,0.64,1) both",
        "row-in":         "row-in 0.3s cubic-bezier(0.25,1,0.5,1) both",
        "pulse-dot":      "pulse-dot 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default config;
