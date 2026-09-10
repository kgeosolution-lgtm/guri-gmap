import type { Config } from 'tailwindcss';
export default {content:['./src/**/*.{js,ts,jsx,tsx,mdx}'],theme:{extend:{fontFamily:{sans:['var(--font-pretendard)','Pretendard','Noto Sans KR','sans-serif']},boxShadow:{soft:'0 16px 48px rgba(18, 43, 36, .08)',card:'0 8px 28px rgba(15, 23, 42, .07)'}}},plugins:[]} satisfies Config;
