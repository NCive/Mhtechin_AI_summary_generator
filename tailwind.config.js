/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        chatmeet: {
          primary: '#5932ea',
          hover: '#4a27d6',
          light: '#f4f0ff',
          border: '#e2d8fe',
          bg: '#f3f4fa',
          dark: '#141522',
          sub: '#71758c',
          muted: '#9da1b4',
        },
      },
    },
  },
  plugins: [],
}
