/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0B2545", 50: "#EEF2F8", 600: "#12345F", 700: "#0B2545", 900: "#061530" },
        teal: { DEFAULT: "#0E8C82", 50: "#E7F6F4", 100: "#CFEEEA", 500: "#0E8C82", 600: "#0B7169", 700: "#095A54" },
        amber: { 500: "#E2933B" },
        coral: { 500: "#D9584F" },
      },
      fontFamily: {
        display: ["'Fraunces'", "serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      boxShadow: { card: "0 1px 2px rgba(11,37,69,0.06), 0 1px 0 rgba(11,37,69,0.04)" },
    },
  },
  plugins: [],
};
