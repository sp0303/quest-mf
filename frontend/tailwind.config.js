/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f5f5f5",
        paper: "#ffffff",
        "surface-alt": "#fafafa",
        ink: "#0a0a0a",
        "ink-soft": "#171717",
        "mid-gray": "#666666",
        hairline: "#e5e5e5",
        ember: "#e7000b",
      },
      borderRadius: {
        "2xl": "18px",
        "3xl": "24px",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      boxShadow: {
        subtle: "0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
}
