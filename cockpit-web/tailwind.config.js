/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        onyx: {
          900: "#090d16",
          800: "#0f172a",
          700: "#1e293b",
          600: "#334155",
        },
        cobalt: {
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        sky: {
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
        },
        indigo: {
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
        },
        emerald: {
          400: "#34d399",
          500: "#10b981",
        }
      },
    },
  },
  plugins: [],
};
