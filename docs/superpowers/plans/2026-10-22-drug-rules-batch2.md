# 약별 영양제 가이드 규칙 2차 확장 — 당뇨약·수면제/수면유도제·탈모약·통풍약 4개(24→28) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1차(혈압약·항우울제·항경련제)에 이어 성분 사전 `drugCautions` 에 근거가 있는 네 분류를 더한다 — 당뇨약(설포닐우레아·DPP-4·SGLT-2·인슐린: 바나바·여주·크롬·가르시니아·홍삼·인삼·알로에 겔 저혈당, 니코틴산 혈당 상승, 차전자피 흡수 지연 — 메트포르민 규칙은 유지하고 복합제는 둘 다 걸림), 수면제·수면유도제·진정 성분(테아닌·락티움·감태 졸림 중복 — e약은요의 디펜히드라민·독실아민 수면유도제 16건이 바로 목록에 실리고 외용 항히스타민 52건은 `oralOnly` 로 제외), 탈모약(피나스테리드·두타스테리드 ↔ 쏘팔메토; 철·비타민D·아연은 검사 후), 통풍약(알로푸리놀·페북소스타트·콜히친 ↔ 고용량 니코틴산·몰리브덴).

**Architecture:** 1차와 같다 — `data/drug-pairings.json` 규칙 4개(cls 당뇨병용제·최면진정제·통풍치료제), `data/drug-guides.json` 본문 4편(당뇨약·탈모약·통풍약 rx, 수면제는 일반의약품 중심이라 rx 아님 — 원래 압축 서식을 유지해 텍스트로 덧붙임), `scripts/drug_ingr_ko.py` 영문 주성분 21종, `data/brand-priority.json` 오리지널 브랜드 키워드(아마릴·자누비아·제미글로·포시가·자디앙·란투스·트레시바·스틸녹스·할시온·자낙스·리보트릴·프로페시아·아보다트·자이로릭·페브릭 등). 코드 변경 없음.

**Tech Stack:** 데이터 JSON + 파이썬 사전 + 빌드.

## Global Constraints

- 규칙의 성분은 성분 사전 근거만, '함께 챙기면 좋은' 성분은 검사 후·상담 전제. 질병 치료·예방·약 중단 표현 금지, 의약품 구매 링크 없음. 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 수면제 규칙이 외용 항히스타민(연고·플라스타)에는 걸리지 않고 먹는 수면유도제·감기약에만 걸리는지(`oralOnly`), 탈모약 규칙이 외용 미녹시딜에 걸리지 않는지(ingr 에 미녹시딜 없음).
2. 당뇨약 규칙 + 메트포르민 규칙이 복합제(자누메트 등)에 함께 뜨는지, `load_rx_rules()` 에 당뇨약·탈모약·통풍약이 들어가는지.
3. `check_site.py` 실패 0·경고 0, 허브 28편(일반의약품 12 + 처방약 16).

---

### Task 1: 데이터

- [x] 규칙 4개 + 가이드 본문 4편 + KO 사전 + 브랜드 키워드 + 테스트.

### Task 2: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` → `unittest`·`node --test` → 브라우저 확인(가이드 4편·허브·수면유도제 상세 조합 블록·성분 칩) → CLAUDE.md·PROJECT-STATUS → 커밋 → `git show --stat` → 리베이스 → 푸시.
