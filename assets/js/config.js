/* =========================================================
 * 사이트 전역 설정 — 실제 정보로 교체해서 사용하세요.
 * (이 파일만 수정하면 브랜드명·도메인·제휴 ID가 전체 페이지에 반영됩니다)
 * ========================================================= */
window.SITE = {
  name: "영양제.kr",                             // 브랜드명 (도메인과 동일하게 사용)
  nameEn: "yeongyangje.kr",
  tagline: "영양제 추천 · 궁합 · 복용 가이드",
  url: "https://xn--og5b1hx9c.kr",             // 영양제.kr (퓨니코드 표기 — canonical·OG·sitemap에 사용)
  description: "영양제 추천 성분, 영양제 궁합, 먹는 시간과 순서까지. 성분별 효능·권장량·주의사항과 식약처 건강기능식품 정보, 고민별·대상별 영양제 가이드를 제공합니다.",
  contactEmail: "contact@example.com",           // TODO: 문의 이메일
  ogImage: "assets/images/og-default.svg",       // 소셜 공유 썸네일 (PNG 1200x630 권장, 교체 가능)
  // 검색엔진 소유 확인 메타태그 값 (없으면 빈 문자열 유지)
  naverSiteVerification: "ea7f0a747323533a9bc41af6ff79b0e82413bfd6",                     // 네이버 서치어드바이저 HTML 태그의 content 값 → python scripts/build_site.py 실행 시 index.html 에 삽입
  googleSiteVerification: ""                     // 구글 서치콘솔 HTML 태그의 content 값 (DNS 방식으로 확인했다면 비워 둬도 됨)
};

/* ---------------------------------------------------------
 * 제휴(어필리에이트) 설정
 *  - 링크프라이스: affiliateId(A로 시작하는 ID)와 머천트 코드를 입력하면
 *    11번가·G마켓·옥션 링크가 자동으로 딥링크로 감싸집니다.
 *    머천트 코드는 링크프라이스 관리자 > 머천트 목록에서 확인 후 수정하세요.
 *  - 쿠팡 파트너스: scripts/build_affiliate_links.py 가 API로 딥링크를 생성해
 *    data/deeplinks.json 에 저장합니다. (키 없으면 일반 검색 링크로 연결)
 * --------------------------------------------------------- */
window.AFFILIATE = {
  linkprice: {
    enabled: false,                              // TODO: 링크프라이스 승인 후 true
    affiliateId: "A100000000",                   // TODO: 링크프라이스 어필리에이트 ID
    // 머천트 코드 (링크프라이스 머천트 목록 기준으로 확인·수정)
    merchants: {
      "11st": "11st",
      "gmarket": "gmarket",
      "auction": "auction"
    },
    // 링크프라이스 딥링크 형식 — 관리자 페이지의 '딥링크 생성' 형식과 다르면 여기만 수정
    buildUrl: function (merchantCode, targetUrl) {
      return "https://click.linkprice.com/click.php?m=" + encodeURIComponent(merchantCode) +
        "&a=" + encodeURIComponent(window.AFFILIATE.linkprice.affiliateId) +
        "&l=9999&l_cd1=3&l_cd2=0&tu=" + encodeURIComponent(targetUrl);
    }
  },
  coupang: {
    enabled: false,                              // TODO: 쿠팡 파트너스 승인 후 true (딥링크는 스크립트로 생성)
    subId: "yeongyangje"                          // 서브 ID (채널 구분용)
  },
  // 표시할 쇼핑몰 목록 (순서대로 버튼 노출). searchUrl 은 검색어로 상품 목록을 여는 주소
  shops: [
    { key: "coupang", label: "쿠팡", short: "쿠팡", color: "#e5322d", network: "coupang",
      searchUrl: function (q) { return "https://www.coupang.com/np/search?q=" + encodeURIComponent(q); } },
    { key: "11st", label: "11번가", short: "11번가", color: "#ff0038", network: "linkprice",
      searchUrl: function (q) { return "https://search.11st.co.kr/Search.tmall?kwd=" + encodeURIComponent(q); } },
    { key: "gmarket", label: "G마켓", short: "G마켓", color: "#00c73c", network: "linkprice",
      searchUrl: function (q) { return "https://browse.gmarket.co.kr/search?keyword=" + encodeURIComponent(q); } },
    { key: "naver", label: "네이버쇼핑", short: "네이버", color: "#03c75a", network: null,
      searchUrl: function (q) { return "https://search.shopping.naver.com/search/all?query=" + encodeURIComponent(q); } }
  ],
  // 제휴 고지 문구 (쿠팡 파트너스 운영 정책상 필수 문구 포함)
  disclosure: "이 사이트는 쿠팡 파트너스 및 링크프라이스 등 제휴 마케팅 활동의 일환으로, 구매 시 일정액의 수수료를 제공받을 수 있습니다. 수수료는 구매 가격에 영향을 주지 않습니다."
};
