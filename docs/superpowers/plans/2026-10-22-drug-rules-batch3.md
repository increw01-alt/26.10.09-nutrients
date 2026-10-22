# 약별 영양제 가이드 규칙 3차 — 일반의약품 빈틈(칼슘제·철분제·정장제) 3개 신설 + 비타민제 분류명 보강(28→31) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** e약은요 수집분 4,952건 가운데 먹는 약인데 규칙이 하나도 걸리지 않는 1,283건을 분류별로 세어 보니 정장제 112·칼슘제 69·무기질제제(철분제 중심) 66·비타민 B/A·D/E·K 제제 106건이 가장 큰 묶음이었다. "칼슘제와 철분제를 같이 먹어도 되나", "정장제와 유산균 영양제가 겹치나", "임팩타민에 종합비타민을 더해도 되나"는 실제 검색 의도가 분명한 질문인데 의약품 상세(`drug.html`)에 아무 안내도 뜨지 않았다. 성분 사전(칼슘·철분·아연·녹차추출물·차전자피·키토산·유산균·프락토올리고당·비타민 A/B6/D/E)의 `cautions`·`drugCautions`·`timing.note` 와 궁합 데이터 쌍(칼슘↔철분·아연·마그네슘·차전자피, 철분↔비타민C·엽산·B12·녹차추출물·키토산·종합비타민, 유산균↔프락토올리고당·차전자피, 종합비타민↔비타민A·B군)에 근거가 있는 세 규칙을 더하고, 기존 비타민 제제 규칙의 분류명(`비타민B제` 등)이 실제 허가 분류명(`비타민 B제(비타민 B1을 제외)`·`비타민 A 및 D제`·`비타민 E 및 K제`·`비타민 B1제`·`비타민 C 및 P제`)과 달라 106건이 빠지던 것을 고친다.

**Architecture:** 1·2차와 같다 — `data/drug-pairings.json` 규칙 3개(calcium-drug: cls 칼슘제 + 구연산·글루콘산·젖산칼슘 — 제산 용도 탄산칼슘·부형제 인산칼슘은 제외, iron-drug: ferrous/ferric/ferritin/polysaccharide iron 부분 일치 + `oralOnly`(외용제 제외; 'iron' 단독은 spironolactone 오탐이라 쓰지 않음), probiotic-drug: bacillus/lactobacillus/bifidobacterium/clostridium butyricum/saccharomyces/enterococcus — 로페라미드 같은 비생균 정장제는 제외) + vitamin-drug 규칙의 cls 보강과 주의 성분(B군·B6·A·D·E) 추가, `data/drug-guides.json` 본문 3편(모두 일반의약품, 원래 압축 서식 유지), `data/brand-priority.json` 키워드(디카맥스·디카테오·훼로바·하드칼·메디락·비오플·훼럼·헤모포스·바이오탑). KO 사전은 e약은요 레코드가 한글 주성분을 갖고 있어 변경 없음. 코드 변경 없음.

**Tech Stack:** 데이터 JSON + 빌드.

## Global Constraints

- 규칙의 성분은 성분 사전·궁합 데이터 근거만, 수치(상한 2,500mg·45mg·4,000 IU·3,000㎍ RAE·B6 100mg/50mg)는 성분 사전 `dosage` 값만 쓴다. 질병 치료·예방·약 중단 표현 금지, 의약품 구매 링크 없음. 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 칼슘제 규칙이 개비스콘(소화성궤양용제, 탄산칼슘)·제산제에는 걸리지 않고 디카맥스·칼디 계열(칼슘제)과 구연산칼슘 복합제(시트큐)에는 걸리는지. 철분제 규칙이 스피로노락톤('iron' 부분 문자열)에 걸리지 않는지. 정장제 규칙이 로페라미드 단일제에 걸리지 않는지.
2. 비타민제 규칙이 `비타민 B제(비타민 B1을 제외)`·`비타민 A 및 D제`·`비타민 E 및 K제`·`비타민 B1제`·`비타민 C 및 P제` 에 걸리는지(임팩타민정이 대표), `load_rx_rules()` 에 새 규칙이 들어가지 않는지(모두 rx 아님).
3. `check_site.py` 실패 0·경고 0, 허브 31편(일반의약품 15 + 처방약 16), 의약품 상세 조합 블록에서 디카맥스디플러스정(칼슘제 + 철분 2시간)·훼로바-유서방정(철분제 + 비타민C 좋음·칼슘 2시간)·메디락에스장용캡슐(정장제 + 유산균 중복)·임팩타민정(비타민 제제)이 뜨는지.

---

### Task 1: 데이터

- [x] 규칙 3개 + vitamin-drug 보강 + 가이드 본문 3편 + 브랜드 키워드 + 테스트.

### Task 2: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` → `unittest`·`node --test` → 브라우저 확인(가이드 3편·허브·의약품 상세 조합 블록 6건·성분 칩) → CLAUDE.md·PROJECT-STATUS → 커밋 → `git show --stat` → 리베이스 → 푸시.
