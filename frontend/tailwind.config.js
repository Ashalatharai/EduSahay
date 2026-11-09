export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: { navy: '#163B65', accent: '#16A6A1', mist: '#F4F7FA', ink: '#263445' },
      fontFamily: { sans: ['"Public Sans"', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(22,59,101,.06), 0 4px 16px rgba(22,59,101,.06)' },
    },
  },
  plugins: [],
}
