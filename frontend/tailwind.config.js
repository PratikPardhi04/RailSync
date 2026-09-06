/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        railway: {
          blue: '#123B66',
          darkblue: '#0B1F3A',
          accent: '#1D5FA7',
          light: '#F4F6F8',
          border: '#CBD5E1',
          success: '#18794E',
          warning: '#A15C00',
          danger: '#B3261E',
          muted: '#4B5563',
        },
        so: {
          bg: '#F4F6F8',
          panel: '#FFFFFF',
          panel2: '#F4F6F8',
          line: '#CBD5E1',
          line2: '#94A3B8',
          text: '#17202A',
          dim: '#4B5563',
          cyan: '#1D5FA7',
          violet: '#123B66',
          blue: '#1D5FA7',
          amber: '#A15C00',
          red: '#B3261E',
          green: '#18794E',
          signal: '#18794E',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        glow: '0 4px 16px -8px rgba(11, 31, 58, 0.35)',
        'glow-green': '0 4px 16px -8px rgba(24, 121, 78, 0.35)',
        'glow-amber': '0 4px 16px -8px rgba(161, 92, 0, 0.3)',
        'glow-red': '0 4px 16px -8px rgba(179, 38, 30, 0.35)',
      },
      keyframes: {
        'dash-flow': {
          to: { strokeDashoffset: '-24' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.9' },
          '100%': { transform: 'scale(1.9)', opacity: '0' },
        },
        'fade-rise': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'grid-drift': {
          from: { backgroundPosition: '0 0' },
          to: { backgroundPosition: '0 40px' },
        },
      },
      animation: {
        'dash-flow': 'dash-flow 0.9s linear infinite',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-rise': 'fade-rise 0.35s ease-out both',
        'grid-drift': 'grid-drift 40s linear infinite',
      },
    },
  },
  plugins: [],
}