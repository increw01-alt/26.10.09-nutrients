# 서플노트 (SuppleNote) — 영양제 정보 · 궁합 · 복용 시간표 사이트

영양제 성분별 효능·권장량·주의사항과 **영양제 간 궁합**, **하루 복용 시간표**를 제공하는 정적 정보 사이트입니다.
식약처(식품안전나라) 건강기능식품 신고 제품과 최신 뉴스를 **GitHub Actions 로 매일 자동 수집**하고,
쿠팡·11번가·G마켓·네이버쇼핑 링크를 **링크프라이스 / 쿠팡 파트너스 제휴 링크**로 연결해 수익화할 수 있습니다.

빌드 도구 없이 바로 열리는 정적 HTML + Tailwind CSS(CDN) + Vanilla JS 구조이며, Cloudflare Pages / GitHub Pages 에 그대로 배포됩니다.

## 폴더 구조

```
project/
├─ index.html                 # 홈 (검색, 빠른 궁합 체크, 인기 성분·궁합, 복용 가이드, 뉴스, FAQ)
├─ ingredients.html           # 성분 사전 목록 (분류·검색·태그 필터)
├─ ingredient.html            # 성분 상세 (JS 렌더링, ?id=vitamin-d)
├─ i/<id>.html                # 성분별 정적 상세 페이지 (SEO용, scripts/build_site.py 가 생성)
├─ compatibility.html         # 궁합 체크 (최대 8개 선택, 매트릭스, 복용 시간표, 공유 링크)
├─ products.html              # 제품 찾기 (식약처 신고 제품 + 쇼핑몰 링크 + 변경 이력)
├─ news.html                  # 뉴스·자료 (식약처/연구/뉴스 분류)
├─ about.html                 # 소개·데이터 출처·제휴 고지·면책
├─ 404.html
├─ robots.txt · sitemap.xml · .nojekyll
├─ assets/
│  ├─ css/style.css           # 공통 스타일 (배지·카드·매트릭스 등)
│  ├─ images/favicon.svg, og-default.svg
│  └─ js/
│     ├─ config.js            # ★ 브랜드명·도메인·제휴 ID 설정 (여기만 수정)
│     ├─ tailwind.config.js   # Tailwind CDN 색상·폰트 설정
│     ├─ data.js              # JSON 로더·검색·유틸
│     ├─ affiliate.js         # 쇼핑몰 링크/딥링크 생성
│     ├─ layout.js            # 헤더·푸터·검색 오버레이
│     ├─ schedule.js          # 복용 시간표 생성 로직
│     └─ pages/*.js           # 페이지별 스크립트
├─ data/
│  ├─ ingredients.json        # ★ 성분 사전 (37종) — 효능·권장량·시간·주의·FAQ
│  ├─ interactions.json       # ★ 궁합 데이터 (97쌍) — synergy/caution/avoid/neutral
│  ├─ products.json           # 식약처 신고 제품 (자동 수집, 현재 샘플)
│  ├─ news.json               # 뉴스 (자동 수집, 현재 샘플)
│  ├─ deeplinks.json          # 쿠팡 파트너스 딥링크 캐시
│  └─ meta.json               # 빌드·갱신 정보
├─ scripts/
│  ├─ fetch_products.py       # 식품안전나라 C003 API → products.json (+변경 이력)
│  ├─ fetch_news.py           # 구글 뉴스 RSS / 네이버 뉴스 API → news.json
│  ├─ build_affiliate_links.py# 쿠팡 파트너스 딥링크 생성 → deeplinks.json
│  ├─ build_site.py           # 데이터 검증 + i/*.html + sitemap.xml + meta.json
│  └─ common.py
├─ config/.env.example        # 로컬 실행용 환경변수 예시
├─ .github/workflows/
│  ├─ update-data.yml         # 매일 03:15 KST 자동 수집·빌드·커밋
│  └─ deploy-pages.yml        # GitHub Pages 배포 (Cloudflare 사용 시 삭제 가능)
├─ requirements.txt
└─ README.md
```

## 바로 실행하기

```bash
# 정적 사이트라 아무 웹서버로 열면 됩니다 (file:// 로는 JSON fetch 가 막히므로 서버 사용)
python3 -m http.server 8080
# → http://localhost:8080
```

Windows PowerShell 도 동일하게 `python -m http.server 8080` 으로 실행됩니다.

## 처음 설정 (5분)

1. **`assets/js/config.js`** 수정
   - `name`, `url`(실제 도메인), `contactEmail`
   - `linkprice.affiliateId` / `enabled: true`, 머천트 코드 확인
   - `coupang.enabled: true` (딥링크는 아래 스크립트가 생성)
   - 네이버 서치어드바이저·구글 서치콘솔 확인 코드
2. **도메인 연결 후** 임시 주소 `https://26-10-09-nutrients.pages.dev` 를 실제 도메인으로 일괄 치환
   ```bash
   grep -rl "26-10-09-nutrients.pages.dev" --include="*.html" --include="*.js" --include="*.txt" . | xargs sed -i 's#https://26-10-09-nutrients.pages.dev#https://your-domain.com#g'
   ```
   Cloudflare Pages 에서는 **Custom domains → Set up a custom domain** 으로 도메인을 추가하면 DNS·SSL 이 자동 설정되며, 기존 `pages.dev` 주소는 자동으로 새 도메인으로 리다이렉트되지 않으므로 치환 후 커밋이 필요합니다.
   (WSL/Linux 기준. 이후 `python scripts/build_site.py` 를 실행하면 `i/*.html` 과 `sitemap.xml` 은 자동 반영)
3. `about.html` 의 문의 이메일, `assets/images/og-default.svg` 교체(선택)

## 데이터 자동 업데이트

### API 키 발급
| 용도 | 발급처 | 환경변수 |
|---|---|---|
| 식약처 건강기능식품 신고 제품 (필수) | [식품안전나라 Open API](https://www.foodsafetykorea.go.kr/api/openApiInfo.do) → 서비스 `C003` 신청 | `FOODSAFETY_API_KEY` |
| 네이버 뉴스 (선택) | [네이버 개발자센터](https://developers.naver.com/apps) 검색 API | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| 쿠팡 파트너스 딥링크 (선택) | 쿠팡 파트너스 → 링크 생성 → API 키 | `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY` |

### GitHub Actions 설정
저장소 **Settings → Secrets and variables → Actions** 에서
- Secrets: `FOODSAFETY_API_KEY`, (선택) `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`
- Variables(선택): `SITE_URL`, `COUPANG_SUB_ID`, `FOODSAFETY_SERVICE`(기본 C003), `FOODSAFETY_MAX_ROWS`(기본 15000)

`update-data.yml` 이 매일 03:15 KST 에 실행되어 뉴스 → 제품 → 딥링크 → 정적 페이지 순으로 갱신하고 변경이 있을 때만 커밋합니다.
Actions 탭에서 **Run workflow** 로 즉시 실행할 수도 있습니다. 키가 없는 단계는 건너뛰며 기존 데이터를 유지합니다.

### 로컬에서 수동 실행
```bash
pip install -r requirements.txt
cp config/.env.example .env   # 값 입력 후
set -a; source .env; set +a   # (Windows PowerShell: $env:FOODSAFETY_API_KEY="...")
python scripts/fetch_news.py
python scripts/fetch_products.py
python scripts/build_affiliate_links.py
python scripts/build_site.py
```

### 제품 변경 추적
`fetch_products.py` 는 식약처 API 가 느리고(1,000건당 20~40초) 키당 동시 요청 1개만 허용하므로, 최신 신고분부터 거꾸로 `FOODSAFETY_MAX_ROWS`(기본 15,000건)만 순차 수집합니다. 이전 `products.json` 과 신고번호 기준으로 비교해 **신규 / 변경(제품명·기능성·원재료·주의사항) / 삭제** 를 `changelog` 에 기록하고, 제품 찾기 페이지 상단에 건수와 이력을 표시합니다.

## 제휴 링크 동작 방식
- `assets/js/affiliate.js` 가 각 성분·제품의 검색어로 쇼핑몰 검색 URL 을 만들고
  - 링크프라이스 머천트(11번가·G마켓·옥션)는 `click.linkprice.com` 딥링크로 감쌉니다 (`config.js` 의 `buildUrl` 형식은 링크프라이스 관리자 "딥링크 생성" 형식과 맞춰 주세요).
  - 쿠팡은 `data/deeplinks.json` 에 생성된 파트너스 단축 링크가 있으면 사용하고, 없으면 일반 검색 링크로 연결합니다.
- 모든 쇼핑 링크는 `rel="nofollow sponsored noopener"` 이며, 푸터·소개·제품 영역에 쿠팡 파트너스 필수 고지 문구가 포함되어 있습니다.

## 성분·궁합 데이터 수정
- 성분 추가: `data/ingredients.json` 의 `items` 에 항목 추가 (필수 키: id, name, en, category, summary, benefits, dosage, timing, cautions, shopQuery, tags) → `python scripts/build_site.py` 로 정적 페이지 생성
- 궁합 추가: `data/interactions.json` 의 `pairs` 에 `{"pair":[a,b],"type":"synergy|caution|avoid|neutral","title","detail","tip","separateHours"}`
- `build_site.py` 가 ID 참조·중복·분류 오류를 검증합니다.

## 배포
### Cloudflare Pages (권장)
- Git 연결 → Build command: **(비움)** → Build output directory: **`/`**
- 환경변수 불필요 (데이터 갱신은 GitHub Actions 가 커밋하면 자동 재배포)
### GitHub Pages
- Settings → Pages → Source: **GitHub Actions** → `deploy-pages.yml` 이 `main` 푸시마다 배포
- 프로젝트 페이지(`/repo/`) 경로로 쓰는 경우 `404.html` 의 절대 경로(`/assets/...`)만 상대 경로로 바꿔 주세요.

## 검색엔진 등록
- `sitemap.xml` 을 구글 서치콘솔·네이버 서치어드바이저에 제출
- `config.js` 의 `naverSiteVerification` / `googleSiteVerification` 에 확인 코드 입력

## 주의
- 성분 정보는 식약처 기능성 고시·한국인 영양소 섭취기준(2020)을 참고해 일반 성인 기준으로 요약한 것으로 의학적 조언이 아닙니다. 수치·문구는 공개 전 한 번 더 검토를 권장합니다.
- `data/products.json`, `data/news.json` 은 현재 **샘플** 상태이며 키 설정 후 첫 수집 시 실제 데이터로 교체됩니다 (화면에 샘플 표시 배너가 자동으로 사라집니다).
