/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Segoe UI"', '"Yu Gothic UI"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Cascadia Mono"', '"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      colors: {
        obsidian: {
          canvas: '#0d0e11',
          chrome: '#121418',
          surface: '#16181d',
          elevated: '#1c1f26',
          inset: '#0a0b0e',
          border: '#23262e',
          'border-strong': '#313642',
        },
      },
    },
  },
  plugins: [],
};
