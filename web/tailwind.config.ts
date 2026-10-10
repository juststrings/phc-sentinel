import type { Config } from "tailwindcss";

// All colours are CSS variables (app/globals.css) so dark mode is a pure variable swap.
const v = (name: string) => `var(--${name})`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"),
        card: v("card"),
        muted: v("muted-bg"),
        line: v("line"),
        ink: v("ink"),
        "ink-2": v("ink-2"),
        "ink-3": v("ink-3"),
        brand: v("brand"),
        "act-now": { DEFAULT: v("q-act-fg"), bg: v("q-act-bg"), bd: v("q-act-bd") },
        "verify-then-act": { DEFAULT: v("q-verify-fg"), bg: v("q-verify-bg"), bd: v("q-verify-bd") },
        "do-not-assume-safe": { DEFAULT: v("q-dnas-fg"), bg: v("q-dnas-bg"), bd: v("q-dnas-bd") },
        monitor: { DEFAULT: v("q-monitor-fg"), bg: v("q-monitor-bg"), bd: v("q-monitor-bd") },
      },
      fontFamily: { sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"] },
      borderRadius: { DEFAULT: "4px", lg: "6px", xl: "8px" },
      fontSize: {
        "label-sm": ["11px", { lineHeight: "14px", letterSpacing: "0.05em", fontWeight: "600" }],
        "label-md": ["13px", { lineHeight: "18px", letterSpacing: "0.01em", fontWeight: "500" }],
        metric: ["28px", { lineHeight: "32px", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
    },
  },
  plugins: [],
};
export default config;
