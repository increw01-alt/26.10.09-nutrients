/* Tailwind CDN 런타임 설정 — 브랜드 색상·폰트 (cdn.tailwindcss.com 로드 직후 실행)
 * 색 체계: 포레스트 그린(brand) + 크림(cream) + 따뜻한 중립색(ink) */
if (window.tailwind) {
  window.tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ["Pretendard Variable", "Pretendard", "-apple-system", "BlinkMacSystemFont", "system-ui", "Roboto", "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "sans-serif"], hand: ["Nanum Pen Script", "cursive"] },
        colors: {
          brand: { 50: "#f1f7f2", 100: "#e2efe4", 200: "#c5dfc9", 300: "#9cc6a4", 400: "#6ea87a", 500: "#4b8c59", 600: "#3a7d44", 700: "#2f6538", 800: "#27512f", 900: "#1f4027", 950: "#102315" },
          cream: { 50: "#fdfcf9", 100: "#faf8f2", 200: "#f3efe6", 300: "#ebe5d8", 400: "#ddd4c2" },
          peach: { 50: "#fdf4ee", 100: "#fbe9dc", 200: "#f7d7c2", 300: "#f0bfa0" },
          ink: { 50: "#f7f7f5", 100: "#efeeea", 200: "#dedcd6", 300: "#bdb9b0", 400: "#8f8b82", 500: "#6b675f", 600: "#524f48", 700: "#3f3d37", 800: "#2b2a26", 900: "#1c1b18", 950: "#111110" }
        },
        boxShadow: { card: "0 1px 2px rgba(28,27,24,.04), 0 10px 30px -14px rgba(28,27,24,.14)", lift: "0 12px 30px -12px rgba(58,125,68,.45)", soft: "0 20px 50px -24px rgba(28,27,24,.25)" },
        borderRadius: { "2xl": "1.25rem", "3xl": "1.75rem", "4xl": "2.25rem" }
      }
    }
  };
}
