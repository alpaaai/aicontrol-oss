import type { Config } from "tailwindcss";

const config: Config = {
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
        "ac-primary":        "#0284A8",
        "ac-primary-lt":     "#4FB8D4",
        "ac-primary-bg":     "#E3F4F8",
        "ac-allow":          "#0F7A54",
        "ac-allow-bg":       "#E6F7EF",
        "ac-deny":           "#C22E28",
        "ac-deny-bg":        "#FCE9E8",
        "ac-review":         "#8F5710",
        "ac-review-bg":      "#FBEEDA",
        "ac-enterprise":     "#534AB7",
        "ac-enterprise-bg":  "#EEEDFE",
        "ac-surface":        "#F8F9FA",
        "ac-card":           "#FFFFFF",
        "ac-border":         "#DDE9EC",
        "ac-text-primary":   "#111827",
        "ac-text-muted":     "#6B7280",
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
