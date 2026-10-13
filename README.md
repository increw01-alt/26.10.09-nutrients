# 영양제.kr — 영양제 추천 · 궁합 · 복용 가이드 사이트

**https://영양제.kr** (퓨니코드 `https://xn--og5b1hx9c.kr`) · Cloudflare Pages 배포

영양제 성분별 효능·권장량·주의사항과 **영양제 간 궁합**, **하루 복용 시간표**, **고민별·대상별·복용법 가이드**를 제공하는 정적 정보 사이트입니다.
식약처(식품안전나라) 건강기능식품 신고 제품·기능성 원료 인정현황과 최신 뉴스를 **GitHub Actions 로 매일 자동 수집**하고,
쿠팡·11번가·G마켓·네이버쇼핑 링크를 **링크프라이스 / 쿠팡 파트너스 제휴 링크**로 연결해 수익화할 수 있습니다.

빌드 도구 없이 바로 열리는 정적 HTML + Tailwind CSS(CDN) + Vanilla JS 구조이며, 성분·가이드 페이지는 Python 스크립트가 JSON 데이터에서 생성합니다.

> 현재 상태·설정 현황·작업 이력·다음 할 일은 [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) 에 정리되어 있습니다.

## 폴더 구조

```
project/
├─ index.html                 # 홈 (검색, 빠른 궁합 체크, 인기 성분·궁합, 복용 가이드, 뉴스, FAQ)
├─ ingredients.html           # 성분 사전 목록 (분류·검색·태그 필터)
├─ ingredient.html            # 성분 상세 (JS 렌더링, ?id=vitamin-d)
├─ i/<id>.html                # 성분별 정적 상세 페이지 (SEO용, scripts/build_site.py 가 생성)
├─ compatibility.html         # 궁합 체크 (최대 8개 선택, 매트릭스, 복용 시간표, 공유 링크)
├─ guides.html                # 영양제 가이드 허브 (scripts/build_site.py 가 생성)
├─ guide/<slug>.html          # 고민별·대상별·복용법 가이드 28개 (data/guides.json 에서 생성)
├─ products.html              # 제품 찾기 (식약처 신고 제품 + 쇼핑몰 링크 + 변경 이력)
├─ news.html                  # 뉴스·자료 (식약처/연구/뉴스 분류)
├─ materials.html             # 식약처 기능성 원료 인정현황 (검색·성분 필터)
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
│  ├─ guides.json             # ★ 가이드 콘텐츠 (고민별 12 · 대상별 9 · 복용법·안전 7)
│  ├─ products.json           # 식약처 신고 제품 목록 (자동 수집, 압축 JSON)
│  ├─ products/top/<id>.json  # 성분별 상위 60개 제품 (성분 상세 페이지)
│  ├─ products/detail/NN.json # 전체 신고 정보 64조각 (제품 '더보기' 펼칠 때 로드)
│  ├─ news.json               # 뉴스 (자동 수집)
│  ├─ materials.json          # 식약처 기능성 원료 인정현황 (자동 수집)
│  ├─ materials/<id>.json     # 성분별 관련 원료 (성분 상세 페이지)
│  ├─ deeplinks.json          # 쿠팡 파트너스 딥링크 캐시
│  └─ meta.json               # 빌드·갱신 정보
├─ scripts/
│  ├─ fetch_products.py       # 식품안전나라 C003 API → products.json (+변경 이력)
│  ├─ fetch_news.py           # 구글 뉴스 RSS / 네이버 뉴스 API → news.json
│  ├─ fetch_materials.py      # 식약처 기능성 원료(I-0040·I-0050) → materials.json
│  ├─ build_affiliate_links.py# 쿠팡 파트너스 딥링크 생성 → deeplinks.json
│  ├─ build_site.py           # 데이터 검증 + i/*.html + sitemap.xml + meta.json
│  └─ common.py
├─ config/.env.example        # 로컬 실행용 환경변수 예시
├─ .github/workflows/
│  ├─ update-data.yml         # 매일 03:15 KST 자동 수집·빌드·커밋
│  └─ deploy-pages.yml        # GitHub Pages 배포 (Cloudflare 사용 시 삭제 가능)
├─ requirements.txt
├─ docs/PROJECT-STATUS.md     # 프로젝트 현황·작업 이력 정리
├─ CLAUDE.md                  # Claude Code 작업 지침
├─ dev.ps1 · dev.bat · dev.sh # 로컬 개발 서버 실행 스크립트 (Windows / WSL·mac)
└─ README.md
```

## 로컬 개발 환경 만들기 (Windows)

1. [Git](https://git-scm.com/download/win) 과 [Python 3.12+](https://www.python.org/downloads/) 설치 (Python 설치 시 "Add python.exe to PATH" 체크)
2. PowerShell 에서 원하는 상위 폴더로 이동해 복제
   ```powershell
   cd "C:\Users\OK\Desktop\블로그이미지"
   git clone https://github.com/increw01-alt/26.10.09-nutrients.git "26.10.12 영양제.kr"
   cd "26.10.12 영양제.kr"
   ```
3. 로컬 서버 실행 — 폴더의 `dev.bat` 을 더블클릭하거나 PowerShell 에서 `.\dev.ps1` (브라우저가 http://localhost:8080 으로 열립니다)
4. (선택) 디자인 클래스나 아이콘을 바꿀 때만 [Node.js](https://nodejs.org/) 가 필요합니다: 폴더에서 `npm ci` 한 번, 이후 `npm run assets` 로 `assets/css/tailwind.css` 와 `assets/js/icons.js` 를 재생성한 뒤 `dev.bat build` 를 실행합니다. Node 가 없어도 push 하면 GitHub Actions(`build-assets.yml`)가 자동으로 만들어 커밋합니다.
   - 데이터를 고친 뒤에는 `.\dev.ps1 -Build` (또는 `dev.bat build`) 로 성분·가이드 페이지를 다시 생성
   - WSL2 Ubuntu·macOS 에서는 `./dev.sh --build`
4. 수정 → 확인 → 커밋 → 푸시하면 Cloudflare Pages 가 자동 배포합니다
   ```powershell
   git add -A
   git commit -m "feat: 변경 내용"
   git push
   ```
   자동 수집 커밋이 매일 원격에 쌓이므로 작업 시작 전 `git pull` 을 먼저 하세요.

정적 사이트라 아무 웹서버로 열면 됩니다. `file://` 로 직접 열면 JSON 불러오기가 막히므로 꼭 서버로 여세요.

### Claude Code 로 이어서 작업하기
이 폴더에서 Claude Code(데스크톱 앱 또는 `claude` CLI)를 실행하면 `CLAUDE.md` 의 작업 지침과 `docs/PROJECT-STATUS.md` 의 현황을 읽고 바로 이어서 작업할 수 있습니다.

## 처음 설정 (5분)

1. **`assets/js/config.js`** 수정
   - `name`, `url`(실제 도메인), `contactEmail`
   - `linkprice.affiliateId` / `enabled: true`, 머천트 코드 확인
   - `coupang.enabled: true` (딥링크는 아래 스크립트가 생성)
   - 네이버 서치어드바이저·구글 서치콘솔 확인 코드
2. **도메인**: 현재 `영양제.kr`(퓨니코드 `https://xn--og5b1hx9c.kr`) 기준으로 canonical·OG·sitemap 이 설정되어 있습니다. 도메인을 바꾸려면 아래처럼 일괄 치환한 뒤 `python scripts/build_site.py` 를 실행하세요.
   ```bash
   grep -rl "xn--og5b1hx9c.kr" --include="*.html" --include="*.js" --include="*.txt" --include="*.py" . | xargs sed -i 's#https://xn--og5b1hx9c.kr#https://your-domain.com#g'
   ```
   한글 도메인은 검색엔진·소셜 공유 호환을 위해 퓨니코드(ASCII) 형태로 적는 것이 안전합니다. 사용자에게 보이는 문구에는 `영양제.kr` 을 그대로 씁니다.
3. `about.html` 의 문의 이메일, `assets/images/og-default.svg` 교체(선택)

## 데이터 자동 업데이트

### API 키 발급
| 용도 | 발급처 | 환경변수 |
|---|---|---|
| 식약처 건강기능식품 신고 제품·기능성 원료 (필수) | [식품안전나라 Open API](https://www.foodsafetykorea.go.kr/api/openApiInfo.do) → 서비스 `C003`, `I-0040`, `I-0050` 신청 | `FOODSAFETY_API_KEY` |
| 식약처 의약품 정보 — 제품명 검색·의약품 페이지 (선택) | [공공데이터포털](https://www.data.go.kr) 회원가입 → **식품의약품안전처_의약품개요정보(e약은요)** 와 **식품의약품안전처_의약품 제품 허가정보** 를 각각 활용신청(개발계정은 즉시 승인) → 마이페이지 → 일반 인증키(Decoding) | `DATA_GO_KR_KEY` |
| 네이버 뉴스 (선택) | [네이버 개발자센터](https://developers.naver.com/apps) 검색 API | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| 쿠팡 파트너스 딥링크 (선택) | 쿠팡 파트너스 → 링크 생성 → API 키 | `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY` |

### GitHub Actions 설정
저장소 **Settings → Secrets and variables → Actions** 에서
- Secrets: `FOODSAFETY_API_KEY`, (선택) `DATA_GO_KR_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `COUPANG_ACCESS_KEY`, `COUPANG_SECRET_KEY`
- Variables(선택): `SITE_URL`, `COUPANG_SUB_ID`, `FOODSAFETY_SERVICE`(기본 C003), `FOODSAFETY_MAX_ROWS`(기본 15000), `DRUG_API_BUDGET`(실행당 의약품 API 호출 상한, 기본 900), `DRUG_EASY_SERVICE`·`DRUG_PERMIT_SERVICE`(공공데이터포털 API 경로가 바뀌었을 때만)

`update-data.yml` 이 매일 03:15 KST 에 실행되어 뉴스 → 기능성 원료 → 제품 → 의약품 → 딥링크 → 정적 페이지 순으로 갱신하고 변경이 있을 때만 커밋합니다.
Actions 탭에서 **Run workflow** 로 즉시 실행할 수도 있습니다. 키가 없는 단계는 건너뛰며 기존 데이터를 유지합니다.

### 로컬에서 수동 실행
```bash
pip install -r requirements.txt
cp config/.env.example .env   # 값 입력 후
set -a; source .env; set +a   # (Windows PowerShell: $env:FOODSAFETY_API_KEY="...")
python scripts/fetch_news.py
python scripts/fetch_products.py
python scripts/fetch_drugs.py        # DATA_GO_KR_KEY 가 있을 때 (또는 --rebuild)
python scripts/build_affiliate_links.py
python scripts/build_site.py
```

### 제품 데이터 파일 구조
- `data/products.json`: 제품 찾기 페이지용 가벼운 목록(이름·업체·신고일·제형·성분·기능성 요약)
- `data/products/top/<성분id>.json`: 성분 상세 페이지용 상위 60개(제품명에 성분이 드러나는 단일 목적 제품 우선)
- `data/products/detail/<00~63>.json`: 전체 신고 정보(원재료·섭취방법·주의사항 등). 제품 id 해시로 조각을 나누며 `assets/js/data.js`의 `productShard()`와 스크립트의 `shard_of()`가 같은 계산을 씁니다.
- 매칭 규칙을 바꾼 뒤에는 `python scripts/fetch_products.py --rebuild` 로 API 호출 없이 저장된 레코드로 다시 생성할 수 있습니다.

### 의약품 데이터 (`scripts/fetch_drugs.py`)
- 공공데이터포털의 **e약은요(의약품개요정보)** 전체(일반의약품 중심 약 4,700건: 효능·사용법·경고·주의사항·상호작용·부작용·보관법·이미지)를 매일 다시 받고, **의약품 제품 허가정보(목록)** 에서 주성분·전문/일반 구분·분류를 품목기준코드로 연결합니다.
- 허가정보는 `data/drugs/permit.json` 에 캐시합니다. 처음에는 목록을 통째로 넘기며 채우고(일반의약품 필터가 되면 약 200회, 아니면 약 450회 호출), 그 뒤로는 새 품목만 개별 조회합니다. `DRUG_API_BUDGET`(기본 900회)·`DRUG_TIME_BUDGET`(기본 780초) 을 넘기면 받은 것까지 저장하고 나머지는 다음 날로 미룹니다.
- 허가정보 API 경로(`DrugPrdtPrmsnInfoService06/…`)는 식약처가 스키마를 바꾸면 버전이 올라갑니다. 기본 경로가 거부되면 스크립트가 후보 경로를 차례로 확인해 쓰고, 모두 실패하면 응답 내용을 로그에 남기고 주성분 없이 e약은요 정보만 저장합니다. 경로가 확인되면 저장소 Variables `DRUG_PERMIT_SERVICE` 로 고정할 수 있습니다.
- 주성분 중 성분 사전에 있는 영양소(비타민·미네랄·유산균·실리마린 등)를 찾아 `ingredients` 로 연결하고, 의약품 페이지(`drug.html?id=품목기준코드`)에서 그 성분 기준의 '함께 먹으면 좋은 성분'·'주의할 조합'을 보여줍니다. 약물의 염(아토르바스타틴칼슘), 제산제(수산화마그네슘), 외용제(연고의 산화아연)는 영양 성분으로 보지 않습니다.
- 허가정보의 주성분은 영문(INN, 예: `Ursodeoxycholic Acid`)으로 오므로 `scripts/drug_ingr_ko.py` 사전으로 한글(우르소데옥시콜산)로 바꿔 보여주고, 영문 원문은 `ingrEn` 에 함께 저장합니다. 사전에 없는 이름은 영문 그대로 나옵니다(단일 성분 약은 제품명 괄호의 한글을 씁니다).
- 파일: `data/drugs/names.json`(검색 색인: 품목코드·이름·영양 성분·주성분 요약·전문/일반·제조사), `data/drugs/detail/<000~127>.json`(상세 조각, `assets/js/data.js` 의 `drugShard()` 와 같은 해시). 의약품은 온라인 판매가 금지되어 구매 링크를 넣지 않습니다.
- 규칙을 바꾼 뒤에는 `python scripts/fetch_drugs.py --rebuild` 로 API 호출 없이 다시 생성할 수 있습니다.

### 제품 매칭 기준
- 비타민·미네랄은 식약처가 기능성 함량 이상일 때만 표기하는 **기능성 문구**(예: 칼슘 "뼈와 치아 형성에 필요")와 제품명으로 판정합니다. 부형제(스테아린산마그네슘 등)는 제외합니다.
- 기능성 원료(홍삼·루테인 등)는 제품명·기능성 문구·원재료 목록 앞부분(주원료)으로 판정합니다.
- 비타민·미네랄 5종 이상이면 종합비타민·미네랄로도 분류합니다.

### 제품 변경 추적
`fetch_products.py` 는 식약처 API 가 느리고(1,000건당 20~40초) 키당 동시 요청 1개만 허용하므로, 최신 신고분부터 거꾸로 `FOODSAFETY_MAX_ROWS`(기본 15,000건)만 순차 수집합니다. 이전 `products.json` 과 신고번호 기준으로 비교해 **신규 / 변경(제품명·기능성·원재료·주의사항) / 삭제** 를 `changelog` 에 기록하고, 제품 찾기 페이지 상단에 건수와 이력을 표시합니다.

## 제휴 링크 동작 방식
- `assets/js/affiliate.js` 가 각 성분·제품의 검색어로 쇼핑몰 검색 URL 을 만들고
  - 링크프라이스 머천트(11번가·G마켓·옥션)는 `click.linkprice.com` 딥링크로 감쌉니다 (`config.js` 의 `buildUrl` 형식은 링크프라이스 관리자 "딥링크 생성" 형식과 맞춰 주세요).
  - 쿠팡은 `data/deeplinks.json` 에 생성된 파트너스 단축 링크가 있으면 사용하고, 없으면 일반 검색 링크로 연결합니다.
- 모든 쇼핑 링크는 `rel="nofollow sponsored noopener"` 이며, 푸터·소개·제품 영역에 쿠팡 파트너스 필수 고지 문구가 포함되어 있습니다.

## 가이드 페이지 추가·수정
- `data/guides.json` 의 `items` 에 항목을 추가하면 `python scripts/build_site.py` 가 `guide/<slug>.html` 과 `guides.html` 을 다시 생성합니다.
- 필수 키: id, type(concern|target|howto), slug, icon(lucide 아이콘명), title(SEO 제목), h1, keywords, description, intro, ingredients[{id, why}], combos[{ids, note}], tips, cautions, faq[{q, a}], related(가이드 id). 긴 본문은 sections[{h2, body}].
- 성분 id 는 `data/ingredients.json` 과 일치해야 하며, 빌드 시 참조가 검증됩니다.
- 표현은 식약처 인정 기능성 범위("~에 도움을 줄 수 있음")를 지키고 질병 치료·예방 표현을 쓰지 마세요.

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
- `config.js` 의 `naverSiteVerification` / `googleSiteVerification` 에 확인 코드 입력 → `python scripts/build_site.py` 실행 → 커밋·푸시 (빌드가 `index.html` 머리에 정적 메타태그로 넣어 주며, 검색엔진 확인 크롤러는 JS 를 실행하지 않으므로 이 절차가 필요)

## 주의
- 성분 정보는 식약처 기능성 고시·한국인 영양소 섭취기준(2020)을 참고해 일반 성인 기준으로 요약한 것으로 의학적 조언이 아닙니다. 수치·문구는 공개 전 한 번 더 검토를 권장합니다.
- `data/products.json`, `data/news.json` 은 현재 **샘플** 상태이며 키 설정 후 첫 수집 시 실제 데이터로 교체됩니다 (화면에 샘플 표시 배너가 자동으로 사라집니다).
