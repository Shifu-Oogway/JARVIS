import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070A12",
        panel: "#0D1320",
        edge: "#1B2436",
        muted: "#5C6B86",
        text: "#C7D2E4",
        live: "#34E0D4",     // cyan — reserved for live / active state only
        surge: "#7C5CFF",    // violet — secondary signature accent
        warn: "#F2B84B",
        bad: "#FF5C72",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
