/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-base': '#030712',
        'bg-surface': '#0B1021',
        'bg-elevated': '#111827',
        'bg-input': '#1A2332',
        'border-subtle': '#1E293B',
        'border-active': '#334155',
        'accent-primary': '#06B6D4',
        'accent-primary-dim': '#083344',
        'accent-secondary': '#8B5CF6',
        'accent-success': '#10B981',
        'accent-warning': '#F59E0B',
        'accent-danger': '#EF4444',
        'accent-info': '#3B82F6',
        'text-primary': '#F8FAFC',
        'text-secondary': '#94A3B8',
        'text-tertiary': '#475569',
      },
      fontFamily: {
        inter: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'card': '12px',
        'panel': '16px',
      },
    },
  },
  plugins: [],
}
