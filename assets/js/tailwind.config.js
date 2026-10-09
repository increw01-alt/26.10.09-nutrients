/* Tailwind CDN 런타임 설정 — 브랜드 색상·폰트 (cdn.tailwindcss.com 로드 직후 실행) */
if (window.tailwind) {
  window.tailwind.config = {
    theme: {
      extend: {
        fontFamily: { sans: ["Pretendard Variable", "Pretendard", "-apple-system", "BlinkMacSystemFont", "system-ui", "Roboto", "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "sans-serif"] },
        colors: {
          brand: { 50: "#f0fdf9", 100: "#ccfbef", 200: "#99f6e0", 300: "#5eead4", 400: "#2dd4bf", 500: "#14b8a6", 600: "#0d9488", 700: "#0f766e", 800: "#115e59", 900: "#134e4a", 950: "#042f2e" },
          ink: { 50: "#f7f8f8", 100: "#eef0f1", 200: "#d9dde0", 300: "#b7bec4", 400: "#8d979f", 500: "#6b7680", 600: "#525c66", 700: "#3f474f", 800: "#2b3137", 900: "#1b2024", 950: "#101316" }
        },
        boxShadow: { card: "0 1px 2px rgba(16,19,22,.04), 0 8px 24px -12px rgba(16,19,22,.12)", lift: "0 12px 32px -12px rgba(13,148,136,.35)" },
        borderRadius: { "2xl": "1.25rem", "3xl": "1.75rem" }
      }
    }
  };
}
