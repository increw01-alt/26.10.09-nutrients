# 기억력·인지 가이드 + 셀프체크 '항응고제' 선택지·추천 제외(avoid) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) 기능성 허브에는 '기억력·인지 기능' 장(성분 4종·개별인정 원료 60건·신고 제품 2,278건)이 있는데 고민별 가이드에는 기억력 편이 없고(50대·수험생 가이드에 한 줄씩만) 셀프체크 고민 선택지에도 없다. "기억력 영양제"·"치매 예방 영양제" 검색 의도를 받는 고민별 가이드 `memory` 를 쓰고 홈 탭·셀프체크에 잇는다. (2) 셀프체크 '복용 중인 약'에 영양제 상호작용이 가장 큰 항응고제·항혈소판제 선택지가 없어, 와파린 복용자가 혈행 고민을 고르면 은행잎·나토키나제·오메가3 가 그대로 추천될 수 있다. 선택지를 더하고 규칙에 `avoid`(추천 제외 성분)를 두어 항응고제·수술 예정이면 출혈 경향 성분을 추천에서 빼고 '제외한 성분'과 이미 먹는 성분 경고를 보여 준다.

**Architecture:**
- 가이드: `data/guides.json` 항목 `memory`(고민별, 아이콘 brain) — 인정 문구 두 갈래('기억력 개선' 오메가3 EPA+DHA 900~2,000mg·은행잎·홍삼 + 개별인정 원료, '노화로 인해 저하된 인지력 개선' 포스파티딜세린 300mg 등)는 `materials.json` 인정현황으로 확인한 것만 쓰고, 치매 예방·집중력은 인정 아님을 명시. 핵심 성분 6(오메가3·PS·은행잎·홍삼·B12·엽산), 조합 3(모두 궁합 데이터 쌍 있음), 본문 4절(인정 문구·되돌릴 수 있는 원인과 약·검사 신호·조합과 주의), FAQ 4. `scripts/home_tabs.py` SHORT·ORDER(고민별 13번째) → 홈 탭·정적 카드, 50대·70대·수험생·이명·혈행 가이드의 related 에 연결(점검 경고 방지).
- 셀프체크: `data/finder.json` 고민 `memory`('기억력·건망증') 규칙 → memory 가이드 3점; 약 `anticoagulant`('항응고제·항혈소판제') 규칙 → with-medication 3점 + flags `meds`·`bleeding` + `avoid`; 기존 `surgery` 규칙에도 `avoid`. avoid 목록은 스크립트가 성분 사전 `drugCautions`/`cautions` 에서 출혈·INR·와파린 효과 변화 문구가 있는 성분 + 혈소판 작용 보고 성분(빌베리·콜레우스)을 모아 만들고(항응고제 26종, 수술은 와파린 효과·INR 변화 성분 8종을 뺀 18종), `drug-pairings.json` 와파린 규칙 주의 성분(피크노제놀 추가, 13종)이 모두 들어 있는지 테스트가 대조한다.
- 로직: `assets/js/finder.js` `score()` 가 규칙 `avoid` 를 모아 추천·점수 목록에서 빼고 `avoided`(점수순)·`avoidedHave`(이미 먹는 성분 중 제외 대상)를 돌려준다. 화면 `pages/finder.js` 는 `bleeding` 플래그 상자와 '복용 중인 약·수술 때문에 추천에서 뺀 성분' 칩, 이미 먹는 성분 경고를 그린다. 빌드 `validate_finder` 가 avoid 의 성분 id 를 검증하고, `render_finder` 의 설명문 가이드 수를 실제 수로.

**Tech Stack:** 데이터 JSON + Vanilla JS(순수 함수 테스트) + 파이썬 빌드. 새 CSS·아이콘 없음(brain 은 번들에 있음).

## Global Constraints

- 식약처 인정 범위: 치매 예방·치료·집중력은 인정 기능성이 아님을 본문·FAQ 에서 분명히 하고, 수치는 `materials.json`·성분 사전 값만(오메가3 기억력 개선 EPA+DHA 0.9~2g/일은 인정현황 원문).
- 추천 제외는 '상담이 필요한 성분을 먼저 보여 주지 않는다'는 뜻이며, 결과에 제외 성분과 이유를 보여 주고 의사·약사 상담을 안내한다.
- 생성 파일은 빌드로만, `check_site.py` 실패 0·경고 0, 푸시 전 `npm run assets`. 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 항응고제 선택 시 은행잎·나토키나제·오메가3·홍삼·비타민K·코엔자임Q10 이 추천·점수 목록에 없고, 이미 먹는 은행잎은 경고로 표시되는지(Node 테스트 + 브라우저).
2. 와파린 규칙 주의 성분 ⊆ 항응고제 avoid (Python 테스트).
3. 기억력 고민만 고르면 오메가3·포스파티딜세린이 상위 5에 오고 제외 안내가 없는지.

---

### Task 1: 코드

- [x] `finder.js` avoid·avoided·avoidedHave, `pages/finder.js` bleeding 플래그·제외 성분 표시, `build_site.py` validate_finder avoid 검증·설명문 가이드 수, 테스트(Node 3건·Python 1건).

### Task 2: 데이터

- [x] `guides.json` memory 가이드 + related 연결, `finder.json` 선택지·규칙·avoid, `drug-pairings.json` 와파린 규칙 피크노제놀, `home_tabs.py` 실행.

### Task 3: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0·경고 0 → `unittest`·`node --test` → 브라우저 확인(가이드·홈·셀프체크 폼·결과 데스크톱/모바일) → PROJECT-STATUS·CLAUDE.md·README → 커밋 → `git show --stat` → 리베이스 → 푸시.
