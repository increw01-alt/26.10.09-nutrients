# 뼈 건강·혈압 관리 가이드 2편 + 셀프체크 고민 선택지·약 규칙 보강 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기능성 허브에는 '뼈 건강'(성분 6·원료 16·제품 4,241)과 '혈압 관리'(성분 2·원료 21·제품 434) 장이 있는데 고민별 가이드에는 둘 다 없다(뼈는 칼슘 고르는 법·골다공증 약 복용자·40대 여성에 흩어져 있고, 혈압은 '고혈압 약 복용자'뿐). "골다공증 영양제"·"뼈에 좋은 영양제"·"혈압 낮추는 영양제" 검색 의도를 받는 고민별 가이드 `bone-health`·`blood-pressure` 를 쓰고 셀프체크 고민 선택지('뼈·골다공증 걱정'·'혈압')와 홈 탭에 잇는다. 아울러 셀프체크의 혈압약·신장질환 규칙에 `avoid` 를 더해 혈압약(ACE 억제제·ARB·칼륨보존 이뇨제) 복용자에게 칼륨, 신장질환·투석에 칼륨·마그네슘·비타민A 가 추천되지 않게 한다.

**Architecture:**
- `data/guides.json` 2편(고민별): 뼈 — 식약처가 칼슘·비타민D 에 인정한 '골다공증 발생 위험 감소에 도움'(질병발생위험감소 기능)을 축으로 비타민K('뼈의 구성에 필요')·망간('뼈 형성에 필요')·대두이소플라본('뼈 건강에 도움', 비배당체 24~27mg)·폴리감마글루탐산('칼슘 흡수 촉진')·마그네슘(뼈 기능성 아님)을 구분하고, 골밀도 T-score(용어 사전 `bmd`)·국가건강검진(54·66세 여성)·식사 칼슘 계산·운동·낙상 예방을 담는다. 혈압 — 코엔자임Q10('높은 혈압 감소에 도움', 90~100mg)·마늘('혈압 조절', 2022 추가)과 개별인정 원료(올리브잎주정추출물 500~1,000mg·포도씨추출물 150~300mg·GABA 20mg·카제인가수분해물·연어펩타이드 2g 등, `materials.json` 원문)를 인정 문구대로 쓰고, 칼륨·마그네슘·오메가3·아르기닌은 혈압 기능성이 아님을 명시하며, 혈압약 병용 주의(고칼륨혈증·혈압 과도 저하)와 생활 치료(나트륨 2g·주 150분 운동·가정혈압 측정법·140/90·180/120 기준)를 정리한다. 아이콘은 기능성 허브와 같은 `bone`·`gauge`(번들에 있음).
- 연결: `scripts/home_tabs.py` SHORT·ORDER(고민별 14·15번째), 칼슘·비타민D·골다공증 약·갱년기·40대 여성·50대 가이드 related ← 뼈, 혈압약·콜레스테롤·혈행·50대·약과 영양제 related ← 혈압.
- 셀프체크 `data/finder.json`: 고민 `bone`('뼈·골다공증 걱정') → bone-health 3·calcium-guide 1, `blood-pressure`('혈압') → blood-pressure 3; 약 규칙 `hypertension` 에 `avoid: [potassium]`, `kidney` 에 `avoid: [potassium, magnesium, vitamin-a]`(성분 사전 주의사항·신장 가이드 제목 근거). 테스트: Node(뼈·혈압·혈압약·신장) + Python(옵션 존재·avoid).

**Tech Stack:** 데이터 JSON + 파이썬 빌드. 코드 변경 없음(지난 라운드의 avoid 구조 재사용).

## Global Constraints

- 식약처 인정 범위: '골다공증 발생 위험 감소에 도움'은 칼슘·비타민D 의 인정 문구 그대로, '혈압' 문구는 원료별 인정 문구·섭취량(`materials.json`)대로. 고혈압·골다공증 치료 대체, '혈압을 낮춘다' 단정은 쓰지 않는다. 수치는 성분 사전·인정현황·기존 가이드에서 쓰는 값만.
- 생성 파일은 빌드로만, `check_site.py` 실패 0·경고 0(새 가이드는 related 로 연결), 푸시 전 `npm run assets`. 응답·커밋·문서는 한국어, 커밋 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. 두 가이드 제목이 기능성 허브 제목('뼈 건강 영양제 — 식약처 인정 기능성 성분·원료·신고 제품 총정리')과 겹치지 않고 95자 이하인지.
2. 셀프체크: 뼈 고민이면 칼슘·비타민D 가 상위 5, 혈압 고민 + 혈압약이면 코엔자임Q10 추천·칼륨 제외, 신장질환이면 마그네슘·칼륨 제외.
3. 혈압 가이드의 칼륨은 '식사로'를 강조하고 성분 순서를 뒤에 두어 추천 점수가 낮게 간다.

---

### Task 1: 데이터

- [x] `guides.json` 2편 + related 연결, `finder.json` 선택지·규칙·avoid, `home_tabs.py` SHORT·ORDER + 실행, 테스트.

### Task 2: 재생성·점검·문서·커밋

- [x] 빌드 → `npm run assets` → 빌드 → `check_site.py` 실패 0·경고 0 → `unittest`·`node --test` → 브라우저 확인(가이드 2편·홈·셀프체크 폼·결과 데스크톱/모바일) → PROJECT-STATUS → 커밋 → `git show --stat` → 리베이스 → 푸시.
