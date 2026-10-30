/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#080504", 900: "#0e0906", 800: "#150d09", 700: "#1f130d", 600: "#2b1a11" },
        ember: { 400: "#ff8a2a", 500: "#ff6a00", 600: "#e14d00", 700: "#b53a00" },
        gold: { 300: "#ffe08a", 400: "#ffc94d", 500: "#f5a91c" },
      },
      fontFamily: {
        display: ["Impact", "Haettenschweiler", "Arial Narrow Bold", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(255,106,0,.35)",
      },
    },
  },
  plugins: [],
};
