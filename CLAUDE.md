# 영양제.kr — Claude Code 작업 지침

영양제 성분 정보·궁합·복용 가이드 정적 사이트. 정식 주소 https://영양제.kr (`https://xn--og5b1hx9c.kr`), Cloudflare Pages 가 이 저장소의 기본 브랜치를 push 마다 자동 배포한다.

## 꼭 지킬 것
- 스택: 정적 HTML + Tailwind CSS(CDN) + Pretendard + Vanilla JS. 빌드 도구·프레임워크를 추가하지 않는다.
- 생성 파일은 직접 고치지 않는다: `i/*.html`, `guide/*.html`, `guides.html`, `sitemap.xml`, `data/meta.json` 은 `python scripts/build_site.py` 가 만든다. `index.html` 의 `site-verification` 마커 사이(검색엔진 소유 확인 메타태그)도 빌드가 `config.js` 값으로 채우므로 손으로 넣지 않는다. 데이터(`data/ingredients.json`, `data/interactions.json`, `data/guides.json`)나 템플릿(`scripts/build_site.py`)을 고친 뒤 빌드한다.
- 브랜드·도메인·제휴 ID 는 `assets/js/config.js` 한 곳에서 관리한다. HTML 의 canonical·OG 주소는 퓨니코드 `https://xn--og5b1hx9c.kr` 를 쓴다.
- 건강 정보 표현은 식약처 인정 기능성 범위("~에 도움을 줄 수 있음")를 지키고 질병 치료·예방·완치 표현을 쓰지 않는다. 근거 없는 수치·수상·보증을 만들지 않는다.
- 응답과 커밋 메시지는 한국어로 쓴다.

## 자주 쓰는 명령
```bash
python -m http.server 8080            # 로컬 확인 (Windows: dev.bat 또는 .\dev.ps1)
python scripts/build_site.py           # 데이터 검증 + 성분·가이드 페이지·sitemap·meta 생성 (데이터 수정 후 필수)
python scripts/fetch_products.py --rebuild   # 매칭 규칙 변경 후 API 호출 없이 제품 파일 재생성
python scripts/fetch_news.py / fetch_materials.py / fetch_products.py   # API 키(.env) 있을 때 수집
```
자동 수집은 `.github/workflows/update-data.yml` 이 매일 03:15 KST 에 실행하며, 수집 결과 커밋(`chore(data): 자동 데이터 갱신`)이 원격에 쌓이므로 작업 전 `git pull` 을 먼저 한다.

## 구조 요약
- `assets/js/` : `config.js`(설정) · `data.js`(JSON 로더·검색) · `affiliate.js`(쇼핑 링크) · `layout.js`(헤더·푸터·검색 오버레이·메뉴·모바일 탭 바) · `schedule.js`(복용 시간표) · `illus.js`(병·캡슐 SVG 일러스트, 사진 대신 사용) · `pages/*.js`(페이지별)
- 디자인 체계: 포레스트 그린(`brand-*`)·크림(`cream-*`)·피치(`peach-*`) 색상은 `assets/js/tailwind.config.js`, 공통 스타일(헤더 워드마크·탭·카드)은 `assets/css/style.css`. 메인(`index.html`)은 실사형 시안을 옮긴 전용 스타일 `assets/css/home.css`(모든 규칙이 `.home` 아래로 한정)를 쓴다. 내부 페이지는 상단 `.page-hero` 밴드 + `.eyebrow-kicker`/`.page-title`/`.page-lead` 제목 묶음, `.btn-primary`/`.btn-outline` 버튼, `.ing-card` 성분 카드로 같은 결을 유지한다. 연출 이미지는 `assets/images/home/*.webp`(분류별 알약 사진은 `Illus.photoFor(category)`), 성분명이 적힌 병은 `Illus.bottle` SVG 를 쓴다. 헤더 높이는 `--header-h`(모바일 68px·데스크톱 84px) 변수로 관리하며 고정 탭(`.detail-tabs`)이 이를 참조한다.
- `data/` : 성분·궁합·가이드(수동) / 제품·원료·뉴스(자동). 제품은 목록(`products.json`) + 성분별 상위(`products/top/`) + 상세 조각(`products/detail/`)
- `scripts/` : 수집·빌드 파이썬. `fetch_products.py` 의 `NUTRIENT_RULES`·`HERBAL_RULES`·`EXCIPIENT_RE` 가 제품-성분 매칭 규칙
- 현황·이력·다음 할 일: `docs/PROJECT-STATUS.md`

## 새 성분·가이드 추가 절차
1. `data/ingredients.json` 또는 `data/guides.json` 에 항목 추가 (성분 id 참조는 빌드 시 검증됨)
2. 궁합이 필요하면 `data/interactions.json` 에 쌍 추가
3. `python scripts/build_site.py` → 생성 파일 확인 → 로컬 서버에서 페이지 확인 → 커밋·푸시
