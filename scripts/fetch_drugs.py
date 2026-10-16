#!/usr/bin/env python3
"""
식약처(공공데이터포털) 의약품 정보를 수집해 제품명 검색·의약품 상세 페이지용 데이터를 만듭니다.

  1) e약은요(의약품개요정보) — 일반의약품 중심 약 4,700건의 효능·사용법·주의사항·상호작용·부작용·보관법
  2) 의약품 제품 허가정보(목록) — 주성분명·전문/일반 구분·분류 (품목기준코드로 1)과 연결)

사용법:
  DATA_GO_KR_KEY=발급키 python scripts/fetch_drugs.py
  python scripts/fetch_drugs.py --rebuild     # API 호출 없이 저장된 레코드로 성분 매칭·파일 재생성

API 키 발급: https://www.data.go.kr 회원가입 → 아래 두 API 를 '활용신청'(개발계정은 자동 승인) → 마이페이지 → 일반 인증키(Decoding)
  - 식품의약품안전처_의약품개요정보(e약은요)     DrbEasyDrugInfoService
  - 식품의약품안전처_의약품 제품 허가정보        DrugPrdtPrmsnInfoService06
환경변수:
  DATA_GO_KR_KEY        필수. 없으면 기존 파일을 유지하고 정상 종료합니다. (Encoding 키를 넣어도 자동으로 풀어 씁니다)
  DRUG_API_BUDGET       선택. 한 번 실행에서 허용할 API 호출 수 (기본 900 — 공공데이터포털 개발계정 일일 1,000건 기준)
  DRUG_TIME_BUDGET      선택. 한 번 실행에서 허용할 시간(초, 기본 780). 넘으면 허가정보 연결을 멈추고 받은 것까지 저장
  DRUG_MAX_ROWS         선택. e약은요 수집 상한 (기본 0 = 전체)
  DRUG_API_BASE / DRUG_EASY_SERVICE / DRUG_PERMIT_SERVICE   선택. 주소·서비스 경로가 바뀌었을 때 덮어쓰기

동작 방식:
  - e약은요는 매번 전체를 다시 받습니다(100건씩 약 50회).
  - 허가정보(주성분)는 품목기준코드별로 data/drugs/permit.json 에 캐시합니다. 처음에는 목록을 통째로 넘기며 채우고,
    그 뒤로는 캐시에 없는 신규 품목만 개별 조회합니다. 호출 예산을 넘기면 나머지는 다음 실행으로 미룹니다.
  - 의약품 주성분 중 성분 사전(data/ingredients.json)에 있는 영양소(비타민·미네랄·유산균 등)를 찾아 연결합니다.
    약물 염(아토르바스타틴칼슘 등)·제산제(수산화마그네슘)·외용제(연고·크림의 산화아연)는 영양 성분으로 보지 않습니다.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_priority import load_brand_priority  # noqa: E402
from common import DATA_DIR, env, load_ingredients, log, now_iso, read_json, write_json  # noqa: E402
from drug_ingr_ko import to_korean  # noqa: E402

DEFAULT_API_BASE = "https://apis.data.go.kr/1471000"
DEFAULT_EASY_SERVICE = "DrbEasyDrugInfoService/getDrbEasyDrugList"
DEFAULT_PERMIT_SERVICE = "DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnInq06"
# 허가정보 API 는 식약처가 스키마를 바꿀 때마다 서비스 버전(…Service06)과 오퍼레이션 번호가 올라간다.
# 기본 경로가 400/404 를 돌려주면 아래 후보를 차례로 1회씩 찔러 보고 품목 필드(ITEM_SEQ)가 오는 첫 경로를 쓴다.
PERMIT_CANDIDATES = [
    "DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnInq06", "DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnDtlInq05",
    "DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07", "DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
    "DrugPrdtPrmsnInfoService08/getDrugPrdtPrmsnInq08", "DrugPrdtPrmsnInfoService08/getDrugPrdtPrmsnDtlInq07",
    "DrugPrdtPrmsnInfoService05/getDrugPrdtPrmsnInq05", "DrugPrdtPrmsnInfoService05/getDrugPrdtPrmsnDtlInq04",
]
DEFAULT_TIME_BUDGET = 780      # 실행당 허용 시간(초). 워크플로 단계 제한(20분) 전에 멈추고 받은 것까지 저장한다
MAX_CONSECUTIVE_FAILS = 5      # 개별 조회가 연속으로 이만큼 실패하면 API 쪽 문제로 보고 중단
PAGE = 100                     # 공공데이터포털 numOfRows 상한
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 60              # e약은요는 페이지당 1~3초, 느릴 때 15초 이상
RETRY = 3
PAUSE_BETWEEN_CALLS = 0.3
DEFAULT_BUDGET = 900
BULK_THRESHOLD = 150           # 허가정보가 없는 품목이 이보다 많으면 개별 조회 대신 목록 전체를 넘긴다
BULK_MAX_PAGES = 600           # 목록 전체 순회 상한 (약 6만 건)
TEXT_LIMIT = 3000              # e약은요 본문 항목별 보관 글자 수
DETAIL_SHARDS = 128            # data/drugs/detail/<NNN>.json 조각 수 (assets/js/data.js 의 drugShard() 와 동일)
INGR_TOKENS_MAX = 12
MATCHER_VERSION = 3            # 2: 영문 주성분 규칙·한글 표시 사전 / 3: 용법 기반 외용 제외, 약물 염 제외, 사전 보강

DIR_NAME = "drugs"
OTC_FLAG = {"일반의약품": 1, "전문의약품": 2}

# 공공데이터포털 공통 오류 코드 → 조치 안내
PORTAL_ERRORS = {
    "01": "APPLICATION_ERROR (제공기관 서비스 오류)", "02": "DB_ERROR", "03": "NODATA_ERROR", "04": "HTTP_ERROR", "05": "SERVICETIME_OUT",
    "10": "INVALID_REQUEST_PARAMETER_ERROR (요청 파라미터 오류)", "11": "NO_MANDATORY_REQUEST_PARAMETERS_ERROR",
    "12": "NO_OPENAPI_SERVICE_ERROR (없는 서비스 — API 주소·버전이 바뀌었는지 확인: DRUG_EASY_SERVICE / DRUG_PERMIT_SERVICE)",
    "20": "SERVICE_ACCESS_DENIED_ERROR (활용신청이 승인되지 않은 API)", "21": "TEMPORARILY_DISABLE_THE_SERVICEKEY_ERROR",
    "22": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR (일일 트래픽 초과 — 내일 다시 실행)",
    "30": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR (등록되지 않은 키 — data.go.kr 에서 이 API 를 활용신청했는지, 마이페이지의 일반 인증키를 썼는지 확인)",
    "31": "DEADLINE_HAS_EXPIRED_ERROR (키 기한 만료 — 활용신청 연장)", "32": "UNREGISTERED_IP_ERROR", "33": "UNSIGNED_CALL_ERROR", "99": "UNKNOWN_ERROR",
}


class PortalError(RuntimeError):
    """공공데이터포털이 돌려준 오류 (키·권한·파라미터 문제 — 재시도해도 같으므로 바로 중단)."""


class QuotaExceeded(PortalError):
    """일일 트래픽 초과 또는 실행당 호출 예산 소진."""


# ---------------------------------------------------------------- 성분 매칭 규칙
NUTRIENT_IDS = {"vitamin-a", "vitamin-c", "vitamin-d", "vitamin-e", "vitamin-k", "vitamin-b-complex", "vitamin-b12", "folate", "biotin",
                "calcium", "magnesium", "zinc", "iron", "selenium", "copper", "manganese", "molybdenum", "iodine", "potassium"}
MULTIVITAMIN_MIN = 5

# 미네랄은 '영양 보급용 염'일 때만 인정 (토큰 전체에 대해 앞부분부터 검사). 약물의 염(아토르바스타틴칼슘), 제산제(수산화마그네슘) 제외
SALT_RULES: dict[str, re.Pattern] = {
    "calcium": re.compile(r"^(탄산|구연산|시트르산|글루콘산|젖산|인산수소|제이인산|제삼인산|아세트산|염화|글리세로인산|아스파르트산|l-아스파르트산|우유|산호|해조|침강탄산)?칼슘(?!도베실|도부실)"
                          r"|^(precipitated |dried |tribasic |dibasic |tricalcium |dicalcium )?calcium( (carbonate|citrate|gluconate|lactate|phosphate|hydrogen ?phosphate|acetate|chloride|glycerophosphate|aspartate|l-aspartate|hydroxyapatite|lactate gluconate)|$)"
                          r"|^(dibasic|tribasic) calcium phosphate|^oyster shell"),
    "magnesium": re.compile(r"^(산화|경질산화|중질산화|탄산|구연산|시트르산|글루콘산|젖산|염화|인산수소|아스파르트산|l-아스파르트산|글리시네이트|비스글리시네이트|피돌산|오로트산|중)?마그네슘"
                            r"|^(light |heavy )?magnesium( (oxide|carbonate|citrate|gluconate|lactate|chloride|aspartate|l-aspartate|glycerophosphate|glycinate|bisglycinate|pidolate|orotate|sulfate|hydrogen ?phosphate)|$)"),
    "zinc": re.compile(r"^(산화|황산|글루콘산|피콜린산|구연산|아세트산|아스파르트산|l-아스파르트산|히스티딘|킬레이트)?아연"
                       r"|^zinc( (oxide|sulfate|gluconate|picolinate|citrate|acetate|aspartate|chloride|bisglycinate|histidine)|$)"),
}
# 토큰 안에 들어 있으면 인정
CONTAIN_RULES: dict[str, list[str]] = {
    "vitamin-a": ["레티놀", "레티닐", "비타민a", "베타카로틴", "베타-카로틴", "retinol", "retinyl", "beta-carotene", "betacarotene", "vitamin a"],
    "vitamin-c": ["아스코르브산", "아스코르빈산", "아스코브산", "아스코르베이트", "비타민c", "ascorbic acid", "ascorbate", "vitamin c"],
    "vitamin-d": ["콜레칼시페롤", "에르고칼시페롤", "비타민d", "cholecalciferol", "ergocalciferol", "vitamin d"],
    "vitamin-e": ["토코페롤", "토코페릴", "비타민e", "tocopherol", "tocopheryl", "tocotrienol", "vitamin e"],
    "vitamin-k": ["피토나디온", "메나테트레논", "메나디온", "필로퀴논", "비타민k", "phytonadione", "menatetrenone", "menadione", "phylloquinone", "vitamin k"],
    "vitamin-b-complex": ["티아민", "푸르설티아민", "벤포티아민", "비스벤티아민", "옥토티아민", "리보플라빈", "피리독신", "피리독살", "니코틴산아미드", "니아신아미드",
                          "니코틴산", "판토텐산", "덱스판테놀", "판테놀", "비타민b1", "비타민b2", "비타민b6", "비타민b군", "비타민b복합",
                          "thiamine", "fursultiamine", "benfotiamine", "bisbentiamine", "octotiamine", "riboflavin", "pyridoxine", "pyridoxal", "nicotinamide", "niacinamide", "nicotinic acid", "pantothen", "dexpanthenol", "panthenol", "vitamin b1", "vitamin b2", "vitamin b6"],
    "vitamin-b12": ["코발라민", "비타민b12", "cobalamin", "vitamin b12"],
    "folate": ["폴산", "엽산", "폴린산", "메틸폴레이트", "메틸테트라히드로", "folic acid", "folate", "folinate", "folinic", "methyltetrahydrofol"],
    "biotin": ["비오틴", "biotin"],
    "selenium": ["셀레늄", "아셀렌산", "셀레노메티오닌", "셀렌", "selenium", "selenite", "selenomethionine"],
    "iron": ["철", "ferrous", "ferric", "iron", "ferritin"],
    "copper": ["구리", "copper", "cupric"],
    "vitamin-b1": ["티아민", "푸르설티아민", "벤포티아민", "비스벤티아민", "옥토티아민", "비타민b1", "thiamine", "fursultiamine", "benfotiamine", "bisbentiamine", "octotiamine", "vitamin b1"],
    "vitamin-b2": ["리보플라빈", "비타민b2", "riboflavin", "vitamin b2"],
    "niacin": ["니코틴산아미드", "니아신아미드", "니코틴산", "나이아신", "nicotinamide", "niacinamide", "nicotinic acid", "niacin"],
    "pantothenic-acid": ["판토텐산", "덱스판테놀", "판테놀", "pantothen", "dexpanthenol", "panthenol"],
    "manganese": ["망간", "manganese"],
    "molybdenum": ["몰리브덴", "molybdenum", "molybdate"],
    "iodine": ["요오드화칼륨", "요오드화나트륨", "potassium iodide", "sodium iodide"],   # 포비돈요오드·요오드 조영제는 제외
    "potassium": ["염화칼륨", "구연산칼륨", "글루콘산칼륨", "potassium chloride", "potassium citrate", "potassium gluconate"],   # 로사르탄칼륨 같은 염은 제외
    "omega-3": ["오메가-3", "오메가3", "에이코사펜타엔산", "도코사헥사엔산", "omega-3", "omega 3", "eicosapentaenoic", "docosahexaenoic", "fish oil"],
    "probiotics": ["락토바실", "비피도박테리움", "비피더스", "바실루스", "바실러스", "스트렙토코쿠스", "엔테로코쿠스", "락토민", "유산균", "사카로미세스", "클로스트리디움부티리쿰",
                   "lactobacillus", "bifidobacterium", "bacillus", "streptococcus", "enterococcus", "saccharomyces", "clostridium butyricum", "lactomin", "lactic acid bacteria"],
    "lutein": ["루테인", "lutein"],
    "coq10": ["유비데카레논", "코엔자임q10", "유비퀴논", "코큐텐", "ubidecarenone", "coenzyme q10", "ubiquinone", "ubiquinol"],
    "milk-thistle": ["실리마린", "실리빈", "밀크시슬", "밀크씨슬", "카르두스마리아누스", "엉겅퀴", "silymarin", "silybin", "milk thistle", "milk-thistle", "carduus"],
    "red-ginseng": ["홍삼", "red ginseng"],
    "ginseng": ["인삼", "panax", "ginseng"],
    "spirulina": ["스피루리나", "spirulina"],
    "chlorella": ["클로렐라", "chlorella"],
    "phytosterol": ["식물스테롤", "시토스테롤", "phytosterol", "sitosterol"],
    "coleus-forskohlii": ["콜레우스", "포스콜린", "forskolin", "forskohlii"],
    "pu-erh": ["보이차", "pu-erh", "puerh"],
    "glucosamine": ["글루코사민", "glucosamine"],
    "msm": ["메틸설포닐메탄", "디메틸설폰", "methylsulfonylmethane", "dimethyl sulfone"],
    "collagen": ["콜라겐", "collagen"],
    "green-tea-extract": ["녹차", "카테킨", "green tea", "catechin"],
    "curcumin": ["쿠르쿠민", "커큐민", "강황", "울금", "curcumin", "turmeric", "curcuma"],
    "arginine": ["아르기닌", "arginine"],
    "theanine": ["테아닌", "theanine"],
    "saw-palmetto": ["쏘팔메토", "소팔메토", "톱야자", "saw palmetto", "serenoa", "sabal"],
    "garcinia": ["가르시니아", "garcinia"],
    "ginkgo": ["은행엽", "은행잎", "징코", "ginkgo"],
    "psyllium": ["차전자", "질경이씨", "사일리움", "플란타고오바타", "psyllium", "plantago ovata", "plantago seed", "plantaginis semen"],   # 차전초(Plantago Herb, 거담 생약)는 제외
    "l-carnitine": ["카르니틴", "카니틴", "carnitine"],
    "boswellia": ["보스웰리아", "유향", "boswellia", "frankincense"],
    "phosphatidylserine": ["포스파티딜세린", "phosphatidylserine"],
    "propolis": ["프로폴리스", "propolis"],
    # 2026-10 추가 성분 (NUTRIENT_IDS 에는 넣지 않아 종합비타민 판정은 그대로)
    "chromium": ["크롬", "chromium", "chromic chloride"],
    "vitamin-b6": ["피리독신", "피리독살", "비타민b6", "pyridoxine", "pyridoxal", "vitamin b6"],
    "hyaluronic-acid": ["히알루론산", "hyaluron"],
    "astaxanthin": ["아스타잔틴", "astaxanthin", "haematococcus"],
    "policosanol": ["폴리코사놀", "policosanol"],
    "rhodiola": ["홍경천", "rhodiola"],
    "gla": ["감마리놀렌산", "달맞이꽃", "gamma-linolenic", "evening primrose"],
    "red-yeast-rice": ["홍국", "red yeast"],
    "fos": ["프락토올리고당", "fructooligosaccharide"],
    "garlic": ["마늘", "garlic", "allium sativum"],
    "chondroitin": ["콘드로이친", "chondroitin"],
    "bitter-melon": ["여주", "momordica", "bitter melon"],
    # 알로에(의약품은 완하제용 전잎)·바나바·CLA·난소화성말토덱스트린은 의약품 연결 대상이 아니라 규칙 없음
}
# 키워드가 들어 있어도 영양 성분이 아닌 경우 (약물의 염·착염): 후보 문자열이 이 패턴에 맞으면 그 후보는 무시
NEGATIVE_RULES: dict[str, re.Pattern] = {
    "arginine": re.compile(r"ibuprofen|tidiacic|이부프로펜|티디아시"),   # 이부프로펜아르기닌(진통제 염), 아르기닌티디아시케이트(간장약)
    "copper": re.compile(r"chlorophyllin|클로로필린"),
    "niacin": re.compile(r"nicotinate|니코틴산메틸|니코틴산벤질|메틸니코틴|벤질니코틴"),   # 바르는 온열제(니코틴산메틸 등) 제외
    "iodine": re.compile(r"povidone|포비돈|iohexol|iopromide|iodixanol|조영"),
    "potassium": re.compile(r"losartan|clavulan|diclofenac|로사르탄|클라불란|디클로페낙"),                  # 클로로필린구리착염(구취·점막 치료 성분)
}
# 외용제·주사제 등 '먹는 약'이 아닌 제형 — 영양 성분으로 연결하지 않음 (연고의 산화아연 등)
EXTERNAL_RE = re.compile(r"연고|크림|로션|패취|패치|플라스타|카타플라스마|좌제|점안|점비|점이|외용|스프레이|가글|구강용|습포|테이프|밴드|소독|파스|샴푸|비누|세정제|관장|질정|주사|수액|겔(제|$|\(|\d)")
# 제품명에 제형이 드러나지 않는 외용제(복합마이녹실액, 득생만통고 같은 경고제)는 e약은요 용법 문구로 가려낸다
EXTERNAL_USE_RE = re.compile(r"바르|도포|환부|두피|붙입니다|붙이|산포|점안|점비|점이|가글|양치|질 ?내|항문")
ORAL_USE_RE = re.compile(r"복용|섭취|먹|경구|마시|씹|녹여")


def is_external_usage(usage: str) -> bool:
    """용법 문구가 바르는·붙이는 사용만 말하면 True (복용 표현이 하나라도 있으면 내복으로 본다)."""
    u = usage or ""
    return bool(EXTERNAL_USE_RE.search(u)) and not ORAL_USE_RE.search(u)
TOKEN_SPLIT_RE = re.compile(r"[|;,/·+]|\s{2,}")
NAME_SPLIT_RE = re.compile(r"[()\[\]【】,/·+\s]+")

# 주성분 전체(토큰을 합친 문자열)에 아래 패턴이 있으면 해당 성분을 연결하지 않음 — 장 세척제(염화칼륨+폴리에틸렌글리콜)·인공 타액(염화칼슘·염화칼륨+카르복시메틸셀룰로오스)은 영양 보충이 아님
PRODUCT_NEGATIVE_RULES: dict[str, re.Pattern] = {
    "potassium": re.compile(r"폴리에틸렌글리콜|macrogol|polyethylene glycol|카르복시메틸셀룰로오스|카르복시메틸셀룰로스|carboxymethylcellulose|carmellose"),
    "calcium": re.compile(r"카르복시메틸셀룰로오스|카르복시메틸셀룰로스|carboxymethylcellulose|carmellose"),
    "magnesium": re.compile(r"카르복시메틸셀룰로오스|카르복시메틸셀룰로스|carboxymethylcellulose|carmellose"),
}

def ingr_tokens(raw: str) -> list[str]:
    """허가정보 주성분 문자열 → 성분명 토큰 목록. '성분명 : X|분량 : ...' 형식과 'A|B|C' 형식을 모두 처리."""
    raw = (raw or "").strip()
    if not raw:
        return []
    named = re.findall(r"성분명\s*:\s*([^|;]+)", raw)
    parts = named if named else TOKEN_SPLIT_RE.split(raw)
    out: list[str] = []
    for p in parts:
        t = re.sub(r"\s+", " ", p).strip(" .")
        t = re.sub(r"\s*\(.*?\)\s*$", "", t) if len(t) > 12 else t   # 긴 토큰 끝의 괄호 설명 제거
        if t and t not in out and not re.fullmatch(r"[\d.]+", t):
            out.append(t)
    return out[:INGR_TOKENS_MAX]


def kw_hit(k: str, text: str) -> bool:
    """키워드 포함 검사. 숫자로 끝나는 키워드('비타민b1'·'vitamin b1')는 뒤에 숫자가 이어지면('비타민b12') 제외."""
    if k and k[-1].isdigit():
        return re.search(re.escape(k) + r"(?!\d)", text) is not None
    return k in text


def match_ids(name: str, tokens: list[str], valid: set[str], external: bool = False) -> list[str]:
    """제품명·주성분 토큰에서 성분 사전 id 를 찾는다. external=True(용법이 외용)면 연결하지 않는다."""
    if external or EXTERNAL_RE.search(name or ""):
        return []
    cands = [re.sub(r"\s+", " ", t.lower()).strip() for t in tokens] + [t.lower().replace(" ", "") for t in tokens] + [t.lower() for t in NAME_SPLIT_RE.split(name or "") if t]
    alltext = " | ".join(cands)
    found: list[str] = []
    for iid, rx in SALT_RULES.items():
        if iid in valid and any(rx.search(c) for c in cands):
            found.append(iid)
    for iid, kws in CONTAIN_RULES.items():
        if iid not in valid or iid in found:
            continue
        pneg = PRODUCT_NEGATIVE_RULES.get(iid)
        if pneg and pneg.search(alltext):
            continue
        neg = NEGATIVE_RULES.get(iid)
        if any(kw_hit(k, c) and not (neg and neg.search(c)) for c in cands for k in kws):
            found.append(iid)
    found = [i for i in found if not (PRODUCT_NEGATIVE_RULES.get(i) and PRODUCT_NEGATIVE_RULES[i].search(alltext))]
    if "omega-3" in valid and "omega-3" not in found and any(re.search(r"\b(epa|dha)\b", c) for c in cands):
        found.append("omega-3")
    if "multivitamin" in valid and sum(1 for i in found if i in NUTRIENT_IDS) >= MULTIVITAMIN_MIN:
        found.append("multivitamin")
    return found


# ---------------------------------------------------------------- API
class Client:
    def __init__(self, key: str, base: str, budget: int, time_budget: int = DEFAULT_TIME_BUDGET):
        self.key = unquote(key) if "%" in key else key
        self.base = base.rstrip("/")
        self.budget = budget
        self.time_budget = time_budget
        self.started = time.monotonic()
        self.calls = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def get(self, service: str, retries: int = RETRY, **params) -> tuple[list[dict], int]:
        if self.calls >= self.budget:
            raise QuotaExceeded(f"실행당 호출 예산({self.budget}회) 소진")
        if self.elapsed() > self.time_budget:
            raise QuotaExceeded(f"실행당 시간 예산({self.time_budget}초) 초과")
        url = f"{self.base}/{service}"
        q = {"serviceKey": self.key, "type": "json", "numOfRows": PAGE, "pageNo": 1}
        q.update({k: v for k, v in params.items() if v not in (None, "")})
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.calls += 1
                r = requests.get(url, params=q, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), headers={"Accept": "application/json, application/xml;q=0.9, */*;q=0.8"})
                if r.status_code >= 400:
                    body = r.text.lstrip()
                    if body.startswith("<") or body.startswith("{"):
                        try:
                            parse_response(body)            # 오류 본문이 포털 공통 오류(코드 12·30 등)면 코드와 조치를 담아 던진다
                        except PortalError:
                            raise
                        except Exception:  # noqa: BLE001
                            pass
                    snippet = re.sub(r"\s+", " ", r.text)[:240]
                    msg = f"HTTP {r.status_code} {r.reason}: {snippet or '(본문 없음)'}"
                    if r.status_code < 500:
                        raise PortalError(msg)           # 4xx 는 요청 자체가 거부된 것 — 재시도해도 같다
                    raise RuntimeError(msg)
                return parse_response(r.text)
            except PortalError:
                raise
            except Exception as e:  # noqa: BLE001
                last_err = e
                shown = {k: v for k, v in q.items() if k != "serviceKey"}
                log.warning("API 호출 실패 (%d/%d) %s %s: %s", attempt, retries, service, shown, e)
                if attempt < retries:
                    time.sleep(3 * attempt)
        raise RuntimeError(f"API 호출 반복 실패: {last_err}")


def parse_response(text: str) -> tuple[list[dict], int]:
    """공공데이터포털 응답(JSON 또는 XML) → (항목 목록, 전체 건수). 오류 응답은 예외."""
    s = text.lstrip()
    if s.startswith("{"):
        import json
        data = json.loads(s)
        header = data.get("header") or (data.get("response") or {}).get("header") or {}
        body = data.get("body") or (data.get("response") or {}).get("body") or {}
        code = str(header.get("resultCode") or "00")
        if code not in ("00", "0"):
            if code in ("03",):
                return [], 0
            raise_portal(code, header.get("resultMsg"))
        items = body.get("items") or []
        if isinstance(items, dict):
            items = items.get("item") or []
        if isinstance(items, dict):
            items = [items]
        return [i for i in items if isinstance(i, dict)], int(body.get("totalCount") or 0)
    if s.startswith("<"):
        root = ET.fromstring(s)
        if root.tag == "OpenAPI_ServiceResponse":
            raise_portal(root.findtext(".//returnReasonCode") or "", root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg"))
        code = root.findtext("./header/resultCode") or root.findtext(".//resultCode") or "00"
        if code not in ("00", "0"):
            if code == "03":
                return [], 0
            raise_portal(code, root.findtext(".//resultMsg"))
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
        return items, int(root.findtext(".//totalCount") or 0)
    raise RuntimeError(f"알 수 없는 응답 형식: {s[:120]!r}")


def raise_portal(code: str, msg) -> None:
    code = str(code).strip().zfill(2) if str(code).strip().isdigit() else str(code)
    desc = PORTAL_ERRORS.get(code, "")
    msg = str(msg or "").strip()
    text = f"공공데이터포털 오류 {code}: " + (desc if not msg or msg in desc else f"{msg} {desc}".strip())
    if code == "22":
        raise QuotaExceeded(text)
    raise PortalError(text)


def fetch_easy(client: Client, service: str, max_rows: int) -> tuple[list[dict], int]:
    """e약은요 전체 수집 (100건씩)."""
    rows: list[dict] = []
    page, total = 1, None
    while True:
        items, tc = client.get(service, pageNo=page)
        total = tc if total is None else total
        if not items:
            break
        rows.extend(items)
        if page == 1:
            log.info("e약은요 총 %s건 → 수집 시작", f"{total:,}")
        target = (min(total, max_rows) if max_rows else total) if total else (max_rows or float("inf"))   # totalCount 가 없으면 빈 페이지까지
        if len(rows) >= target:
            break
        page += 1
        time.sleep(PAUSE_BETWEEN_CALLS)
    log.info("e약은요 수집 %s건 (API %d회)", f"{len(rows):,}", client.calls)
    return rows, total or len(rows)


def permit_entry(row: dict) -> dict:
    """허가 목록 행 → 캐시 항목 (필드명이 바뀌어도 되도록 여러 후보를 본다)."""
    def pick(*keys):
        for k in keys:
            v = row.get(k)
            if v not in (None, ""):
                return str(v).strip()
        return ""
    cls = pick("PRDUCT_TYPE", "CLASS_NAME", "PRDUCT_TYPE_NAME")
    cls = re.sub(r"^\[\d+\]\s*", "", cls)
    return {
        "ingr": pick("ITEM_INGR_NAME", "MATERIAL_NAME", "MAIN_ITEM_INGR", "INGR_NAME"),
        "otc": pick("SPCLTY_PBLC", "ETC_OTC_NAME", "ETC_OTC_CODE"),
        "cls": cls,
        "date": ymd(pick("ITEM_PERMIT_DATE")),
        "cancel": pick("CANCEL_NAME"),
        "img": pick("BIG_PRDT_IMG_URL"),
        "name": pick("ITEM_NAME"),
    }


def resolve_permit_service(client: Client, preferred: str) -> str | None:
    """허가정보 API 경로를 확인한다: 지정 경로 → 후보 순서로 1회씩 호출해 품목 필드가 오는 첫 경로. 실패 사유는 모두 로그에 남긴다."""
    cands = [c for c in [preferred] + PERMIT_CANDIDATES if c]
    seen: set[str] = set()
    for svc in cands:
        if svc in seen:
            continue
        seen.add(svc)
        try:
            items, total = client.get(svc, retries=1, numOfRows=1)
        except QuotaExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("허가정보 경로 후보 %s → %s", svc, str(e)[:300])
            continue
        if items and any(k in items[0] for k in ("ITEM_SEQ", "ITEM_NAME")):
            log.info("허가정보 경로 확인: %s (전체 %s건, 필드 예: %s)", svc, f"{total:,}", ", ".join(list(items[0].keys())[:14]))
            return svc
        log.warning("허가정보 경로 후보 %s → 품목 필드 없음 (%s)", svc, ", ".join(list(items[0].keys())[:8]) if items else "빈 응답")
    log.warning("허가정보 API 경로를 찾지 못해 주성분 연결을 건너뜁니다. 위 로그의 응답을 보고 저장소 Variables 의 DRUG_PERMIT_SERVICE 를 맞춰 주세요.")
    return None


def fill_permits(client: Client, service: str, cache: dict[str, dict], needed: list[str]) -> None:
    """허가 목록으로 주성분 캐시를 채운다. 많이 비어 있으면 목록 전체 순회, 아니면 품목별 조회."""
    missing = [i for i in needed if i not in cache]
    if not missing:
        return
    need = set(missing)
    log.info("허가정보 캐시에 없는 품목 %s건", f"{len(need):,}")
    service = resolve_permit_service(client, service) or ""
    if not service:
        return
    if len(missing) > BULK_THRESHOLD:
        # 일반의약품만 걸러지는지 확인 (지원하지 않는 필터면 전체를 넘긴다)
        flt: dict = {}
        try:
            _, t_all = client.get(service, numOfRows=1)
            _, t_otc = client.get(service, numOfRows=1, spclty_pblc="일반의약품")
            if 0 < t_otc < t_all:
                flt = {"spclty_pblc": "일반의약품"}
            log.info("허가 목록 전체 %s건%s → 목록 순회로 캐시 채우기", f"{t_all:,}", f" (일반의약품 {t_otc:,}건만)" if flt else "")
        except QuotaExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("허가 목록 건수 확인 실패: %s → 전체 순회", str(e)[:300])
        page, found = 1, 0
        while page <= BULK_MAX_PAGES and need:
            try:
                items, _ = client.get(service, pageNo=page, **flt)
            except QuotaExceeded:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("허가 목록 %d페이지 실패: %s → 목록 순회 중단", page, str(e)[:300])
                break
            if not items:
                break
            for row in items:
                seq = str(row.get("ITEM_SEQ") or row.get("itemSeq") or "").strip()
                if seq in need:
                    cache[seq] = permit_entry(row)
                    need.discard(seq); found += 1
            if page % 25 == 0:
                log.info("허가 목록 %d페이지 … 연결 %s건 / 남음 %s건 (API %d회)", page, f"{found:,}", f"{len(need):,}", client.calls)
            page += 1
            time.sleep(PAUSE_BETWEEN_CALLS)
        log.info("허가 목록 순회 종료: 연결 %s건, 남은 품목 %s건", f"{found:,}", f"{len(need):,}")
    # 남은 품목은 개별 조회 (예산 안에서)
    single, fails = 0, 0
    for seq in list(need):
        if client.calls >= client.budget - 1:
            log.warning("호출 예산 소진 — 남은 %s건은 다음 실행에서 조회합니다.", f"{len(need):,}")
            break
        try:
            items, _ = client.get(service, retries=2, item_seq=seq, numOfRows=5)
        except QuotaExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            fails += 1
            log.warning("허가정보 개별 조회 실패 %s: %s", seq, str(e)[:300])
            if fails >= MAX_CONSECUTIVE_FAILS:
                log.warning("개별 조회가 %d번 연속 실패해 중단합니다. 남은 %s건은 다음 실행에서 다시 시도합니다.", fails, f"{len(need):,}")
                break
            continue
        fails = 0
        hit = next((r for r in items if str(r.get("ITEM_SEQ") or "").strip() == seq), None) or (items[0] if items else None)
        cache[seq] = permit_entry(hit) if hit else {"ingr": "", "otc": "", "cls": "", "date": "", "cancel": "", "img": "", "name": "", "none": True}
        need.discard(seq); single += 1
        time.sleep(PAUSE_BETWEEN_CALLS)
    if single:
        log.info("허가정보 개별 조회 %s건", f"{single:,}")


# ---------------------------------------------------------------- 정규화·저장
def ymd(v: str) -> str:
    v = (v or "").strip()[:10]
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else v


def clean_text(v, limit: int = TEXT_LIMIT) -> str:
    s = html.unescape(str(v or ""))
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t　]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def normalize(row: dict, permit: dict | None, valid: set[str]) -> dict | None:
    seq = str(row.get("itemSeq") or row.get("ITEM_SEQ") or "").strip()
    name = re.sub(r"\s+", " ", str(row.get("itemName") or "")).strip()
    if not seq or not name:
        return None
    permit = permit or {}
    tokens = ingr_tokens(permit.get("ingr", ""))          # 허가정보 주성분 (영문 INN)
    display = [to_korean(t) for t in tokens]
    if len(tokens) == 1 and display[0] == tokens[0]:        # 사전에 없으면 제품명 괄호의 한글 성분명을 쓴다: 우루사정(우르소데옥시콜산)
        m = re.search(r"\(([가-힣][가-힣A-Za-z0-9·\-\s]*)\)\s*$", name)
        if m:
            display = [m.group(1).strip()]
    otc = permit.get("otc", "")
    otc = "일반의약품" if "일반" in otc else "전문의약품" if "전문" in otc else otc
    rec = {
        "id": seq,
        "name": name,
        "company": re.sub(r"\s+", " ", str(row.get("entpName") or "")).strip(),
        "otc": otc,
        "cls": permit.get("cls", ""),
        "ingr": display,
        "ingrEn": tokens if display != tokens else [],
        "ingredients": match_ids(name, tokens, valid, external=is_external_usage(str(row.get("useMethodQesitm") or ""))),
        "efficacy": clean_text(row.get("efcyQesitm")),
        "usage": clean_text(row.get("useMethodQesitm")),
        "warn": clean_text(row.get("atpnWarnQesitm")),
        "caution": clean_text(row.get("atpnQesitm")),
        "interaction": clean_text(row.get("intrcQesitm")),
        "sideEffects": clean_text(row.get("seQesitm")),
        "storage": clean_text(row.get("depositMethodQesitm")),
        "image": str(row.get("itemImage") or permit.get("img") or "").strip(),
        "openDe": ymd(row.get("openDe")),
        "updateDe": ymd(row.get("updateDe")),
        "permitDate": permit.get("date", ""),
        "source": "mfds-drug",
    }
    if permit.get("cancel") and permit["cancel"] != "정상":
        rec["cancel"] = permit["cancel"]
    return rec


def shard_of(did: str) -> str:
    """의약품 id → 조각 파일 번호. assets/js/data.js 의 drugShard() 와 동일해야 합니다."""
    h = 0
    for ch in did:
        h = (h * 31 + ord(ch)) % 1000003
    return f"{h % DETAIL_SHARDS:03d}"


def load_full_records(data_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted((data_dir / DIR_NAME / "detail").glob("*.json")):
        for p in (read_json(f, {}) or {}).get("items", []):
            out.setdefault(p["id"], p)
    return out


def record_to_row(p: dict) -> dict:
    """저장된 레코드 → e약은요 행 형식 (--rebuild 용)."""
    return {"itemSeq": p.get("id"), "itemName": p.get("name"), "entpName": p.get("company"), "efcyQesitm": p.get("efficacy"), "useMethodQesitm": p.get("usage"),
            "atpnWarnQesitm": p.get("warn"), "atpnQesitm": p.get("caution"), "intrcQesitm": p.get("interaction"), "seQesitm": p.get("sideEffects"),
            "depositMethodQesitm": p.get("storage"), "itemImage": p.get("image"), "openDe": p.get("openDe"), "updateDe": p.get("updateDe")}


def write_outputs(data_dir: Path, items: list[dict], meta: dict, valid_ids: list[str]) -> None:
    d = data_dir / DIR_NAME
    (d / "detail").mkdir(parents=True, exist_ok=True)
    used = sorted({i for it in items for i in it["ingredients"]})
    idx = {i: n for n, i in enumerate(used)}
    companies = sorted({it["company"] for it in items if it["company"]})
    cidx = {c: n for n, c in enumerate(companies)}
    bp = load_brand_priority()   # 검색 순위용 브랜드 가중치 (data/brand-priority.json)

    def entry(it: dict) -> list:   # [품목기준코드, 이름, [영양 성분 번호], 주성분 요약, 1=일반·2=전문, 제조사 번호, (브랜드 가중치 1~3 — 0 이면 생략)]
        row = [it["id"], it["name"], [idx[i] for i in it["ingredients"]], " · ".join(it["ingr"][:3])[:40], OTC_FLAG.get(it["otc"], 0), cidx.get(it["company"], -1)]
        w = bp.weight(it["name"], it["company"])
        return row + [w] if w else row

    names = {"_meta": meta, "i": used, "c": companies, "p": [entry(it) for it in items]}
    write_json(d / "names.json", names, compact=True)
    shards: dict[str, list[dict]] = {}
    for it in items:
        shards.setdefault(shard_of(it["id"]), []).append(it)
    for n in range(DETAIL_SHARDS):
        key = f"{n:03d}"
        write_json(d / "detail" / f"{key}.json", {"items": sorted(shards.get(key, []), key=lambda x: x["id"])}, compact=True, quiet=True)
    log.info("저장: 검색 색인 %s건 · 상세 조각 %d개 파일 (영양 성분 연결 %s건)", f"{len(items):,}", DETAIL_SHARDS, f"{sum(1 for it in items if it['ingredients']):,}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="API 호출 없이 기존 파일 유지")
    ap.add_argument("--rebuild", action="store_true", help="API 호출 없이 저장된 레코드로 성분 매칭·파일을 다시 생성")
    args = ap.parse_args()

    names_path = DATA_DIR / DIR_NAME / "names.json"
    existing_meta = (read_json(names_path, {}) or {}).get("_meta", {})
    permit_path = DATA_DIR / DIR_NAME / "permit.json"
    permit_cache: dict[str, dict] = read_json(permit_path, {}) or {}
    permit_cache.pop("_meta", None)
    valid = {it["id"] for it in load_ingredients()}
    full_prev = load_full_records(DATA_DIR)

    client: Client | None = None
    easy_service = env("DRUG_EASY_SERVICE", DEFAULT_EASY_SERVICE)
    permit_service = env("DRUG_PERMIT_SERVICE", DEFAULT_PERMIT_SERVICE)
    if args.rebuild:
        if not full_prev:
            log.warning("재구성할 저장 데이터가 없습니다.")
            return 0
        rows = [record_to_row(p) for p in full_prev.values()]
        total = existing_meta.get("apiTotal") or len(rows)
        log.info("저장된 레코드 %s건으로 재구성 (API 호출 없음)", f"{len(rows):,}")
    else:
        key = env("DATA_GO_KR_KEY")
        if args.sample or not key:
            log.warning("DATA_GO_KR_KEY 가 없어 의약품 수집을 건너뜁니다. 기존 데이터(%s건)를 유지합니다.", f"{len(full_prev):,}")
            return 0
        client = Client(key, env("DRUG_API_BASE", DEFAULT_API_BASE), int(env("DRUG_API_BUDGET", str(DEFAULT_BUDGET)) or DEFAULT_BUDGET),
                        int(env("DRUG_TIME_BUDGET", str(DEFAULT_TIME_BUDGET)) or DEFAULT_TIME_BUDGET))
        rows, total = fetch_easy(client, easy_service, int(env("DRUG_MAX_ROWS", "0") or 0))
        if not rows:
            log.warning("수집된 행이 없어 기존 데이터를 유지합니다.")
            return 0
        ids = [str(r.get("itemSeq") or "").strip() for r in rows]
        try:
            fill_permits(client, permit_service, permit_cache, [i for i in ids if i])
        except QuotaExceeded as e:
            log.warning("%s — 허가정보(주성분) 연결은 다음 실행에서 이어집니다.", e)
        except Exception as e:  # noqa: BLE001
            log.warning("허가정보 연결 실패: %s — 주성분 없이 e약은요 정보만 저장합니다.", e)
        finally:
            if permit_cache:
                write_json(permit_path, {"_meta": {"updatedAt": now_iso(), "total": len(permit_cache)}} | permit_cache, compact=True)

    items: dict[str, dict] = {}
    for row in rows:
        seq = str(row.get("itemSeq") or "").strip()
        permit = permit_cache.get(seq)
        if permit is None and args.rebuild and seq in full_prev:   # 캐시가 없으면 저장된 토큰으로
            prev = full_prev[seq]
            permit = {"ingr": "|".join(prev.get("ingrEn") or prev.get("ingr", [])), "otc": prev.get("otc", ""), "cls": prev.get("cls", ""), "date": prev.get("permitDate", ""), "cancel": prev.get("cancel", ""), "img": prev.get("image", "")}
        rec = normalize(row, permit, valid)
        if rec:
            items[rec["id"]] = rec
    new_items = sorted(items.values(), key=lambda x: x["name"])
    added = sum(1 for i in items if i not in full_prev)
    removed = sum(1 for i in full_prev if i not in items)
    with_permit = sum(1 for i in items if (permit_cache.get(i) or {}).get("ingr"))
    meta = {
        "source": "mfds-drug",
        "sourceLabel": "식품의약품안전처 의약품개요정보(e약은요) · 의약품 제품 허가정보 (공공데이터포털)",
        "updatedAt": now_iso() if not args.rebuild else (existing_meta.get("updatedAt") or now_iso()),
        "rebuiltAt": now_iso() if args.rebuild else None,
        "total": len(new_items),
        "apiTotal": total,
        "withPermit": with_permit,
        "withNutrients": sum(1 for it in new_items if it["ingredients"]),
        "matcherVersion": MATCHER_VERSION,
        "apiCalls": client.calls if client else 0,
        "files": {"names": f"data/{DIR_NAME}/names.json", "detail": f"data/{DIR_NAME}/detail/<shard>.json", "shards": DETAIL_SHARDS, "permit": f"data/{DIR_NAME}/permit.json"},
    }
    write_outputs(DATA_DIR, new_items, meta, sorted(valid))
    log.info("완료: 의약품 %s건 (신규 %d · 삭제 %d · 주성분 연결 %s건 · API 호출 %d회)", f"{len(new_items):,}", added, removed, f"{with_permit:,}", meta["apiCalls"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("의약품 수집 실패: %s — 기존 데이터를 유지합니다.", e)
        if env("CI"):
            print(f"::warning title=의약품 수집 실패::{e} — 기존 data/drugs 유지")
            sys.exit(0)
        sys.exit(1)
