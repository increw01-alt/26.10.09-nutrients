#!/usr/bin/env python3
"""
식품안전나라(식약처) 건강기능식품 품목제조신고(C003) 데이터를 수집해
성분별로 분류한 뒤 data/products.json 으로 저장합니다.

사용법:
  FOODSAFETY_API_KEY=발급키 python scripts/fetch_products.py
  python scripts/fetch_products.py --sample      # 키 없이 기존 샘플 유지 (CI 안전)

API 키 발급: https://www.foodsafetykorea.go.kr/api/openApiInfo.do (식품안전나라 > Open API 신청)
환경변수:
  FOODSAFETY_API_KEY   필수. 없으면 기존 파일을 유지하고 정상 종료합니다.
  FOODSAFETY_MAX_ROWS  선택. 최신 신고분부터 거꾸로 수집할 최대 행 수 (기본 15000, 0 = 전체).
  FOODSAFETY_SERVICE   선택. 서비스 ID (기본 C003).

동작 방식:
  - 식약처 API 는 1,000건당 20~40초가 걸리고 인증키 하나로 동시에 1개 요청만 처리합니다.
    그래서 읽기 제한을 넉넉히 두고(READ_TIMEOUT) 순차 호출하며, 실패 시 서버가 이전 요청을
    끝낼 시간을 기다린 뒤 재시도합니다.
  - 데이터는 오래된 신고부터 정렬되어 있어 마지막 페이지(최신)부터 거꾸로 MAX_ROWS 만큼만 받습니다.
  - 이전 수집분 중 이번 수집 범위 밖(더 오래된)의 제품은 그대로 유지하고, 범위 안에서 사라진 제품만 '삭제'로 기록합니다.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, env, load_ingredients, log, now_iso, read_json, write_json  # noqa: E402

PathType = Path

API_BASE = "http://openapi.foodsafetykorea.go.kr/api"
PAGE = 1000
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 150             # 1,000건 응답에 20~40초, 여유 있게
RETRY = 4
WAIT_AFTER_TIMEOUT = 60        # 읽기 제한 초과 후 서버가 이전 요청을 끝낼 시간
WAIT_WHEN_BUSY = 40            # INFO-500(현재 접속 중인 인증키) 시 대기
PAUSE_BETWEEN_CALLS = 1.0
DEFAULT_MAX_ROWS = 15000       # 최신 신고분부터 거꾸로 수집할 기본 행 수
PER_INGREDIENT_CAP = 400       # 제품 찾기 목록(products.json)의 성분별 최대 건수 (최신 신고순). 상세 조각·검색 색인에는 상한 없음
CHANGELOG_KEEP = 200

MATCHER_VERSION = 3            # 매칭 규칙이 바뀌면 올립니다 → 다음 수집에서 변경 이력을 새로 시작 (3: 짧은 영문 약어 단어 경계, 비타민C·E 첨가물 제외)
RAW_HEAD = 160                 # 원재료 목록 앞부분(주원료로 보는 범위) 글자 수

# 원재료 목록에서 제거할 부형제·첨가물 (기능성 원료가 아닌데 성분명이 들어 있는 것들)
EXCIPIENT_RE = re.compile(
    r"스테아린산\s?마그네슘|마그네슘\s?스테아레이트|규산마그네슘|삼규산마그네슘|탄산마그네슘|산화마그네슘\s?\(부형제\)|"
    r"스테아린산\s?칼슘|제이인산칼슘|제삼인산칼슘|인산수소칼슘|인산칼슘|판토텐산칼슘|아스코르빌팔미테이트|울금색소|치자황색소|카라멜색소|스피루리나청색소|스피루리나색소",
    re.IGNORECASE,
)

# 영양소(비타민·미네랄): 제품명 키워드 / 기능성 문구(식약처 고시 표현) 로 판정
#   (이름 키워드, 고유 기능성 문구, 공유 기능성 문구, 기능성 텍스트에서 이름 키워드 허용 여부)
NUTRIENT_RULES: dict[str, tuple[list[str], list[str], str | None, bool]] = {
    "vitamin-a": (["비타민a", "비타민 a", "레티놀", "레티닐", "베타카로틴", "베타-카로틴"], ["어두운 곳에서 시각", "피부와 점막을 형성", "상피세포의 성장"], None, True),
    "vitamin-c": (["비타민c", "비타민 c", "아스코르브산", "아스코르빈산"], ["결합조직 형성과 기능유지", "철의 흡수에 필요"], "유해산소로부터 세포를 보호", True),
    "vitamin-d": (["비타민d", "비타민 d", "콜레칼시페롤"], ["칼슘과 인이 흡수되고", "뼈의 형성과 유지에 필요"], None, True),
    "vitamin-e": (["비타민e", "비타민 e", "토코페롤"], [], "유해산소로부터 세포를 보호", True),
    "vitamin-k": (["비타민k", "비타민 k", "메나퀴논", "필로퀴논", "mk-7"], ["뼈의 구성에 필요"], None, True),
    "vitamin-b-complex": (["비타민b1", "비타민 b1", "비타민b2", "비타민 b2", "비타민b6", "비타민 b6", "나이아신", "판토텐산", "티아민", "리보플라빈", "피리독신", "비타민b군", "비타민 b군", "비타민b 컴플렉스", "비타민b컴플렉스"], ["탄수화물과 에너지 대사에 필요", "체내 에너지 생성에 필요", "단백질 및 아미노산 이용에 필요"], None, True),
    "vitamin-b12": (["비타민b12", "비타민 b12", "코발라민"], ["정상적인 엽산 대사에 필요"], None, True),
    "folate": (["엽산", "폴산", "메틸폴레이트", "5-mthf"], ["세포와 혈액생성에 필요", "태아 신경관"], None, False),   # '엽산'은 B12 문구에도 등장 → 기능성 텍스트 이름 검사 제외
    "biotin": (["비오틴"], [], "지방, 탄수화물, 단백질 대사와 에너지 생성", True),
    "calcium": (["칼슘"], ["뼈와 치아 형성에 필요"], None, False),                      # '칼슘'은 비타민D 문구에도 등장
    "magnesium": (["마그네슘"], [], "에너지 이용에 필요", True),
    "zinc": (["아연", "징크"], ["정상적인 면역기능에 필요", "정상적인 세포분열에 필요"], None, True),
    "iron": (["철분", "헴철", "푸마르산철", "황산철", "피로인산철", "구연산철", "비스글리시네이트철", "철(ii)", "철 (ii)"], ["체내 산소운반과 혈액생성"], None, True),
    "selenium": (["셀레늄", "셀렌"], [], "유해산소로부터 세포를 보호", True),
    "copper": (["구리"], ["철의 운반과 이용에 필요"], None, True),
    # B군 단일 성분: B군 복합제 규칙과 함께 잡히며(함유 사실), 종합비타민 판정 수(B_SINGLE_IDS)에서는 제외
    "vitamin-b1": (["비타민b1", "비타민 b1", "티아민", "벤포티아민", "푸르설티아민"], ["탄수화물과 에너지 대사에 필요"], None, True),
    "vitamin-b2": (["비타민b2", "비타민 b2", "리보플라빈"], [], "체내 에너지 생성에 필요", True),
    "niacin": (["나이아신", "니코틴산", "니아신"], [], "체내 에너지 생성에 필요", True),
    "pantothenic-acid": (["판토텐산", "판테놀", "비타민b5", "비타민 b5"], [], "지방, 탄수화물, 단백질 대사와 에너지 생성", True),   # 비오틴과 같은 공유 문구
    "manganese": (["망간"], ["뼈 형성에 필요"], None, True),
    "molybdenum": (["몰리브덴"], ["환원 효소의 활성", "환원효소의 활성"], None, True),
    "iodine": (["요오드", "아이오딘"], ["갑상선 호르몬의 합성", "갑상선호르몬의 합성"], None, True),
    "potassium": (["염화칼륨", "구연산칼륨", "글루콘산칼륨"], ["체내 물과 전해질 균형"], None, False),   # '칼륨' 단독은 폴리감마글루탐산칼륨 등 오탐
}
# 기능성 원료: 제품명 / 기능성 텍스트 / 원재료 앞부분(주원료) / 고유 기능성 문구 로 판정
HERBAL_RULES: dict[str, tuple[list[str], list[str]]] = {
    "omega-3": (["오메가3", "오메가-3", "오메가 3", "epa", "dha", "피쉬오일", "크릴오일", "알티지", "rtg"], ["혈중 중성지질 개선"]),
    "probiotics": (["프로바이오틱스", "유산균", "락토바실러스", "비피도박테리움", "비피더스", "lactobacillus", "bifidobacterium"], ["유산균 증식", "유해균 억제"]),
    "lutein": (["루테인", "지아잔틴", "마리골드"], ["황반색소밀도"]),
    "coq10": (["코엔자임q10", "코엔자임 q10", "코큐텐", "유비퀴놀", "유비퀴논", "coq10"], []),
    "milk-thistle": (["밀크씨슬", "실리마린", "밀크시슬", "엉겅퀴"], []),
    "lycopene": (["리코펜", "라이코펜", "토마토추출물", "lycopene"], []),
    "bilberry": (["빌베리", "bilberry"], []),
    "glutamine": (["re:글루타민(?!산)", "l-glutamine"], ["신체 저항능력"]),   # 'L-글루타민산 유래 GABA' 제품은 제외
    "nattokinase": (["나토키나제", "낫토키나제", "나토배양물", "nattokinase"], []),
    "hovenia": (["헛개"], []),
    "lactoferrin": (["락토페린", "lactoferrin"], []),
    "red-ginseng": (["홍삼"], ["혈소판 응집억제"]),
    "glucosamine": (["글루코사민"], []),
    "msm": (["msm", "optimsm", "엠에스엠", "디메틸설폰", "식이유황", "메틸설포닐메탄"], []),   # 'msm' 은 단어 경계 검사 → OptiMSM·엠에스엠 표기는 따로
    "collagen": (["콜라겐"], []),
    "green-tea-extract": (["녹차추출물", "카테킨", "egcg"], []),
    "curcumin": (["커큐민", "강황", "울금", "터메릭", "테라큐민"], []),
    "arginine": (["아르기닌", "알지닌", "시트룰린"], []),
    "theanine": (["테아닌"], ["긴장 완화"]),
    "saw-palmetto": (["쏘팔메토", "소팔메토", "로르산"], ["전립선 건강"]),
    "garcinia": (["가르시니아", "hca", "하이드록시시트르산"], ["탄수화물이 지방으로 합성되는 것을 억제"]),
    "ginkgo": (["은행잎", "징코"], []),
    "psyllium": (["차전자피", "질경이씨", "차전자", "사일리움"], []),
    "l-carnitine": (["카르니틴"], []),
    "boswellia": (["보스웰리아", "유향", "보스웰릭산", "akba"], []),
    "phosphatidylserine": (["포스파티딜세린", "ps"], ["인지력 개선"]),   # '피에스'는 '피에스트로'(피부 제품) 오탐 → 단어 경계 검사되는 'ps'로
    "propolis": (["프로폴리스"], ["구강에서의 항균"]),
    # 2026-10 추가 성분. 크롬·비타민B6 는 영양소지만 종합비타민 판정(NUTRIENT_RULES 5종 이상)이 바뀌지 않도록 여기서 이름·문구로만 연결
    "chromium": (["크롬"], ["체내 탄수화물, 지방, 단백질 대사에 관여"]),
    "vitamin-b6": (["비타민b6", "비타민 b6", "피리독신"], ["단백질 및 아미노산 이용에 필요"]),
    "hyaluronic-acid": (["히알루론산"], []),                                 # '피부 보습' 문구는 콜라겐·세라마이드와 겹쳐 이름으로만
    "astaxanthin": (["아스타잔틴", "헤마토코쿠스"], ["눈의 피로도 개선"]),
    "policosanol": (["폴리코사놀", "사탕수수왁스알코올"], []),
    "rhodiola": (["홍경천"], ["스트레스로 인한 피로 개선", "스트레스로 인한 피로개선"]),
    # 2026-10 추가 성분 2차. 공유되는 기능성 문구('식후 혈당상승 억제', '면역과민반응…')는 다른 원료와 겹쳐 이름으로만 연결
    "gla": (["감마리놀렌산", "달맞이꽃종자유", "달맞이꽃 종자유", "보라지유"], []),
    "aloe-gel": (["알로에 겔", "알로에겔", "알로에베라겔", "알로에 베라겔", "알로에베라 겔"], []),   # 알로에 전잎(배변) 제품은 제외
    "cla": (["공액리놀레산", "cla", "토날린"], ["과체중인 성인의 체지방 감소"]),
    "red-yeast-rice": (["홍국", "모나콜린"], []),
    "fos": (["프락토올리고당"], ["장내 유익균 증식 및 배변활동 원활"]),
    "banaba": (["바나바", "코로솔산"], []),
    "indigestible-dextrin": (["난소화성말토덱스트린", "난소화성 말토덱스트린"], []),
    "garlic": (["마늘", "흑마늘"], ["콜레스테롤 개선·혈압조절", "콜레스테롤 개선‧혈압조절", "콜레스테롤 개선 · 혈압조절"]),
    "bitter-melon": (["여주", "미숙여주"], []),
    # 3차 추가. '관절 및 연골 건강'·'갱년기 여성 건강'·'뼈 건강' 문구는 여러 원료가 공유해 이름으로만 연결
    "octacosanol": (["옥타코사놀"], ["지구력 증진"]),
    "soy-isoflavone": (["대두이소플라본", "이소플라본"], []),
    "chondroitin": (["콘드로이친", "뮤코다당", "소연골"], []),
    "green-lipped-mussel": (["초록입홍합", "리프리놀", "녹색홍합"], []),
    "sophora": (["회화나무"], []),
    "lactium": (["락티움", "유단백가수분해물"], []),
    "cynanchum": (["백수오"], []),
    "ecklonia": (["감태"], []),
    "pomegranate": (["석류추출물", "석류 추출물", "석류농축분말", "석류농축", "석류엑기스"], []),   # '석류' 단독은 석류맛 제품 오탐
    "chitosan": (["키토산", "키토올리고당"], []),
    "pycnogenol": (["피크노제놀", "프랑스해안송", "소나무껍질추출물"], []),
    "pga": (["폴리감마글루탐산"], ["칼슘흡수 촉진", "칼슘 흡수 촉진"]),
    "ginseng": (["인삼", "고려인삼"], []),   # 홍삼은 red-ginseng 규칙('홍삼')이 따로 잡음
    "spirulina": (["스피루리나", "스피룰리나"], []),   # 청색소(스피루리나청색소)는 EXCIPIENT_RE 로 제외
    "chlorella": (["클로렐라"], []),
    "phytosterol": (["식물스테롤", "파이토스테롤", "식물성스테롤", "식물성 스테롤"], []),
    "coleus-forskohlii": (["콜레우스포스콜리", "콜레우스 포스콜리", "포스콜리", "포스콜린"], []),
    "pu-erh": (["보이차추출물", "보이차 추출물", "보이차추출분말"], []),   # '보이차' 단독은 차 음료 오탐 가능
    "creatine": (["크레아틴"], ["근력 운동 시에 운동수행능력"]),
    "fgo": (["유산균발효굴", "fgo"], []),   # '발효굴추출물' 단독은 FSO(근력)와 겹침
    "ht042": (["황기추출물 등 복합물", "황기추출물등복합물", "ht042"], []),
}
MULTIVITAMIN_MIN = 5           # 영양소 5종 이상이면 종합비타민·미네랄로도 분류
B_SINGLE_IDS = {"vitamin-b1", "vitamin-b2", "niacin", "pantothenic-acid"}   # B군 복합제 규칙과 중복되므로 종합비타민 판정 수에서 제외
# 비타민C·E 는 산화방지제(첨가물)로도 쓰여 원재료 뒷부분에 '비타민C', 'd-α-토코페롤'로 흔히 등장한다.
# 기능성 문구에 이름이 없고 공유 문구(유해산소…)만 있을 때는 (고시형) 표기·주원료 범위·'혼합제제'(영양 프리믹스)일 때만 영양 성분으로 본다.
ADDITIVE_PRONE = {"vitamin-c", "vitamin-e"}
_TAG_RE = r"[^,;()]{0,12}\((?:고시형|개별인정형|개별인정|고시)\)"
_SHORT_ASCII_RE = re.compile(r"^[a-z0-9\-]{1,4}$")


def kw_in(k: str, text: str) -> bool:
    """키워드 포함 검사. 짧은 영문 약어(epa·dha·hca·msm·rtg 등)는 단어 경계를 요구해 Hepazone·Ashwagandha·Healthcare 같은 오탐을 막는다. 're:' 로 시작하면 정규식."""
    if k.startswith("re:"):   # 정규식 키워드 — 뒤따르는 글자를 제한할 때('글루타민(?!산)')
        return re.search(k[3:], text) is not None
    if _SHORT_ASCII_RE.match(k):
        return re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text) is not None
    if k[-1].isdigit():   # '비타민b1' 이 '비타민b12' 에, 'b6' 가 'b60' 에 걸리지 않게 뒤에 숫자가 이어지면 제외
        return re.search(re.escape(k) + r"(?!\d)", text) is not None
    return k in text


def build_matchers(ingredients: list[dict]):
    """ingredients.json 에 있는 성분만 규칙에서 골라 반환 (규칙 없는 성분은 이름·별칭으로 원료 규칙 생성)."""
    nut, herb = {}, {}
    for it in ingredients:
        iid = it["id"]
        if iid in NUTRIENT_RULES:
            nut[iid] = NUTRIENT_RULES[iid]
        elif iid in HERBAL_RULES:
            herb[iid] = HERBAL_RULES[iid]
        elif iid != "multivitamin":
            kws = [it["name"].split(" (")[0]] + [a for a in it.get("aliases", []) if len(a) >= 3 and not re.fullmatch(r"[A-Za-z]{1,2}", a)]
            herb[iid] = ([k.lower() for k in kws], [])
    return nut, herb


def match_ingredients(row: dict, matchers) -> list[str]:
    nut, herb = matchers
    name = (row.get("PRDLST_NM") or "").lower()
    func = (row.get("PRIMARY_FNCLTY") or "").lower()
    raw = EXCIPIENT_RE.sub(" ", (row.get("RAWMTRL_NM") or "")).lower()
    raw_head = raw[:RAW_HEAD]
    found: list[str] = []
    for iid, (names, claims, shared, fn_name_ok) in nut.items():
        hit = any(kw_in(k, name) for k in names) or any(c in func for c in claims)
        if not hit and fn_name_ok:
            hit = any(kw_in(k, func) for k in names)
        if not hit and shared and shared in func:
            hits = [k for k in names if kw_in(k, raw)]
            if hits and iid in ADDITIVE_PRONE:
                hits = [k for k in hits if k in raw_head or re.search(re.escape(k) + _TAG_RE, raw) or re.search(re.escape(k) + r"\s*혼합제제", raw)]
            hit = bool(hits)
        if hit:
            found.append(iid)
    nutrient_count = sum(1 for i in found if i not in B_SINGLE_IDS)
    for iid, (kws, claims) in herb.items():
        if any(kw_in(k, name) for k in kws) or any(kw_in(k, func) for k in kws) or any(kw_in(k, raw_head) for k in kws) or any(c in func for c in claims):
            found.append(iid)
    if nutrient_count >= MULTIVITAMIN_MIN:
        found.append("multivitamin")
    return found


def api_get(key: str, service: str, start: int, end: int) -> dict:
    url = f"{API_BASE}/{key}/{service}/json/{start}/{end}"
    safe_url = url.replace(key, "***")
    last_err: Exception | None = None
    for attempt in range(1, RETRY + 1):
        wait = 5 * attempt
        try:
            r = requests.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            r.raise_for_status()
            data = r.json()
            body = data.get(service) or {}
            result = body.get("RESULT", {})
            code = result.get("CODE", "")
            if code and code != "INFO-000":
                if code == "INFO-200":   # 해당하는 데이터가 없습니다
                    return {"row": [], "total_count": body.get("total_count", "0")}
                if code == "INFO-500":   # 현재 접속 중인 인증키입니다 → 이전 요청이 아직 처리 중
                    wait = WAIT_WHEN_BUSY
                raise RuntimeError(f"API 오류 {code}: {result.get('MSG')}")
            return body
        except requests.exceptions.ReadTimeout as e:
            last_err = e
            wait = WAIT_AFTER_TIMEOUT
            log.warning("API 응답 지연 (%d/%d) %s: %ds 내 응답 없음 → %ds 대기 후 재시도", attempt, RETRY, safe_url, READ_TIMEOUT, wait)
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("API 호출 실패 (%d/%d) %s: %s → %ds 대기 후 재시도", attempt, RETRY, safe_url, e, wait)
        if attempt < RETRY:
            time.sleep(wait)
    raise RuntimeError(f"API 호출 반복 실패: {last_err}")


def fetch_rows(key: str, service: str, max_rows: int) -> tuple[list[dict], int]:
    """마지막 페이지(최신 신고)부터 거꾸로 max_rows 만큼 수집."""
    probe = api_get(key, service, 1, 1)
    total = int(probe.get("total_count") or 0)
    if total <= 0:
        return [], 0
    limit = min(total, max_rows) if max_rows else total
    floor = total - limit + 1
    log.info("총 %s건 (서비스 %s) → 최신 %s건 수집 (행 %s~%s)", f"{total:,}", service, f"{limit:,}", f"{floor:,}", f"{total:,}")
    rows: list[dict] = []
    end = total
    while end >= floor:
        start = max(end - PAGE + 1, floor)
        body = api_get(key, service, start, end)
        chunk = body.get("row") or []
        if not chunk:
            log.warning("행 %s~%s 응답이 비어 있어 중단", f"{start:,}", f"{end:,}")
            break
        rows.extend(chunk)
        dates = [r.get("PRMS_DT", "") for r in chunk if r.get("PRMS_DT")]
        log.info("수집 %s / %s (행 %s~%s · 신고일 %s~%s)", f"{len(rows):,}", f"{limit:,}", f"{start:,}", f"{end:,}", min(dates) if dates else "?", max(dates) if dates else "?")
        end = start - 1
        time.sleep(PAUSE_BETWEEN_CALLS)
    return rows, total


def clip(v, n: int) -> str:
    v = re.sub(r"[ \t]+", " ", (v or "")).strip()
    return v if len(v) <= n else v[: n - 1].rstrip() + "…"


def normalize(row: dict, ingredient_ids: list[str]) -> dict:
    name = (row.get("PRDLST_NM") or "").strip()

    def ymd(v: str) -> str:
        v = (v or "").strip()
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if re.fullmatch(r"\d{8}", v) else v

    reg = ymd(row.get("PRMS_DT"))
    return {
        "lastUpdated": ymd(row.get("LAST_UPDT_DTM")),
        "id": (row.get("PRDLST_REPORT_NO") or f"{row.get('LCNS_NO','')}-{name}").strip(),
        "name": name,
        "company": (row.get("BSSH_NM") or "").strip(),
        "reportNo": (row.get("PRDLST_REPORT_NO") or "").strip(),
        "registeredAt": reg,
        "function": clip(row.get("PRIMARY_FNCLTY"), 500),
        "rawMaterials": clip(row.get("RAWMTRL_NM"), 500),
        "intake": clip(row.get("NTK_MTHD"), 300),
        "caution": clip(row.get("IFTKN_ATNT_MATR_CN"), 400),
        "shape": (row.get("PRDT_SHAP_CD_NM") or "").strip(),
        "shelfLife": (row.get("POG_DAYCNT") or "").strip(),
        "ingredients": ingredient_ids,
        "shopQuery": re.sub(r"\s+", " ", re.sub(r"[\[\]\(\)【】]", " ", name))[:40].strip(),
        "source": "mfds",
    }


NEW_WITHIN_DAYS = 90           # 이 기간 안에 신고된 제품만 '신규'로 기록 (성분별 상한 경계에서 끼어드는 옛 제품 제외)


def diff_changelog(old_items: list[dict], new_items: list[dict], window_oldest: str = "", still_present: set | None = None) -> dict:
    """old → new 비교. window_oldest(YYYY-MM-DD) 이후 신고분만 이번 수집 범위이므로 삭제 판정은 그 안에서만.
    still_present: 이번 수집에서 여전히 확인된(상한 때문에 목록에서만 빠진) 제품 id — 삭제로 기록하지 않음."""
    from datetime import date, timedelta
    recent_cutoff = (date.today() - timedelta(days=NEW_WITHIN_DAYS)).isoformat()
    old = {p["id"]: p for p in old_items if p.get("source") != "sample"}
    new = {p["id"]: p for p in new_items}
    entries = []
    for pid, p in new.items():
        if pid not in old:
            if (p.get("registeredAt") or "") >= recent_cutoff:
                entries.append({"type": "added", "name": p["name"], "company": p["company"], "id": pid})
        else:
            o = old[pid]
            for field, label in (("name", "제품명"), ("function", "기능성"), ("rawMaterials", "원재료"), ("caution", "주의사항"), ("intake", "섭취방법"), ("lastUpdated", "식약처 정보 갱신")):
                if (o.get(field) or "") != (p.get(field) or ""):
                    entries.append({"type": "changed", "name": p["name"], "company": p["company"], "id": pid, "field": label})
                    break
    for pid, o in old.items():
        if pid in new or (still_present and pid in still_present):
            continue
        if not window_oldest or (o.get("registeredAt") or "") >= window_oldest:
            entries.append({"type": "removed", "name": o["name"], "company": o.get("company", ""), "id": pid})
    counts = {t: sum(1 for e in entries if e["type"] == t) for t in ("added", "removed", "changed")}
    return {"updatedAt": now_iso(), "added": counts["added"], "removed": counts["removed"], "changed": counts["changed"], "items": entries[:CHANGELOG_KEEP]}


INDEX_FUNCTION_CHARS = 110     # 목록 파일에 넣을 기능성 요약 길이
INDEX_FIELDS = ("id", "name", "company", "registeredAt", "shape", "ingredients")
LIST_RECENT_ITEMS = 600        # products.json 에 싣는 최신 신고 제품 수(첫 화면과 앞 25페이지). 전체 목록은 products/all.json 으로 분리
FULL_DIR_NAME = "products"     # data/products/top/<성분id>.json(성분별 상위), data/products/detail/<NN>.json(전체 레코드 조각), data/products/all.json(목록 전체)
TOP_PER_INGREDIENT = 60        # 성분 상세 페이지용 성분별 상위 제품 수
DETAIL_SHARDS = 64             # 전체 레코드 조각 파일 수


def shard_of(pid: str) -> str:
    """제품 id → 조각 파일 번호. assets/js/data.js 의 productShard() 와 동일해야 합니다."""
    h = 0
    for ch in pid:
        h = (h * 31 + ord(ch)) % 1000003
    return f"{h % DETAIL_SHARDS:02d}"


def load_full_records(data_dir: Path) -> dict[str, dict]:
    """성분별 상세 파일에 저장된 전체 레코드를 id 기준으로 합쳐 반환."""
    out: dict[str, dict] = {}
    for f in sorted((data_dir / FULL_DIR_NAME / "detail").glob("*.json")):
        for p in (read_json(f, {}) or {}).get("items", []):
            out.setdefault(p["id"], p)
    return out


def item_to_row(p: dict) -> dict:
    """저장된 레코드를 API 행 형식으로 되돌림 (--rebuild 용)."""
    return {
        "PRDLST_NM": p.get("name", ""), "BSSH_NM": p.get("company", ""), "PRDLST_REPORT_NO": p.get("reportNo") or p.get("id", ""),
        "PRMS_DT": (p.get("registeredAt") or "").replace("-", ""), "LAST_UPDT_DTM": (p.get("lastUpdated") or "").replace("-", ""),
        "PRIMARY_FNCLTY": p.get("function", ""), "RAWMTRL_NM": p.get("rawMaterials", ""), "NTK_MTHD": p.get("intake", ""),
        "IFTKN_ATNT_MATR_CN": p.get("caution", ""), "PRDT_SHAP_CD_NM": p.get("shape", ""), "POG_DAYCNT": p.get("shelfLife", ""),
    }


def robust_oldest(dates: list[str]) -> str:
    """수집 범위의 '최초 신고일' — 순서가 어긋난 소수의 옛 행을 무시하기 위해 하위 2% 지점을 사용."""
    ds = sorted(d for d in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d))
    if not ds:
        return ""
    return ds[min(len(ds) - 1, int(len(ds) * 0.02))]


def focus_sort_key(p: dict, iid: str, kws: list[str]):
    """성분별 목록 정렬: 제품명에 성분이 드러나는 단일 목적 제품 → 성분 수 적은 순 → 최신순."""
    nm = p["name"].lower()
    named = any(k in nm for k in kws)
    return (0 if named else 1, len(p["ingredients"]), p["registeredAt"] and -int(p["registeredAt"].replace("-", "") or 0))


def write_outputs(data_dir: Path, items: list[dict], meta: dict, changelog: dict, matchers, all_items: list[dict] | None = None) -> None:
    """items: 제품 찾기 목록용(성분별 상한 적용) · all_items: 매칭된 전체(상세 조각·성분별 상위·검색 색인의 바탕)."""
    all_items = all_items if all_items is not None else items
    nut, herb = matchers
    kw_by_id = {iid: r[0] for iid, r in nut.items()} | {iid: r[0] for iid, r in herb.items()} | {"multivitamin": ["멀티비타민", "종합비타민", "멀티미네랄", "종합영양제"]}
    # 1) 목록 파일 (가벼움, 압축 JSON): 제품 찾기 페이지·홈 통계용
    index_items = []
    for p in items:
        slim = {k: p.get(k) for k in INDEX_FIELDS}
        slim["f"] = clip(p.get("function"), INDEX_FUNCTION_CHARS)
        if p.get("shopQuery") and p["shopQuery"] != p["name"]:
            slim["shopQuery"] = p["shopQuery"]
        if p.get("isNew"):
            slim["isNew"] = True
        index_items.append(slim)
    full_dir = data_dir / FULL_DIR_NAME
    top_dir, detail_dir = full_dir / "top", full_dir / "detail"
    top_dir.mkdir(parents=True, exist_ok=True)
    # products.json 에는 최신 LIST_RECENT_ITEMS 건(첫 화면·앞 페이지)만 싣고, 전체 목록은 products/all.json 으로 분리해
    # 제품 찾기 페이지가 필터·검색·뒷페이지에서만 불러오게 한다 (전체 약 3MB 를 첫 화면마다 받지 않도록)
    index_items.sort(key=lambda x: x.get("registeredAt") or "", reverse=True)
    shapes = sorted({p["shape"] for p in index_items if p.get("shape")})
    list_meta = meta | {"listed": min(LIST_RECENT_ITEMS, len(index_items)), "shapes": shapes, "files": (meta.get("files") or {}) | {"all": f"data/{FULL_DIR_NAME}/all.json"}}
    write_json(data_dir / "products.json", {"_meta": list_meta, "changelog": changelog, "items": index_items[:LIST_RECENT_ITEMS]}, compact=True)
    write_json(full_dir / "all.json", {"_meta": {"updatedAt": meta.get("updatedAt"), "total": len(index_items)}, "items": index_items}, compact=True, quiet=True)
    detail_dir.mkdir(parents=True, exist_ok=True)
    # 2) 성분별 상위 제품 (성분 상세 페이지용)
    by_ing: dict[str, list[dict]] = {}
    for p in all_items:
        for iid in p["ingredients"]:
            by_ing.setdefault(iid, []).append(p)
    wanted = set()
    for iid, plist in by_ing.items():
        plist.sort(key=lambda p: focus_sort_key(p, iid, kw_by_id.get(iid, [])))
        write_json(top_dir / f"{iid}.json", {"_meta": {"ingredient": iid, "updatedAt": meta["updatedAt"], "total": len(plist)}, "items": plist[:TOP_PER_INGREDIENT]}, compact=True, quiet=True)
        wanted.add(f"{iid}.json")
    for stale in top_dir.glob("*.json"):
        if stale.name not in wanted:
            stale.unlink()
    # 3) 전체 레코드 조각 (제품 페이지·'더보기'·검색 색인용, 상한 없이 매칭된 전체, 중복 없음)
    shards: dict[str, list[dict]] = {}
    for p in all_items:
        shards.setdefault(shard_of(p["id"]), []).append(p)
    for n in range(DETAIL_SHARDS):
        key = f"{n:02d}"
        write_json(detail_dir / f"{key}.json", {"items": shards.get(key, [])}, compact=True, quiet=True)
    log.info("저장: 목록 %s건 · 성분별 상위 %d개 파일 · 상세 조각 %d개 파일(전체 %s건)", f"{len(items):,}", len(wanted), DETAIL_SHARDS, f"{len(all_items):,}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="API 호출 없이 기존 파일 유지")
    ap.add_argument("--rebuild", action="store_true", help="API 호출 없이 저장된 상세 레코드로 매칭·파일을 다시 생성")
    args = ap.parse_args()

    out_path = DATA_DIR / "products.json"
    existing = read_json(out_path, {"_meta": {}, "changelog": {}, "items": []})
    existing_meta = existing.get("_meta", {})
    was_sample = existing_meta.get("source") == "sample"
    full_prev = {} if was_sample else load_full_records(DATA_DIR)
    # 이전 데이터가 구버전(단일 파일에 전체 레코드)이면 그 레코드를 상세 레코드로 사용
    if not was_sample and not full_prev:
        full_prev = {p["id"]: p for p in existing.get("items", []) if p.get("rawMaterials") is not None}
    service = env("FOODSAFETY_SERVICE", existing_meta.get("service") or "C003")
    ingredients = load_ingredients()
    matchers = build_matchers(ingredients)

    if args.rebuild:
        if was_sample or not full_prev:
            log.warning("재구성할 저장 데이터가 없습니다.")
            return 0
        rows = [item_to_row(p) for p in full_prev.values()]
        total = existing_meta.get("apiTotal") or len(rows)
        log.info("저장된 레코드 %s건으로 재구성 (API 호출 없음)", f"{len(rows):,}")
    else:
        key = env("FOODSAFETY_API_KEY")
        if args.sample or not key:
            log.warning("FOODSAFETY_API_KEY 가 없어 제품 수집을 건너뜁니다. 기존 데이터(%s)를 유지합니다.", existing_meta.get("source", "?"))
            return 0
        max_rows = int(env("FOODSAFETY_MAX_ROWS", str(DEFAULT_MAX_ROWS)) or 0)
        rows, total = fetch_rows(key, service, max_rows)
        if not rows:
            log.warning("수집된 행이 없어 기존 데이터를 유지합니다.")
            return 0

    items: dict[str, dict] = {}
    for row in rows:
        ids = match_ingredients(row, matchers)
        if not ids:
            continue
        p = normalize(row, ids)
        if not p["name"]:
            continue
        items[p["id"]] = p
    matched_now = set(items.keys())
    window_oldest = robust_oldest([p["registeredAt"] for p in items.values()])
    log.info("성분 매칭 제품 %s건 / %s행 (수집 범위 최초 신고일 %s)", f"{len(items):,}", f"{len(rows):,}", window_oldest or "?")

    # 이전 수집분 중 이번 범위보다 오래된 제품은 그대로 유지 (갱신은 못 하지만 사라지지도 않음)
    if not args.rebuild:
        for pid, p in full_prev.items():
            if p.get("source") == "mfds" and pid not in items and window_oldest and (p.get("registeredAt") or "") < window_oldest:
                items[pid] = p

    # 성분별 상한 적용 (최신 신고순)
    per: dict[str, int] = {}
    kept: dict[str, dict] = {}
    for p in sorted(items.values(), key=lambda x: x["registeredAt"], reverse=True):
        if any(per.get(iid, 0) < PER_INGREDIENT_CAP for iid in p["ingredients"]):
            kept[p["id"]] = p
            for iid in p["ingredients"]:
                per[iid] = per.get(iid, 0) + 1

    new_items = sorted(kept.values(), key=lambda x: x["registeredAt"], reverse=True)          # 제품 찾기 목록 (상한 적용)
    all_items = sorted(items.values(), key=lambda x: x["registeredAt"], reverse=True)         # 상세 조각·검색 색인 (매칭된 전체)
    for p in all_items:
        p.pop("isNew", None)
    # 샘플→실데이터 첫 전환, 매칭 규칙 변경, 재구성 시에는 변경 이력을 새로 시작
    baseline = was_sample or args.rebuild or existing_meta.get("matcherVersion") != MATCHER_VERSION
    changelog = {"updatedAt": now_iso(), "added": 0, "removed": 0, "changed": 0, "items": []} if baseline else diff_changelog(list(full_prev.values()), all_items, window_oldest, matched_now)
    added_ids = {e["id"] for e in changelog["items"] if e["type"] == "added"}
    for p in all_items:
        if p["id"] in added_ids:
            p["isNew"] = True

    meta = {
        "source": "mfds",
        "sourceLabel": "식품의약품안전처 식품안전나라 건강기능식품 품목제조신고",
        "service": service,
        "updatedAt": now_iso() if not args.rebuild else (existing_meta.get("updatedAt") or now_iso()),
        "rebuiltAt": now_iso() if args.rebuild else None,
        "total": len(new_items),
        "indexed": len(all_items),
        "scanned": len(rows),
        "apiTotal": total,
        "windowOldest": window_oldest,
        "matcherVersion": MATCHER_VERSION,
        "files": {"top": f"data/{FULL_DIR_NAME}/top/<ingredientId>.json", "detail": f"data/{FULL_DIR_NAME}/detail/<shard>.json", "shards": DETAIL_SHARDS},
    }
    write_outputs(DATA_DIR, new_items, meta, changelog, matchers, all_items)
    log.info("완료: 목록 %s건 · 검색 색인 대상 %s건 (신규 %d · 변경 %d · 삭제 %d)%s", f"{len(new_items):,}", f"{len(all_items):,}", changelog["added"], changelog["changed"], changelog["removed"], " · 변경 이력 초기화" if baseline else "")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("제품 수집 실패: %s — 기존 데이터를 유지합니다.", e)
        if env("CI"):
            print(f"::warning title=제품 수집 실패::{e} — 기존 products.json 유지")
            sys.exit(0)
        sys.exit(1)
