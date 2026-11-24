/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        nexus: {
          canvas: "#0A0E17",
          card: "#111827",
          border: "#1F2937",
          cyan: "#06B6D4",
          blue: "#3B82F6",
          violet: "#8B5CF6",
        },
      },
      boxShadow: {
        "neon-cyan": "0 0 0 1px rgba(6,182,212,0.5), 0 0 18px rgba(6,182,212,0.18)",
        "neon-blue": "0 0 0 1px rgba(59,130,246,0.5), 0 0 18px rgba(59,130,246,0.18)",
      },
    },
  },
  plugins: [],
};
