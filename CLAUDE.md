# 영양제.kr — Claude Code 작업 지침

영양제 성분 정보·궁합·복용 가이드 정적 사이트. 정식 주소 https://영양제.kr (`https://xn--og5b1hx9c.kr`), Cloudflare Pages 가 이 저장소의 기본 브랜치를 push 마다 자동 배포한다.

## 꼭 지킬 것
- 스택: 정적 HTML + Tailwind CSS(정적 빌드 `assets/css/tailwind.css`) + Pretendard + Vanilla JS. 프레임워크·번들러를 추가하지 않는다. 속도를 위해 런타임 CDN(Tailwind Play, unpkg lucide)은 쓰지 않는다: Tailwind 클래스를 추가·변경하면 `npm run css`, 새 lucide 아이콘을 쓰면 `npm run icons` 로 `assets/js/icons.js`(사용 아이콘만 담은 번들) 를 재생성한다 (둘 다 `npm run assets`; Node 가 없으면 push 후 `.github/workflows/build-assets.yml` 이 자동 생성·커밋). 모든 1st-party 스크립트는 `defer` 로 싣는다.
- 생성 파일은 직접 고치지 않는다: `i/*.html`, `guide/*.html`, `guides.html`, `sitemap.xml`, `data/meta.json` 은 `python scripts/build_site.py` 가 만든다. `index.html` 의 `site-verification` 마커 사이(검색엔진 소유 확인 메타태그)도 빌드가 `config.js` 값으로 채우므로 손으로 넣지 않는다. 데이터(`data/ingredients.json`, `data/interactions.json`, `data/guides.json`)나 템플릿(`scripts/build_site.py`)을 고친 뒤 빌드한다. 빌드는 모든 HTML 의 `assets/js·css` 링크에 내용 해시(`?v=…`)를 붙이므로(캐시 무효화) JS·CSS 를 고친 뒤에도 반드시 빌드한다. 루트의 `_headers` 는 Cloudflare Pages 캐시 설정이다.
- 브랜드·도메인·제휴 ID 는 `assets/js/config.js` 한 곳에서 관리한다. HTML 의 canonical·OG 주소는 퓨니코드 `https://xn--og5b1hx9c.kr` 를 쓴다. Cloudflare Pages 는 `/foo.html` 요청을 `/foo` 로(`/index.html` 은 `/`) 리다이렉트하고 확장자 없는 주소로 서비스하므로 canonical·og:url·sitemap·구조화 데이터의 주소는 확장자 없는 형태(`scripts/build_site.py` 의 `page_url()`, 정적 페이지는 head 에 직접)로 쓰고, 내부 링크는 로컬 `http.server` 확인을 위해 `.html` 을 유지한다.
- 건강 정보 표현은 식약처 인정 기능성 범위("~에 도움을 줄 수 있음")를 지키고 질병 치료·예방·완치 표현을 쓰지 않는다. 근거 없는 수치·수상·보증을 만들지 않는다.
- 응답과 커밋 메시지는 한국어로 쓴다.

## 자주 쓰는 명령
```bash
python -m http.server 8080            # 로컬 확인 (Windows: dev.bat 또는 .\dev.ps1)
python scripts/build_site.py           # 데이터 검증 + 성분·가이드 페이지·sitemap·meta 생성 (데이터 수정 후 필수)
npm run assets                         # Tailwind CSS 재생성 + 아이콘 번들 (클래스·아이콘을 바꿨을 때, 그다음 build_site.py)
python scripts/fetch_products.py --rebuild   # 매칭 규칙 변경 후 API 호출 없이 제품 파일 재생성
python scripts/fetch_drugs.py --rebuild      # 의약품 성분 규칙 변경 후 API 호출 없이 재생성 (수집은 DATA_GO_KR_KEY 필요)
python scripts/fetch_news.py / fetch_materials.py / fetch_products.py / fetch_drugs.py   # API 키(.env) 있을 때 수집
```
자동 수집은 `.github/workflows/update-data.yml` 이 매일 03:15 KST 에 실행하며, 수집 결과 커밋(`chore(data): 자동 데이터 갱신`)이 원격에 쌓이므로 작업 전 `git pull` 을 먼저 한다.

## 구조 요약
- `assets/js/` : `config.js`(설정) · `data.js`(JSON 로더·검색 — `nameMatcher`/`has`/`markMatch` 는 한글을 자모로 풀어 비교하므로 '락ㅌ'·'ㄹㅌㅍ' 같은 일부 입력도 제품명과 맞춘다) · `affiliate.js`(쇼핑 링크) · `layout.js`(헤더·푸터·검색 오버레이·메뉴·모바일 탭 바) · `schedule.js`(복용 시간표) · `illus.js`(병·캡슐 SVG 일러스트, 사진 대신 사용) · `pages/*.js`(페이지별)
- 디자인 체계: 딥 그린(`brand-*`)·크림(`cream-*`)·피치(`peach-*`) 색상은 `tailwind.config.cjs`(빌드 설정), 공통 스타일(헤더 워드마크·탭·카드)은 `assets/css/style.css`. 메인(`index.html`)은 실사형 시안을 옮긴 전용 스타일 `assets/css/home.css`(모든 규칙이 `.home` 아래로 한정)를 쓴다. 내부 페이지는 상단 `.page-hero` 밴드 + `.eyebrow-kicker`/`.page-title`/`.page-lead` 제목 묶음, `.btn-primary`/`.btn-outline` 버튼, `.ing-card` 성분 카드로 같은 결을 유지한다. 연출 이미지는 `assets/images/home/*.webp`(분류별 알약 사진은 `Illus.photoFor(category)`), 성분명이 적힌 병은 `Illus.bottle` SVG 를 쓴다. 헤더 높이는 `--header-h`(모바일 68px·데스크톱 84px) 변수로 관리하며 고정 탭(`.detail-tabs`)이 이를 참조한다.
- `data/` : 성분·궁합·가이드(수동) / 제품·원료·뉴스(자동). 제품은 목록(`products.json`, 성분별 400건 상한) + 성분별 상위(`products/top/`) + 상세 조각(`products/detail/`, 매칭된 전체) + 검색용 경량 색인(`products/names.json` 최근 3년 + `names-old.json` 그 이전, 빌드가 상세 조각에서 생성, 이름·제조사로 검색; `D.productNames()` 는 최근분을 먼저 주고 `n.more` 로 과거분을 합친다). 검색 순위(`D.nameMatcher`)는 이름 앞부분 일치 → 단어 첫머리 → 이름 중간 → 제조사명 일치 등급 순이고, 같은 등급 안에서는 `data/brand-priority.json`(수동, 제조사명 앞부분·제품명 키워드별 가중치 1~3)이 높은 브랜드가 먼저 나온다 — 빌드(`scripts/brand_priority.py`)가 색인 항목(제품 `p[4]`, 의약품 `p[6]`)에 실어 두므로 규칙을 고친 뒤 빌드한다. 제품 상세는 `product.html?id=…`(`pages/product.js`: 함유 성분·함께 먹으면 좋은 성분·주의 조합·신고 정보, noindex)
- 검색: 메인 검색창·전역 검색(/)은 자동완성(성분·제품·의약품·가이드 + '전체 검색 결과 보기'), Enter·검색 버튼은 통합 검색 결과 페이지 `search.html?q=…`(`pages/search.js`: 섹션별 결과, 결과 없으면 비슷한 이름 제안과 검색 요령, noindex·robots 제외)로 간다
- 메인 '빠른 궁합 체크'(`pages/home.js` `initChecker`)는 검색형 선택란: 성분·제품·의약품을 고르면 연결된 영양 성분 묶음으로 조합을 계산하고 `compatibility.html?items=…` 로 넘긴다. 영양 성분이 없는 의약품은 `drug-pairings.json` 규칙으로 상대 영양제를 판정하고 `drug.html?id=…&with=성분id#sec-pairing`(선택한 영양제와의 조합 블록)으로 넘긴다. 의약품별 '함께 챙기면 좋은/주의할 영양 성분'은 `data/drug-pairings.json`(수동, 주성분 영문·분류 기준, 빌드가 id 검증)이며 `drug.html` 의 `#sec-pairing` 에 표시된다
- 의약품(`scripts/fetch_drugs.py`, 공공데이터포털 `DATA_GO_KR_KEY` 필요): `data/drugs/names.json`(검색 색인) + `data/drugs/detail/<000~127>.json`(상세 조각) + `data/drugs/permit.json`(허가정보 캐시, 지우면 첫 실행처럼 목록 전체를 다시 받음). 상세는 `drug.html?id=품목기준코드`(`pages/drug.js`). 의약품에는 구매 링크를 넣지 않는다(온라인 판매 금지). 수집 전에는 `names.json` 이 없어 검색 결과가 비는 것이 정상
- `scripts/` : 수집·빌드 파이썬. `fetch_products.py` 의 `NUTRIENT_RULES`·`HERBAL_RULES`·`EXCIPIENT_RE` 가 제품-성분 매칭 규칙. `fetch_drugs.py` 의 `SALT_RULES`·`CONTAIN_RULES`(한글·영문)가 의약품 주성분-영양 성분 규칙, `drug_ingr_ko.py` 가 영문 주성분 → 한글 표시 사전 (규칙·사전을 고친 뒤 `python scripts/fetch_drugs.py --rebuild`)
- 현황·이력·다음 할 일: `docs/PROJECT-STATUS.md`

## 새 성분·가이드 추가 절차
1. `data/ingredients.json` 또는 `data/guides.json` 에 항목 추가 (성분 id 참조는 빌드 시 검증됨)
2. 궁합이 필요하면 `data/interactions.json` 에 쌍 추가
3. `python scripts/build_site.py` → 생성 파일 확인 → 로컬 서버에서 페이지 확인 → 커밋·푸시
