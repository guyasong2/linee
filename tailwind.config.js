/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  safelist: ["form-input", "form-select", "form-checkbox"],
  theme: {
    extend: {
      colors: {
        ink: "#142c3a",
        navy: "#0f3b57",
        sand: "#ffffff",
        mist: "#f2f8fb",
        line: "#dce7ee",
        brand: {
          50: "#f2f8fc",
          100: "#e4f1f8",
          200: "#c9e3f1",
          300: "#a3cfe5",
          400: "#78b4d3",
          500: "#4a89ac",
          600: "#3d7595",
          700: "#315f7a",
          800: "#2a4e63",
          900: "#203e50",
          950: "#122e40",
        },
        aqua: "#ace5f6",
      },
      fontFamily: {
        sans: [
          "Poppins",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        display: [
          "Poppins",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 0 rgba(15,59,87,0.03), 0 18px 45px -30px rgba(15,59,87,0.35)",
        hero: "0 40px 90px -40px rgba(0,0,0,0.55)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
      maxWidth: {
        "8xl": "90rem",
      },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/typography")],
};
