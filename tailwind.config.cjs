/* Tailwind 정적 빌드 설정 — `npm run css` 가 assets/css/tailwind.css 를 생성한다 (런타임 CDN 사용 안 함)
 * 색 체계: 메인 시안과 같은 딥 그린(brand) + 연한 민트·크림(cream) + 녹색 기운의 중립색(ink) */
module.exports = {
  content: ["./*.html", "./i/*.html", "./guide/*.html", "./function/*.html", "./compare/*.html", "./drug-guide/*.html", "./term/*.html", "./assets/js/**/*.js", "./scripts/build_site.py"],
  theme: {
    extend: {
      fontFamily: { sans: ["Pretendard Variable", "Pretendard", "-apple-system", "BlinkMacSystemFont", "system-ui", "Roboto", "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "sans-serif"], hand: ["Nanum Pen Script", "cursive"] },
      colors: {
        brand: { 50: "#eff5ec", 100: "#dfedd7", 200: "#c5dcbf", 300: "#9cc49c", 400: "#6ea678", 500: "#3f8a5a", 600: "#246d4b", 700: "#1e5c3f", 800: "#175136", 900: "#12402b", 950: "#0b2619" },
        cream: { 50: "#fbfbf6", 100: "#f8faf5", 200: "#f3f6ee", 300: "#ebefe3", 400: "#dfe6d6" },
        peach: { 50: "#fdf7ef", 100: "#faf3ea", 200: "#f5e4d2", 300: "#efcfae" },
        ink: { 50: "#f6f7f3", 100: "#e6ebe2", 200: "#d3dacd", 300: "#aeb8a8", 400: "#8a9684", 500: "#647368", 600: "#4d5b4f", 700: "#3a463c", 800: "#27322a", 900: "#19241f", 950: "#0f1612" }
      },
      boxShadow: { card: "0 1px 2px rgba(25,36,31,.04), 0 10px 30px -14px rgba(25,36,31,.12)", lift: "0 10px 24px -10px rgba(36,109,75,.45)", soft: "0 20px 50px -24px rgba(25,36,31,.22)" },
      borderRadius: { "2xl": "1rem", "3xl": "1.375rem", "4xl": "1.75rem" }
    }
  }
};
