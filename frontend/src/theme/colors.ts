/**
 * Cortex Color Palette Configuration
 * Derived from Google Stitch Design Specs & Design Tokens
 */
export const colors = {
  // Brand Primary & Accents
  amber: {
    50: '#FFFBEB',
    100: '#FEF3C7',
    200: '#FDE68A',
    300: '#FCD34D',
    400: '#FBBF24',
    500: '#F59E0B',
    600: '#D97706', // Primary Accent
    700: '#B45309',
    800: '#92400E',
    900: '#78350F',
    glow: 'rgba(217, 119, 6, 0.15)',
  },

  // Dark Slate & Grays
  slate: {
    50: '#F8FAFC',
    100: '#F1F5F9',
    200: '#E2E8F0',
    300: '#CBD5E1',
    400: '#94A3B8',
    500: '#64748B',
    600: '#475569',
    700: '#334155',
    800: '#1F2937', // Dark Slate Sidebar & Headers
    900: '#0F172A',
    950: '#030712',
  },

  // Neutrals & Backgrounds
  neutral: {
    bg: '#F3F4F6',        // Main Canvas Background
    cardBg: '#FFFFFF',    // KPI & Table Card Background
    border: '#E5E7EB',    // Border Dividers
    inputBg: '#F9FAFB',   // Input background
    hoverBg: '#F3F4F6',   // Hover item highlight
  },

  // Typography Colors
  text: {
    primary: '#111827',   // Main body & headings (#111827)
    secondary: '#4B5563', // Subheadings & labels
    muted: '#6B7280',     // Timestamps & metadata
    inverse: '#FFFFFF',   // Text on dark backgrounds
    active: '#B45309',    // Active state text
  },

  // Status Badges & Indicators
  status: {
    approved: {
      bg: '#DCFCE7',
      text: '#15803D',
      border: '#86EFAC',
    },
    pending: {
      bg: '#FEF3C7',
      text: '#B45309',
      border: '#FDE68A',
    },
    rejected: {
      bg: '#FEE2E2',
      text: '#B91C1C',
      border: '#FCA5A5',
    },
  },
} as const;

export type ColorsType = typeof colors;
