# 성분 비교 6편 추가(종합비타민/비타민B군·마그네슘/칼슘·코엔자임Q10/오메가3·비오틴/콜라겐·홍경천/테아닌·아연/셀레늄) + 셀프체크 생활 선택지·기능성 허브 연결 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 성분 대 성분 비교 20편은 새 성분 축 6편까지 끝났고, 남은 비교형 검색 의도 가운데 궁합 데이터 쌍과 성분 사전이 모두 갖춰진 6쌍을 더한다 — "종합비타민 비타민B군 같이"(B군 중복·B6 상한), "칼슘 마그네슘 같이·칼마디"(흡수 경쟁·2:1 비율), "코큐텐 오메가3 같이"(스타틴·항응고제·혈압약), "비오틴 콜라겐"(탈모·피부 인정 범위, 검사 왜곡), "홍경천 테아닌"(활력 vs 진정), "아연 셀레늄"(상한·구리 결핍·셀레노시스). 아울러 셀프체크 생활 상황에 '술자리가 잦아요'(→ 간 건강)·'햇빛을 거의 못 봐요'(→ 비타민D 고르는 법)를 더하고, 기능성 허브 기억력·뼈·혈압 장의 수동 가이드 목록에 지난 라운드의 새 가이드를 올린다(현재는 성분 겹침으로만 연결).

**Architecture:** 기존 구조 그대로 — `data/compares.json` 6편(ids·title·h1·description·keywords·intro·verdict·points·rows·together·faq·related; 궁합 쌍은 모두 데이터에 있어 '같이 먹어도 될까' 판정이 뜸: 종합비타민/B군·마그네슘/칼슘은 caution, 나머지 synergy), `data/finder.json` 생활 선택지 2개 + 규칙 2개(압축 서식 유지, 텍스트 삽입), `data/functions.json` guides 3곳. 코드 변경 없음.

**Tech Stack:** 데이터 JSON + 파이썬 빌드.

## Global Constraints

- 식약처 인정 문구는 성분 사전 `mfdsFunction` 그대로, 수치는 사전의 권장량·상한·1일 섭취량만(비오틴 30㎍·셀레늄 상한 400㎍·아연 상한 35mg·마그네슘 보충제 상한 350mg·칼슘 상한 2,500mg·코엔자임Q10 90~100mg·홍경천 200~600mg·테아닌 200~250mg). 탈모 개선·스타틴 근육통 개선처럼 인정되지 않은 효능은 FAQ 에서 구분하고 우열·수치 단정은 쓰지 않는다.
- 제목 틀 "`{A} vs {B}`: 차이와 고르는 기준", 기존 34편·성분 페이지와 제목이 겹치지 않게. 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 6편 모두 `validate_compares` 통과, '같이 먹어도 될까'에 데이터 쌍 판정(caution 2·synergy 4)이 뜨고 성분 페이지 칩이 늘어나는지.
2. 셀프체크 생활 '술자리가 잦아요'면 간 건강 가이드와 밀크씨슬이, '햇빛을 거의 못 봐요'면 비타민D 가 결과에 오는지(Node 테스트 + 브라우저).
3. `check_site.py` 실패 0·경고 0.

---

### Task 1: 데이터

- [x] `compares.json` 6편, `finder.json` 생활 선택지·규칙, `functions.json` guides, 테스트(Node 1건).

### Task 2: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` → `unittest`·`node --test` → 브라우저 확인(비교 6편·허브·셀프체크) → PROJECT-STATUS → 커밋 → `git show --stat` → 리베이스 → 푸시.
