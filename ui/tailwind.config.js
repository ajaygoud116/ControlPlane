/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],

  theme: {
    extend: {
      colors: {
        cp: {
          /*
           * =========================================================
           * CONTROLPLANE VISUAL SYSTEM
           *
           * Orange = environment
           * White  = workspace
           * Cream = secondary surfaces
           * Light red = intervention / attention
           * Brick  = severe decision
           * Black  = authority / text
           * =========================================================
           */

          // ---------------------------------------------------------
          // ENVIRONMENT
          // ---------------------------------------------------------
          bg: '#D36A32',
          'bg-dark': '#B94F22',
          'bg-light': '#E17C47',

          // ---------------------------------------------------------
          // WORKSPACE / SURFACES
          // ---------------------------------------------------------
          white: '#FFFFFF',

          surface: '#FFFFFF',
          'surface-2': '#FFF7F1',
          'surface-3': '#F2D7CC',

          // Alternate explicit names for semantic UI surfaces
          workspace: '#FFFFFF',
          'workspace-soft': '#FFF7F1',
          intervention: '#F2D7CC',

          // ---------------------------------------------------------
          // BORDERS
          // ---------------------------------------------------------
          border: '#E8DDD6',
          'border-strong': '#D8C7BD',
          'border-accent': '#D36A32',

          // ---------------------------------------------------------
          // TEXT
          // ---------------------------------------------------------
          text: '#171513',
          'text-secondary': '#625C57',
          'text-muted': '#948A83',
          'text-inverse': '#FFFFFF',

          // ---------------------------------------------------------
          // BRAND
          // ---------------------------------------------------------
          brand: '#171513',
          'brand-dark': '#000000',
          'brand-light': '#F2D7CC',

          // ---------------------------------------------------------
          // ORANGE ACCENT
          // ---------------------------------------------------------
          accent: '#D36A32',
          'accent-dim': '#B94F22',
          'accent-hover': '#C65B27',
          'accent-light': '#F7E1D7',

          // ---------------------------------------------------------
          // SEMANTIC DECISION COLORS
          // ---------------------------------------------------------

          // ALLOW — intentionally restrained green
          allow: '#376B43',

          // MODIFY — signal orange
          modify: '#C65A2D',

          // VERIFY — dark neutral / warm brown
          verify: '#72564A',

          // ESCALATE — orange-red
          escalate: '#C84D2F',

          // BLOCK — severe brick red
          block: '#7A2F2B',

          // UNKNOWN / UNAVAILABLE
          unknown: '#756D67',
          unavailable: '#948A83',

          // ---------------------------------------------------------
          // SOFT SEMANTIC BACKGROUNDS
          // ---------------------------------------------------------

          'allow-soft': '#EDF4ED',

          // Light red/orange intervention surface
          'modify-soft': '#F2D7CC',

          // Warm pale red
          'verify-soft': '#F5E6E1',

          // Light orange-red
          'escalate-soft': '#F6DDD3',

          // Strongest soft red surface
          'block-soft': '#F3D8D5',

          // Neutral secondary surface
          'unknown-soft': '#FFF7F1',

          // ---------------------------------------------------------
          // LEGACY ALIASES
          // ---------------------------------------------------------
          success: '#376B43',
          warning: '#C84D2F',
          danger: '#7A2F2B',
          info: '#171513',

          plum: '#72564A',
          'plum-light': '#F5E6E1',

          coral: '#C65A2D',
        },
      },

      // =============================================================
      // TYPOGRAPHY
      // =============================================================
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],

        display: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          'sans-serif',
        ],

        mono: [
          '"JetBrains Mono"',
          '"SFMono-Regular"',
          'Consolas',
          '"Liberation Mono"',
          'monospace',
        ],
      },

      fontSize: {
        'display-lg': [
          '2.5rem',
          {
            lineHeight: '1.1',
            letterSpacing: '-0.025em',
            fontWeight: '700',
          },
        ],

        display: [
          '2rem',
          {
            lineHeight: '1.2',
            letterSpacing: '-0.02em',
            fontWeight: '700',
          },
        ],

        'display-sm': [
          '1.5rem',
          {
            lineHeight: '1.25',
            letterSpacing: '-0.015em',
            fontWeight: '600',
          },
        ],

        'heading-lg': [
          '1.5rem',
          {
            lineHeight: '1.3',
            fontWeight: '600',
          },
        ],

        heading: [
          '1.25rem',
          {
            lineHeight: '1.35',
            fontWeight: '600',
          },
        ],

        'heading-sm': [
          '1.125rem',
          {
            lineHeight: '1.4',
            fontWeight: '500',
          },
        ],

        'body-lg': [
          '1rem',
          {
            lineHeight: '1.6',
          },
        ],

        body: [
          '0.9375rem',
          {
            lineHeight: '1.6',
          },
        ],

        'body-sm': [
          '0.875rem',
          {
            lineHeight: '1.5',
          },
        ],

        metadata: [
          '0.8125rem',
          {
            lineHeight: '1.4',
          },
        ],

        caption: [
          '0.75rem',
          {
            lineHeight: '1.4',
          },
        ],

        eyebrow: [
          '0.6875rem',
          {
            lineHeight: '1.4',
            letterSpacing: '0.1em',
            fontWeight: '600',
          },
        ],

        decision: [
          '2rem',
          {
            lineHeight: '1.1',
            letterSpacing: '-0.015em',
            fontWeight: '700',
          },
        ],

        'decision-sm': [
          '1.25rem',
          {
            lineHeight: '1.2',
            letterSpacing: '-0.005em',
            fontWeight: '600',
          },
        ],
      },

      // =============================================================
      // SPACING
      // =============================================================
      spacing: {
        18: '4.5rem',
        22: '5.5rem',

        sidebar: '15rem',
        inspector: '22.5rem',
      },

      // =============================================================
      // CORNERS
      //
      // Slightly restrained. Avoid overly rounded SaaS styling.
      // =============================================================
      borderRadius: {
        sm: '0.25rem',
        DEFAULT: '0.375rem',
        md: '0.5rem',
        lg: '0.625rem',
        xl: '0.75rem',
      },

      // =============================================================
      // SHADOWS
      //
      // Very subtle. The screenshot should feel flat and editorial,
      // not glossy or "glittering".
      // =============================================================
      boxShadow: {
        none: 'none',

        card: [
          '0 1px 2px rgba(23, 21, 19, 0.035)',
          '0 1px 1px rgba(23, 21, 19, 0.025)',
        ].join(', '),

        'card-hover': [
          '0 3px 8px rgba(23, 21, 19, 0.06)',
          '0 1px 2px rgba(23, 21, 19, 0.04)',
        ].join(', '),

        elevated: [
          '0 6px 18px rgba(23, 21, 19, 0.08)',
          '0 2px 5px rgba(23, 21, 19, 0.04)',
        ].join(', '),

        sidebar: '1px 0 4px rgba(23, 21, 19, 0.035)',

        intercept: [
          '0 0 0 1px rgba(211, 106, 50, 0.12)',
          '0 4px 12px rgba(23, 21, 19, 0.06)',
        ].join(', '),

        decision: [
          '0 0 0 1px rgba(122, 47, 43, 0.12)',
          '0 5px 16px rgba(23, 21, 19, 0.07)',
        ].join(', '),

        stage: 'inset 0 1px 2px rgba(23, 21, 19, 0.035)',

        ambient: [
          '0 8px 32px rgba(154, 62, 26, 0.18)',
          '0 2px 8px rgba(154, 62, 26, 0.08)',
          '0 0 0 1px rgba(255, 255, 255, 0.12)',
        ].join(', '),
      },

      // =============================================================
      // ANIMATIONS
      //
      // Kept deliberately quiet.
      // =============================================================
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
        'slide-up': 'slide-up 0.25s ease-out',
        'slide-in': 'slide-in 0.2s ease-out',

        'pulse-soft': 'pulse-soft 2.5s ease-in-out infinite',

        reveal: 'reveal 0.25s ease-out both',
        resolve: 'resolve 0.3s ease-out both',

        'rail-pulse': 'rail-pulse 2.5s ease-in-out infinite',
      },

      keyframes: {
        'fade-in': {
          from: {
            opacity: '0',
          },
          to: {
            opacity: '1',
          },
        },

        'slide-up': {
          from: {
            opacity: '0',
            transform: 'translateY(6px)',
          },
          to: {
            opacity: '1',
            transform: 'translateY(0)',
          },
        },

        'slide-in': {
          from: {
            opacity: '0',
            transform: 'translateX(-5px)',
          },
          to: {
            opacity: '1',
            transform: 'translateX(0)',
          },
        },

        'pulse-soft': {
          '0%, 100%': {
            opacity: '1',
          },
          '50%': {
            opacity: '0.65',
          },
        },

        reveal: {
          from: {
            opacity: '0',
            transform: 'translateY(4px)',
          },
          to: {
            opacity: '1',
            transform: 'translateY(0)',
          },
        },

        resolve: {
          from: {
            opacity: '0',
            transform: 'scale(0.98)',
          },
          to: {
            opacity: '1',
            transform: 'scale(1)',
          },
        },

        'rail-pulse': {
          '0%, 100%': {
            opacity: '0.35',
          },
          '50%': {
            opacity: '0.8',
          },
        },
      },

      transitionDuration: {
        250: '250ms',
        350: '350ms',
      },
    },
  },

  plugins: [],
};