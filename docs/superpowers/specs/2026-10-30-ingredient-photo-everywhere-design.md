# 성분 실사 사진을 성분 사전·상세·작은 목록에 확장 — 설계 (2026-10-30)

## 의도
가이드 '핵심 성분' 실사 카드(설계 `2026-10-30-guide-photo-cards-design.md`)에 쓴 성분별 사진 87장을, 분류별 알약 그림(`Illus.photoFor(category)` / `build_site.py photo_img`)이 들어가던 모든 자리에 그 성분의 사진으로 바꿔 사이트 전체가 같은 결이 되게 한다. 사용자는 시안 중 **B-1(카드 위 넓은 사진 띠 + 사진 아래쪽을 어둡게 깔고 성분명을 흰 글씨로 얹음)** 과 **상세 페이지 상단(병 그림 자리에 정사각형 사진 + 금색 한 줄)** 을 골랐다.

## 바뀌는 자리
| 자리 | 지금 | 바뀐 뒤 |
|---|---|---|
| 성분 사전 목록 `ingredients.html`(`pages/ingredients.js`) | 알약 그림 + 제목 | **B-1 띠**: 높이 168px 사진(`-m` 360px, `srcset` 로 640 도 제공) + 아래쪽 그라데이션 + 성분명(흰색 900)·영문명, 분류 배지는 오른쪽 위. 본문(요약·태그·시간·링크)은 띠 아래 |
| 제품·의약품 페이지의 성분 카드(`pages/product.js`·`pages/drug.js` `ingCard`) | 같은 `.ing-card` | 같은 B-1 띠(제목은 h3 + 링크) |
| 성분 상세 상단(`pages/ingredient.js` hero) | 병 SVG + 알약 배지 + 작은 칸 3개 | 정사각형 사진(640) + 아래쪽 그라데이션 + 금색 한 줄(claim, `scope: individual` 이면 '개별인정 원료' 보조 문구) + 작은 칸은 [사진 썸네일·분류 SVG·아이콘] |
| 검색 결과(`pages/search.js`)·셀프체크 결과(`pages/finder.js` thumb) | 44px/56px 알약 | 같은 크기의 사진 썸네일(`-s` 160px) |
| SSR 작은 카드: 기능성 허브·성분 비교·제형 비교·약별 가이드·용어 페이지의 `finder-thumb`(`build_site.py photo_img` 6곳) | 알약 | 사진 썸네일 `-s` + `?v=내용해시` |
| 가이드 핵심 성분 카드 | 사진 640 | 그대로 |

홈(`index.html`)·궁합 체크·내 영양제의 분류 SVG 아이콘(`Illus.forCategory`)은 그대로 둔다(사진이 아니라 아이콘 자리).

## 파일 크기 3종
`scripts/convert_photos.py` 가 원본 PNG 한 장에서 `<id>.webp`(640, 가이드·상세), `<id>-m.webp`(360, 목록 띠), `<id>-s.webp`(160, 썸네일) 셋을 만든다(`_default` 도 셋). 목록 띠는 `src=-m` + `srcset="-m 360w, 640 640w" sizes="(min-width:768px) 360px, 100vw"` 로 데스크톱 1x 는 360, 고해상도·휴대폰은 640 을 받는다(lazy). `prepare_photos` 는 셋이 다 있어야 `<id>.webp` 로 치고, 하나라도 없으면 `_default.webp` + 경고(`missing_sizes`) — 변환을 다시 돌리라는 신호.

## 캐시·버전
- SSR(가이드·작은 카드·상세 hero 의 `data-photo`)은 `?v=내용해시`.
- JS 가 그리는 사진(목록·검색·셀프체크·제품/의약품 카드)은 해시 없이 `assets/images/ingredients/<id>-m.webp` — `_headers` 의 `/assets/images/*` 7일 캐시, 서비스워커는 `?v=` 없는 자산을 재검증(`strategyFor` "revalidate") 하므로 사진을 바꾸면 최대 7일 뒤 반영. 사진이 거의 안 바뀌므로 받아들인다.

## 상세 페이지의 금색 한 줄
claim 은 `data/ingredient-photos.json` 에만 있고 JS 는 이 파일을 안 읽는다(프롬프트 틀까지 내려보낼 이유가 없음). 빌드(`render_page`)가 `#ingredient-hero` 에 `data-photo="<file>?v=…" data-photo-claim="…" data-photo-scope="individual|"` 를 넣고 `pages/ingredient.js` 가 읽는다. 속성이 없으면(옛 빌드) 금색 줄 없이 사진만.

## 비목표
- 사진 재생성·프롬프트 변경 없음. 제품 사진 없음. 홈 연출 이미지 교체 없음.
- `?v=` 를 JS 로 전달하는 색인 파일을 새로 만들지 않는다.

## 테스트
- Python: `convert_photos` 3종 생성, `prepare_photos` 3종 요구, `ing_thumb_img` SSR 썸네일 + 대체, `render_page` 의 data-photo 속성, CSS 클래스 존재.
- Node: `illus.js` 를 Node 에서 읽을 수 있게 가드(`module.exports`)하고 `ingPhotoUrl`·`ingThumb`·`ingBand` 의 문자열 결과를 `tests/illus.test.mjs` 로 검증.
- 브라우저: 목록·상세·검색·셀프체크·제품·기능성·비교 페이지, 모바일 폭.
