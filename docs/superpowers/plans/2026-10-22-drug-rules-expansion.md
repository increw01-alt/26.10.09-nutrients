# 약별 영양제 가이드 규칙 확장 — 혈압약·항우울제·항경련제 3개(21→24) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 의약품 상세(`drug.html`)의 '함께 챙기면 좋은/주의할 영양 성분'과 약별 영양제 가이드는 `data/drug-pairings.json` 규칙 21개에만 반응한다. 복용자가 가장 많은 처방약 분류 가운데 혈압약(ACE 억제제·ARB·칼슘채널차단제·베타차단제 — 이미 수집된 허가 목록에 암로디핀·사르탄 복합제 49+46건이 있으나 규칙이 없어 아무 안내도 뜨지 않음), 항우울제(SSRI·SNRI), 항경련제(뇌전증·신경통약)는 성분 사전 `drugCautions` 에 상호작용 근거가 이미 적혀 있다(칼륨·코엔자임Q10·마늘·오메가3·아르기닌·테아닌·홍경천·홍삼 ↔ 혈압약, 홍경천·가르시니아·테아닌·락티움·감태·은행잎 ↔ 항우울제, 비타민D·엽산·비오틴·B6·글루타민·은행잎 ↔ 항경련제). 세 규칙과 가이드 본문을 더해 24개로 늘린다.

**Architecture:** 기존 구조 그대로 — `data/drug-pairings.json` 규칙 3개(id·label·ingr(영문 INN 부분 일치)·cls(허가 분류명 — 혈압강하제·항전간제)·good·caution(why 는 성분 사전 drugCautions 근거)·note), `data/drug-guides.json` 본문 3편(rx: true — 처방약이라 e약은요 목록 대신 `drugs` 대표 성분·제품을 보여 주고, `fetch_drugs.py` 의 `fetch_rx` 가 다음 실행부터 허가 목록을 수집해 '이 분류의 약' 목록을 채움), `scripts/drug_ingr_ko.py` KO 사전에 영문 주성분 45종의 한글 표기, `data/brand-priority.json` 에 오리지널 브랜드 키워드(렉사프로·졸로푸트·프로작·심발타·케프라·라믹탈·토파맥스·테그레톨·트리렙탈·오르필·데파코트·미카르디스·트윈스타·아타칸·아프로벨·트리테이스·아달라트·콩코르·딜라트렌·네비레트·아서틸·세비카·레메론·이펙사·리리카·뉴론틴·빔팻·웰부트린·세로자트·팍실·브린텔릭스). 코드 변경 없음.

**Tech Stack:** 데이터 JSON + 파이썬 사전 + 빌드. 수집은 CI(`update-data.yml`)가 이어서 한다(처방약 규칙 10→13개라 남은 수집 일수가 늘어남).

## Global Constraints

- 규칙의 성분은 성분 사전 `drugCautions`/`cautions` 에 적힌 상호작용만 옮기고 질병 치료·예방·약 중단 표현은 쓰지 않는다. '함께 챙기면 좋은' 성분은 검사 후·의사 상담 전제를 why 에 적는다.
- 의약품에는 구매 링크를 넣지 않는다(기존 템플릿 그대로). 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. `validate_drug_pairings`·`validate_drug_guides` 통과(성분 id·규칙 id 1:1·related slug), 기존 허가 레코드(암로디핀·사르탄 복합제)가 새 혈압약 규칙에 걸려 `drug.html` 조합 블록에 칼륨 주의가 뜨는지.
2. `load_rx_rules()` 가 새 규칙 3개를 포함하는지(처방약 수집 대상), KO 사전에 빠진 INN 이 없는지.
3. `check_site.py` 실패 0·경고 0, 성분 페이지 '약과 함께' 칩(칼륨·홍경천·글루타민 등) 증가.

---

### Task 1: 데이터

- [x] 규칙 3개 + 가이드 본문 3편 + KO 사전 + 브랜드 키워드 + 테스트(Python 2건).

### Task 2: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` → `unittest`·`node --test` → 브라우저 확인(가이드 3편·허브·의약품 상세 조합 블록·성분 칩) → CLAUDE.md·PROJECT-STATUS → 커밋 → `git show --stat` → 리베이스 → 푸시.
