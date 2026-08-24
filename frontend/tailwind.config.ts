import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "ac-primary":            "var(--ac-primary)",
        "ac-primary-active":     "var(--ac-primary-active)",
        "ac-primary-soft":       "var(--ac-primary-soft)",
        "ac-primary-disabled":   "var(--ac-primary-disabled)",
        "ac-on-primary":         "var(--ac-on-primary)",

        "ac-ink":                "var(--ac-ink)",
        "ac-body":               "var(--ac-body)",
        "ac-body-strong":        "var(--ac-body-strong)",
        "ac-muted":              "var(--ac-muted)",
        "ac-muted-soft":         "var(--ac-muted-soft)",

        "ac-hairline":           "var(--ac-hairline)",
        "ac-hairline-soft":      "var(--ac-hairline-soft)",
        "ac-hairline-strong":    "var(--ac-hairline-strong)",

        "ac-canvas":             "var(--ac-canvas)",
        "ac-canvas-soft":        "var(--ac-canvas-soft)",
        "ac-surface-card":       "var(--ac-surface-card)",
        "ac-surface-sunk":       "var(--ac-surface-sunk)",
        "ac-surface-ink":        "var(--ac-surface-ink)",
        "ac-surface-ink-elevated": "var(--ac-surface-ink-elevated)",
        "ac-on-ink":             "var(--ac-on-ink)",
        "ac-on-ink-soft":        "var(--ac-on-ink-soft)",

        "ac-decision-allow":       "var(--ac-decision-allow)",
        "ac-decision-allow-soft":  "var(--ac-decision-allow-soft)",
        "ac-decision-review":      "var(--ac-decision-review)",
        "ac-decision-review-soft": "var(--ac-decision-review-soft)",
        "ac-decision-deny":        "var(--ac-decision-deny)",
        "ac-decision-deny-soft":   "var(--ac-decision-deny-soft)",

        "ac-success":            "var(--ac-success)",
        "ac-warning":            "var(--ac-warning)",
        "ac-error":              "var(--ac-error)",
      },
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Bricolage Grotesque", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "display-xl": ["64px", { lineHeight: "1.04", letterSpacing: "-2.4px", fontWeight: "400" }],
        "display-lg": ["48px", { lineHeight: "1.08", letterSpacing: "-1.8px", fontWeight: "400" }],
        "display-md": ["36px", { lineHeight: "1.14", letterSpacing: "-1.2px", fontWeight: "400" }],
        "display-sm": ["28px", { lineHeight: "1.2",  letterSpacing: "-0.8px", fontWeight: "450" }],
        "sentence":   ["32px", { lineHeight: "1.45", letterSpacing: "-0.9px", fontWeight: "400" }],
        "sentence-inline": ["15px", { lineHeight: "1.5", letterSpacing: "-0.1px" }],
        "title-lg":   ["22px", { lineHeight: "1.3",  letterSpacing: "-0.4px", fontWeight: "500" }],
        "title-md":   ["17px", { lineHeight: "1.4",  letterSpacing: "-0.2px", fontWeight: "500" }],
        "title-sm":   ["15px", { lineHeight: "1.4",  letterSpacing: "0",      fontWeight: "600" }],
        "body-md":    ["16px", { lineHeight: "1.6" }],
        "body-sm":    ["14px", { lineHeight: "1.55" }],
        "caption":    ["13px", { lineHeight: "1.4",  fontWeight: "500" }],
        "label-uc":   ["11px", { lineHeight: "1.4",  letterSpacing: "1.2px", fontWeight: "600" }],
        "code":       ["13.5px", { lineHeight: "1.6" }],
        "identifier": ["13px", { lineHeight: "1.4",  letterSpacing: "-0.2px", fontWeight: "500" }],
        "button":     ["14px", { lineHeight: "1",    fontWeight: "550" }],
        "nav-link":   ["14px", { lineHeight: "1.4",  fontWeight: "450" }],
      },
      borderRadius: {
        xs: "var(--ac-rounded-xs)",
        sm: "var(--ac-rounded-sm)",
        DEFAULT: "var(--ac-rounded-md)",
        md: "var(--ac-rounded-md)",
        lg: "var(--ac-rounded-lg)",
        chip: "var(--ac-rounded-chip)",
      },
      transitionTimingFunction: {
        micro: "cubic-bezier(0.2, 0, 0, 1)",
        standard: "cubic-bezier(0.2, 0, 0, 1)",
        entrance: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      transitionDuration: {
        micro: "120ms",
        standard: "200ms",
        entrance: "260ms",
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
