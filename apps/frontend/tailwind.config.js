/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0a0a0a',
          panel: '#0d0d0d',
          card: '#111111',
          border: '#1a3a1a',
          green: '#00ff41',
          'green-muted': '#4ade80',
          'green-dim': '#166534',
          cyan: '#22d3ee',
          red: '#ef4444',
          yellow: '#eab308',
          text: '#d4d4d4',
          'text-dim': '#737373',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-green': 'pulse-green 2s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        'pulse-green': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'glow': {
          '0%': { boxShadow: '0 0 5px rgba(0, 255, 65, 0.2)' },
          '100%': { boxShadow: '0 0 15px rgba(0, 255, 65, 0.4)' },
        },
        'blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
