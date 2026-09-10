import type { Config } from 'tailwindcss';

/** KRDS 색 토큰(--krds-color-light-*)을 Tailwind 팔레트로 매핑한다. 5~95 단계. */
const STEPS = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95];
const krdsScale = (name: string, extra: number[] = []) =>
  Object.fromEntries(
    [...extra, ...STEPS].map((s) => [s, `var(--krds-color-light-${name}-${s})`]),
  ) as Record<string, string>;

export default {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        primary: { ...krdsScale('primary'), DEFAULT: 'var(--krds-color-light-primary-50)' },
        secondary: { ...krdsScale('secondary'), DEFAULT: 'var(--krds-color-light-secondary-50)' },
        gray: { ...krdsScale('gray', [0]), 100: 'var(--krds-color-light-gray-100)' },
        danger: { ...krdsScale('danger'), DEFAULT: 'var(--krds-color-light-danger-50)' },
        warning: { ...krdsScale('warning'), DEFAULT: 'var(--krds-color-light-warning-50)' },
        success: { ...krdsScale('success'), DEFAULT: 'var(--krds-color-light-success-50)' },
        info: {
          ...krdsScale('information'),
          DEFAULT: 'var(--krds-color-light-information-50)',
        },
        point: { ...krdsScale('point'), DEFAULT: 'var(--krds-color-light-point-50)' },
      },
      fontFamily: {
        sans: ['var(--krds-font-family-base)'],
        gov: ['Pretendard GOV', 'Pretendard', 'Noto Sans KR', 'sans-serif'],
      },
      /* 간격: KRDS gap 토큰 (gap-1=2px … gap-12=80px) */
      spacing: Object.fromEntries(
        Array.from({ length: 12 }, (_, i) => [`krds-${i + 1}`, `var(--krds-gap-${i + 1})`]),
      ),
      borderRadius: {
        'krds-xs': 'var(--krds-radius-xsmall1)',
        'krds-sm': 'var(--krds-radius-small1)',
        'krds-md': 'var(--krds-radius-medium1)',
        'krds-md2': 'var(--krds-radius-medium3)',
        'krds-lg': 'var(--krds-radius-large1)',
        'krds-xl': 'var(--krds-radius-xlarge1)',
        'krds-max': 'var(--krds-radius-max)',
      },
      boxShadow: {
        'krds-1': 'var(--krds-shadow-1)',
        'krds-2': 'var(--krds-shadow-2)',
        'krds-3': 'var(--krds-shadow-3)',
        /* v1 홈이 쓰는 그림자 */
        soft: '0 16px 48px rgba(18, 43, 36, .08)',
        card: '0 8px 28px rgba(15, 23, 42, .07)',
      },
    },
  },
  plugins: [],
} satisfies Config;
