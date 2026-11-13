export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'var(--color-surface)',
        'surface-container': 'var(--color-surface-container)',
        'surface-container-low': 'var(--color-surface-container-low)',
        'surface-tint': 'var(--color-surface-tint)',
        foreground: 'var(--color-on-surface)',
        'foreground-muted': 'var(--color-on-surface-variant)',
        border: 'var(--color-outline-variant)',
        primary: 'var(--color-primary)',
        'on-primary': 'var(--color-on-primary)',
        'primary-container': 'var(--color-primary-container)',
        secondary: 'var(--color-secondary)',
        'status-error': 'var(--color-error)',
        'status-success': 'var(--color-status-success)',
        'status-warning': 'var(--color-status-warning)',
        'status-info': 'var(--color-status-info)',
      },
      fontFamily: {
        sans: ['Public Sans', 'sans-serif'],
      },
      borderRadius: {
        sm: '0.125rem',
        DEFAULT: '0.25rem',
        md: '0.375rem',
        lg: '0.5rem',
        xl: '0.75rem',
      },
      maxWidth: {
        shell: '1280px',
      },
    },
  },
  plugins: [],
};
