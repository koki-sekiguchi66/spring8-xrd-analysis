/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Segoe UI"', '"Yu Gothic UI"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Cascadia Mono"', '"JetBrains Mono"', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
