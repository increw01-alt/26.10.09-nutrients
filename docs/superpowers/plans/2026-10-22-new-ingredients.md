# 성분 사전 확장 — 개별인정 원료 6종(리코펜·빌베리·L-글루타민·나토키나제·헛개나무·락토페린) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/PROJECT-STATUS.md` 7절 5번 (다) "신고 제품이 있는 원료 우선"에 따라, 성분 페이지가 없는 개별인정 원료 가운데 신고 제품이 많고 검색 수요("리코펜 효능", "빌베리 루테인", "글루타민 효능", "나토키나제 효능", "헛개나무 간", "락토페린 다이어트")가 있는 6종을 성분 사전에 더한다. 기능성 문구·1일 섭취량·주의사항은 모두 `data/materials.json`(식약처 기능성 원료 인정현황)에 있는 값만 쓴다.

| id | 이름 | 분류 | 인정 기능성 (materials.json) | 1일 섭취량 | 수집 제품(원재료명 기준) |
|---|---|---|---|---|---|
| lycopene | 리코펜 (토마토추출물) | herbal | 항산화에 도움을 줄 수 있음 | 리코펜으로서 5.7~15mg | 250 |
| bilberry | 빌베리추출물 | herbal | 눈의 피로 개선에 도움을 줄 수 있음 | 160~240mg | 144 |
| glutamine | L-글루타민 | amino | 과도한 운동 후의 L-글루타민 보충은 신체 저항능력 향상에 도움이 될 수 있음 | 3,000~5,000mg | 112 |
| nattokinase | 나토키나제 (HK나토배양물) | herbal | 혈소판 응집을 억제하여 혈액 흐름을 원활히 하는 데 도움을 줄 수 있음 | HK나토배양물로서 133mg | 60 |
| hovenia | 헛개나무과병추출분말 | herbal | 알코올성 손상으로부터 간을 보호하는 데 도움을 줄 수 있음 | 2,460mg | 44 |
| lactoferrin | 락토페린 | amino | 체지방 감소 · 면역기능 증진(원료별) | 300mg | 74 |

제외: 자일리톨(1,612건이지만 대부분 감미료로 든 제품이라 '함유' 연결이 오해를 부름), 자일로올리고당·이소말토올리고당(프락토올리고당 페이지가 프리바이오틱스 역할을 대표), 참당귀·구기자·비수리·복분자·오미자(검색 수요가 작고 복합 원료 표기가 제각각), 구아검가수분해물(공전 2025-03 개정 수치 미확인 — 보류 유지).

**Architecture:** 기존 절차(CLAUDE.md '새 성분·가이드 추가 절차') 그대로 — `data/ingredients.json` 항목 6개(id·name·en·aliases·category·icon·summary·mfdsFunction·benefits·dosage·timing·cautions·drugCautions·whoFor·shopQuery·tags·faq; 주의사항은 인정현황의 '섭취 시 주의사항' 문구를 옮기고 '(식약처 주의사항)' 표시), `data/interactions.json` 쌍 23개(성분당 4~5쌍, 나토키나제는 출혈 경향 성분과 caution), 가이드 핵심 성분 연결(눈 건강·전립선·운동·혈행·간 건강·면역), `drug-pairings.json`(와파린 규칙에 나토키나제 주의, 메토트렉세이트 규칙에 L-글루타민 주의 — 둘 다 인정현황 주의사항 근거), `scripts/fetch_products.py` HERBAL_RULES 6개(글루타민은 `re:글루타민(?!산)` 정규식 키워드로 'L-글루타민산 유래 GABA' 제품을 제외 — `kw_in` 에 `re:` 접두 지원 추가) → `fetch_products.py --rebuild` → 빌드. 기능성별 허브는 정규식이 자동으로 잡는다(항산화·눈·면역(신체저항)·혈행·간·체지방).

**Tech Stack:** 데이터 JSON + 파이썬 빌드. 새 아이콘 없음(sun·eye·dumbbell·heart-pulse·leaf·shield 는 번들에 있음).

## Global Constraints

- 식약처 인정 문구 범위("~에 도움을 줄 수 있음")만 쓰고, 전립선·혈전·숙취·근육 증가처럼 인정되지 않은 효능은 FAQ 에서 "인정 기능성이 아님"으로 분명히 쓴다. 수치는 인정현황의 1일 섭취량만.
- 궁합 쌍의 판정은 성분 사전의 주의사항·인정 기능성에서 나오는 사실 관계(혈소판 작용 중복, 지용성 흡수, 같은 기능성 중복)로만 쓴다.
- 응답·커밋·주석·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 새 성분 6개가 가이드 핵심 성분에 모두 연결되고 궁합이 4쌍 이상이라 `check_site.py` 경고가 0이어야 한다.
2. `re:글루타민(?!산)` 규칙이 GABA 제품을 제외하는지(`fetch_products.py` 단위 테스트).
3. 와파린·MTX 규칙에 더한 성분의 why 가 성분 사전 `drugCautions` 와 같은 근거여야 한다.

---

### Task 1: 데이터

- [x] `ingredients.json` 6개, `interactions.json` 23쌍, 가이드 6편 핵심 성분, `drug-pairings.json` 2곳, `fetch_products.py` 규칙 + `re:` 키워드.

### Task 2: 재생성·점검

- [x] `fetch_products.py --rebuild` → 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0·경고 0 → `unittest`·`node --test` → 새 성분 페이지·기능성 허브·궁합 체크 브라우저 확인.

### Task 3: 문서·커밋

- [x] PROJECT-STATUS(데이터 표 87종, 이력, 7절 5번), README 성분 수 → 커밋 → `git show --stat` → 푸시.
