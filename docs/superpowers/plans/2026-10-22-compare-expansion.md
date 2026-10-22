# 성분 비교 확장 — 새 성분 6종을 축으로 한 'A vs B' 6편 + 용어 3개 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10-22 에 성분 사전에 더한 개별인정 원료 6종(리코펜·빌베리·L-글루타민·나토키나제·헛개나무·락토페린)은 모두 기존 대표 성분과 짝을 이루는 비교형 검색("루테인 빌베리 차이", "밀크씨슬 헛개", "크레아틴 글루타민", "오메가3 나토키나제 같이", "쏘팔메토 리코펜", "락토페린 가르시니아")이 있다. `data/compares.json` 에 6편을 더해 성분 비교 허브를 14→20편으로 늘리고, 비교 본문에서 자주 쓰는 계열·단위 용어 3개(카로티노이드·안토시아닌·FU)를 용어 사전에 더해 본문 자동 링크가 걸리게 한다.

| slug | ids | 비교 축 | 궁합 데이터 쌍 | related 가이드 |
|---|---|---|---|---|
| lutein-vs-bilberry | lutein · bilberry | 황반색소밀도 유지(고시형·지용성) vs 눈의 피로 개선(개별인정·수용성) | synergy 2 | eye-health · office-workers · 50s-plus |
| milk-thistle-vs-hovenia | milk-thistle · hovenia | 간 건강(실리마린 130mg) vs 알코올성 손상으로부터 간 보호(2,460mg) | synergy 2 | liver-health · liver-disease · 30s-men |
| creatine-vs-glutamine | creatine · glutamine | 근력 운동 시 운동수행능력(매일 3g) vs 과도한 운동 후 신체 저항능력(3~5g) | synergy 1 | exercise · athletes · kidney |
| omega-3-vs-nattokinase | omega-3 · nattokinase | 혈중 중성지질·혈행(EPA+DHA) vs 혈소판 응집 억제(HK나토배양물 133mg) — 겹치면 출혈 경향 | caution 2 | blood-circulation · surgery · with-medication |
| saw-palmetto-vs-lycopene | saw-palmetto · lycopene | 전립선 건강 유지(고시형) vs 항산화(개별인정, 전립선은 인정 기능성 아님) | neutral 1 | prostate · 50s-plus · hair-loss-meds |
| lactoferrin-vs-garcinia | lactoferrin · garcinia | 같은 '체지방 감소' — 우유 단백질(300mg) vs HCA(750~2,800mg, 식전) | neutral 1 | diet · weight-loss-drugs · immunity |

용어: `carotenoid`(카로티노이드 — 루테인·지아잔틴·리코펜·아스타잔틴 계열, 지용성, 카로틴혈증), `anthocyanin`(안토시아닌 — 빌베리추출물 지표 성분, 수용성, 항응고제 상담), `fu`(FU 나토키나제 활성 단위 — 인정 기준은 FU 가 아니라 원료 mg). 기존 용어 `antioxidant`·`iu`·`marker-compound` 의 related 에 연결.

**Architecture:** 기존 구조 그대로 — `data/compares.json` 항목(slug·ids·title·h1·description·keywords·intro·verdict·points·rows·together·faq·related)만 더하면 `compare_model`→`render_compare` 가 사전·제품 수·기능성·궁합 쌍과 합쳐 `compare/<slug>.html`·허브·요약 색인·성분 페이지 '비교 글' 칩을 만든다. 용어는 `data/glossary.json` 항목 3개(`component` 2 · `intake` 1)만 더하면 `TermLinker`·`terms.js` 가 본문 첫 등장을 링크한다. 코드 변경 없음.

**Tech Stack:** 데이터 JSON + 파이썬 빌드. 새 아이콘 없음.

## Global Constraints

- 각 성분의 기능성은 사전 `mfdsFunction` 을 그대로 인용하고, 인정되지 않은 효능(리코펜 전립선, 나토키나제 혈전 용해, 글루타민 근육 증가, 헛개 숙취 해소, 락토페린 '먹기만 하면 감량')은 FAQ 에서 "인정 기능성이 아님"으로 분명히 쓴다. 수치는 사전·인정현황의 1일 섭취량만 쓰고 가격·흡수율 수치·우열 단정은 쓰지 않는다.
- 제목 틀 "`{A} vs {B}`: … 차이와 고르는 기준"을 지키되 기존 14편·성분 페이지와 제목이 겹치지 않게 한다(`check_site.py` 제목 중복 실패).
- 용어 별칭은 다른 용어·성분명과 겹치지 않는 표기만(`validate_glossary`), 성분 이름 자체는 용어로 넣지 않는다.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 6편 모두 ids·points·rows 셀·related 가 검증을 통과하고 궁합 쌍이 데이터에 있어 '같이 먹어도 될까'에 판정이 뜨는지(특히 오메가3+나토키나제는 caution).
2. 새 용어 3개가 비교·성분 본문에서 실제로 링크되는지(카로티노이드 → 루테인·리코펜·아스타잔틴 본문, 안토시아닌 → 빌베리, FU → 나토키나제).
3. `check_site.py` 실패 0·경고 0, 성분 페이지 '비교 글' 칩 증가(루테인 2편, 밀크씨슬 2편, 크레아틴 2편, 오메가3 2편, 가르시니아 2편).

---

### Task 1: 데이터

- [x] `data/compares.json` 6편, `data/glossary.json` 3개 + 기존 용어 related 연결.

### Task 2: 재생성·점검

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0·경고 0 → `unittest`·`node --test` → 새 비교 6편·용어 3개·성분 페이지 칩·허브 브라우저 확인(데스크톱·모바일).

### Task 3: 문서·커밋

- [x] PROJECT-STATUS(페이지 표 20편·83개, 이력, 7절 ③·⑤) → 커밋 → `git show --stat` → 푸시.
