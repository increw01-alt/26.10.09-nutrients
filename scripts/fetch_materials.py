#!/usr/bin/env python3
"""
식품안전나라(식약처) 건강기능식품 기능성 원료 데이터를 수집해 성분 사전을 보강합니다.

  - I-0040  건강기능식품 기능성 원료인정현황 (인정번호·인정일자·업체명·신청원료명·기능성 내용·1일 섭취량·섭취시 주의사항)
  - I-0050  건강기능식품 개별인정형 정보

결과:
  data/materials.json              전체 원료 목록 (원료명+기능성 기준으로 묶음, 압축 JSON)
  data/materials/<성분id>.json      성분별 관련 원료 (성분 상세 페이지)

사용법:
  FOODSAFETY_API_KEY=발급키 python scripts/fetch_materials.py
환경변수:
  FOODSAFETY_API_KEY        필수. 없으면 기존 파일 유지.
  FOODSAFETY_MATERIAL_SVCS  선택. 쉼표 구분 서비스 ID (기본 I-0040,I-0050)

API 응답의 영문 필드명이 서비스마다 달라서, 알려진 후보 이름 → 키워드 포함 여부 순으로 자동 매핑하고
매핑되지 않은 필드는 extra 에 보존합니다. CI 로그에 첫 행의 필드명을 출력하니 필요하면 후보를 보강하세요.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, env, load_ingredients, log, now_iso, read_json, write_json  # noqa: E402
import fetch_products as fp  # noqa: E402  (api_get · 매칭 규칙 재사용)

DEFAULT_SERVICES = ["I-0040", "I-0050"]
SERVICE_LABEL = {"I-0040": "기능성 원료인정현황", "I-0050": "개별인정형 정보"}
PAGE = 1000
MAX_ROWS = 20000

# 개념별 후보 필드명 (앞에서부터 우선) 과 키워드 (후보가 없을 때 키 이름에 포함되면 채택)
FIELD_MAP = {
    "name":          (["APLC_RAWMTRL_NM", "RAWMTRL_NM", "FNCLTY_MTRAL_NM", "MTRAL_NM", "PRDLST_NM", "RAW_MTRAL_NM"], ["RAWMTRL", "MTRAL", "MATRL"]),
    "function":      (["FNCLTY_CN", "FNCLTY_CNTNT", "PRIMARY_FNCLTY", "FNCLTY", "FUNCTN_CN"], ["FNCLTY", "FUNCT"]),
    "intakeLow":     (["DAY_INTK_LOWLIMIT", "DAY_INTK_LOW", "INTK_LOWLIMIT"], ["LOWLIMIT", "LOW_LIMIT"]),
    "intakeHigh":    (["DAY_INTK_HIGHLIMIT", "DAY_INTK_HIGH", "INTK_HIGHLIMIT"], ["HIGHLIMIT", "HIGH_LIMIT"]),
    "intake":        (["DAY_INTK_CN", "DAY_INTK", "INTK_CN", "NTK_MTHD"], ["INTK_CN", "DAY_INTK"]),
    "caution":       (["IFTKN_ATNT_MATR_CN", "ATNT_MATR_CN", "INTK_ATNT_MATR"], ["ATNT"]),
    "recognitionNo": (["HF_FNCLTY_MTRAL_RCOGN_NO", "RCOGN_NO", "RECOG_NO", "APRVL_NO", "PRMS_NO"], ["RCOGN_NO", "RECOG_NO", "APRVL_NO"]),
    "recognizedAt":  (["RCOGN_DT", "RECOG_DT", "APRVL_DT", "PRMS_DT", "CRET_DTM"], ["RCOGN_DT", "RECOG_DT", "APRVL_DT"]),
    "company":       (["BSSH_NM", "ENTRPS_NM", "CMPNY_NM", "APLCNT_NM"], ["BSSH", "ENTRPS", "CMPNY"]),
    "materialType":  (["RAWMTRL_DVS_NM", "MTRAL_DVS_NM", "FNCLTY_DVS_NM", "DVS_NM"], ["DVS_NM"]),
}
INTAKE_UNIT_KEYS = ["DAY_INTK_UNIT", "INTK_UNIT", "UNIT"]


RECOG_RE = re.compile(r"(new)?\s*제?\s*(\d{4})\s*-\s*(\d+)\s*호?", re.I)
NAME_SUFFIX_RE = re.compile(r"\(?\s*(기능성\s*원료\s*인정)?\s*(new)?\s*제?\s*\d{4}\s*-\s*\d+\s*호?\s*\)?", re.I)
NUMLIKE_RE = re.compile(r"\s*(new)?\s*제?\s*\d{4}\s*-\s*\d+\s*호?\s*", re.I)

# 원료 데이터는 '원료명' 기준으로만 성분에 연결합니다 (같은 기능성 문구를 가진 다른 원료가 섞이지 않도록)
MATERIAL_NAME_KWS: dict[str, list[str]] = {
    "probiotics": ["프로바이오틱스", "유산균", "락토바실러스", "비피도박테리움", "비피더스", "락토코커스", "스트렙토코커스", "바실러스", "사카로마이세스", "엔테로코커스", "페디오코커스", "류코노스톡", "바이셀라",
                   "lactobacillus", "bifidobacterium", "lactococcus", "streptococcus", "bacillus", "saccharomyces", "enterococcus", "pediococcus", "leuconostoc", "weissella", "probiotic"],
    "milk-thistle": ["밀크씨슬", "밀크시슬", "실리마린", "카르두스", "milk thistle", "silymarin"],
    "red-ginseng": ["홍삼"],
    "theanine": ["테아닌", "theanine"],
    "saw-palmetto": ["쏘팔메토", "소팔메토", "saw palmetto"],
    "phosphatidylserine": ["포스파티딜세린", "phosphatidylserine", "leci-ps"],
    "coq10": ["코엔자임q10", "코엔자임 q10", "코큐텐", "유비퀴놀", "유비퀴논", "coq10", "coenzyme q10", "ubiquinol"],
    "garcinia": ["가르시니아", "garcinia"],
    "lutein": ["루테인", "지아잔틴", "마리골드", "lutein", "zeaxanthin"],
    "omega-3": ["오메가3", "오메가-3", "오메가 3", "epa", "dha", "피쉬오일", "크릴오일", "정제어유", "오징어유", "omega-3", "krill"],
    "collagen": ["콜라겐", "collagen"],
    "curcumin": ["커큐민", "강황", "울금", "터메릭", "테라큐민", "curcumin", "turmeric"],
    "green-tea-extract": ["녹차", "카테킨", "egcg", "green tea"],
    "boswellia": ["보스웰리아", "boswellia"],
    "glucosamine": ["글루코사민", "glucosamine"],
    "msm": ["msm", "디메틸설폰", "식이유황", "메틸설포닐메탄", "dimethylsulfone"],
    "arginine": ["아르기닌", "시트룰린", "arginine", "citrulline"],
    "ginkgo": ["은행잎", "징코", "ginkgo"],
    "psyllium": ["차전자피", "차전자", "질경이씨", "psyllium"],
    "l-carnitine": ["카르니틴", "carnitine"],
    "propolis": ["프로폴리스", "propolis"],
}


def recog_key(no: str, name: str) -> str:
    """인정번호를 '2023-40' / 'new-2007-13' 형태로 정규화 (New 시리즈는 별도 번호 체계)."""
    m = RECOG_RE.search(no or "") or RECOG_RE.search(name or "")
    if not m:
        return ""
    return ("new-" if m.group(1) else "") + f"{m.group(2)}-{int(m.group(3))}"


def clean_name(s: str) -> str:
    s = NAME_SUFFIX_RE.sub("", s or "")
    s = re.sub(r"\(\s*\)", "", s)
    return re.sub(r"\s+", " ", s).strip(" ,·-")


def clean_function(s: str) -> str:
    s = (s or "").replace("\r", "\n")
    if NUMLIKE_RE.fullmatch(s):          # 기능성 칸에 인정번호만 들어 있는 행 (최근 I-0040 데이터)
        return ""
    s = re.split(r"\(\s*영문\s*\)", s)[0]
    s = re.sub(r"\(\s*국문\s*\)", "", s)
    s = re.sub(r"[“”\"◆■●▶]", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip(" \n")


def tidy_intake(s: str) -> str:
    s = (s or "").strip()
    if s in (".", "-"):
        return ""
    m = re.fullmatch(r"([\d.,]+)\s*\(([^)]+)\)\s*~\s*([\d.,]+)\s*\(([^)]+)\)", s)
    if m and m.group(2) == m.group(4):
        return f"{m.group(1)}~{m.group(3)} {m.group(2)}"
    m = re.fullmatch(r"([\d.,]+)\s*\(([^)]+)\)", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return re.sub(r"\s+", " ", s)


def pick(row: dict, concept: str, used: set) -> str:
    cands, needles = FIELD_MAP[concept]
    for k in cands:
        if k in row and str(row[k]).strip():
            used.add(k)
            return str(row[k]).strip()
    for k in row:
        if k in used:
            continue
        ku = k.upper()
        if any(n in ku for n in needles) and str(row[k]).strip():
            used.add(k)
            return str(row[k]).strip()
    return ""


def ymd(v: str) -> str:
    v = re.sub(r"[^0-9]", "", v or "")
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if len(v) >= 8 else (v[:4] if len(v) >= 4 else "")


def normalize(service: str, row: dict) -> dict:
    used: set = set()
    rec = {c: pick(row, c, used) for c in FIELD_MAP}
    unit = next((str(row[k]).strip() for k in INTAKE_UNIT_KEYS if k in row and str(row[k]).strip()), "")
    if unit:
        used.update(k for k in INTAKE_UNIT_KEYS if k in row)
    low, high = rec.pop("intakeLow"), rec.pop("intakeHigh")
    if low or high:
        rec["intake"] = (f"{low}~{high}" if low and high and low != high else (low or high)) + (f" {unit}" if unit else "")
    rec["recognizedAt"] = ymd(rec["recognizedAt"])
    rec["service"] = service
    rec["type"] = "고시형" if "고시" in (rec["materialType"] + rec["name"]) else "개별인정형"
    rec["recogKey"] = recog_key(rec["recognitionNo"], rec["name"])
    rec["name"] = clean_name(rec["name"])
    rec["function"] = clean_function(rec["function"])
    rec["intake"] = tidy_intake(rec["intake"])
    rec["caution"] = re.sub(r"[ \t]+", " ", rec["caution"].replace("\r", "\n")).strip()
    rec["extra"] = {k: str(v).strip()[:200] for k, v in row.items() if k not in used and str(v).strip() and k not in ("RESULT",)}
    return rec


def fetch_all(key: str, service: str) -> list[dict]:
    first = fp.api_get(key, service, 1, PAGE)
    total = int(first.get("total_count") or 0)
    rows = list(first.get("row") or [])
    log.info("%s(%s): 총 %s건", service, SERVICE_LABEL.get(service, ""), f"{total:,}")
    if rows:
        log.info("%s 필드명: %s", service, ", ".join(rows[0].keys()))
    start = PAGE + 1
    while start <= min(total, MAX_ROWS):
        end = min(start + PAGE - 1, total)
        body = fp.api_get(key, service, start, end)
        chunk = body.get("row") or []
        if not chunk:
            break
        rows.extend(chunk)
        log.info("%s 수집 %s / %s", service, f"{len(rows):,}", f"{total:,}")
        start = end + 1
        time.sleep(fp.PAUSE_BETWEEN_CALLS)
    return rows


def match_ids(rec: dict, matchers) -> list[str]:
    nut, herb = matchers
    name = rec["name"].lower()
    found = []
    for iid, (names, _claims, _shared, _ok) in nut.items():
        if any(k in name for k in names):
            found.append(iid)
    for iid, (kws, _claims) in herb.items():
        kws = MATERIAL_NAME_KWS.get(iid, kws)
        if any(k in name for k in kws):
            found.append(iid)
    return found


def norm_key(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


SERVICE_PRIORITY = {"I-0050": 0, "I-0040": 1}   # 기능성·섭취량·주의사항은 구조화된 I-0050 값을 우선


def group_records(recs: list[dict]) -> list[dict]:
    """같은 인정번호(없으면 원료명+기능성)는 하나로 합치고 두 서비스의 빈칸을 서로 채웁니다."""
    groups: dict[str, dict] = {}
    order = sorted(recs, key=lambda r: SERVICE_PRIORITY.get(r["service"], 9))
    for r in order:
        key = r["recogKey"] or (norm_key(r["name"]) + "|" + norm_key(r["function"])[:80])
        g = groups.get(key)
        if not g:
            g = groups[key] = {"name": "", "type": r["type"], "function": "", "intake": "", "caution": "", "recognitionNo": "",
                               "recognizedAt": "", "companies": [], "services": [], "ingredients": [], "count": 0, "extra": {}}
        g["count"] += 1
        # 원료명은 I-0040(신청원료명)을 우선, 없으면 아무거나
        if r["name"] and (not g["name"] or (r["service"] == "I-0040" and len(r["name"]) <= len(g["name"]))):
            g["name"] = r["name"]
        for f in ("function", "intake", "caution"):
            if r[f] and (not g[f] or len(r[f]) > len(g[f]) * 2):
                g[f] = r[f]
        if r["recognitionNo"] and (not g["recognitionNo"] or len(r["recognitionNo"]) < len(g["recognitionNo"])):
            g["recognitionNo"] = r["recognitionNo"]
        if r["recognizedAt"] and (not g["recognizedAt"] or r["recognizedAt"] < g["recognizedAt"]):
            g["recognizedAt"] = r["recognizedAt"]
        if r["company"] and r["company"] not in g["companies"]:
            g["companies"].append(r["company"])
        if r["service"] not in g["services"]:
            g["services"].append(r["service"])
        for iid in r["ingredients"]:
            if iid not in g["ingredients"]:
                g["ingredients"].append(iid)
        for k, v in r["extra"].items():
            g["extra"].setdefault(k, v)
    out = []
    for key, g in groups.items():
        g["companyCount"] = len(g["companies"])
        g["companies"] = g["companies"][:6]
        g["id"] = (key if RECOG_RE.search(key) else norm_key(g["name"])[:40] + "-" + str(abs(hash(g["function"])) % 100000))
        g["recognitionNo"] = re.sub(r"\s+", "", g["recognitionNo"])
        out.append(g)
    out.sort(key=lambda g: (g["recognizedAt"] or "0000", g["name"]), reverse=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    out_path = DATA_DIR / "materials.json"
    existing = read_json(out_path, {"_meta": {}, "items": []})
    key = env("FOODSAFETY_API_KEY")
    if args.sample or not key:
        log.warning("FOODSAFETY_API_KEY 가 없어 기능성 원료 수집을 건너뜁니다. 기존 데이터(%s)를 유지합니다.", existing.get("_meta", {}).get("source", "?"))
        return 0
    services = [s.strip() for s in env("FOODSAFETY_MATERIAL_SVCS", ",".join(DEFAULT_SERVICES)).split(",") if s.strip()]
    matchers = fp.build_matchers(load_ingredients())

    recs: list[dict] = []
    totals: dict[str, int] = {}
    for svc in services:
        try:
            rows = fetch_all(key, svc)
        except Exception as e:  # noqa: BLE001
            log.warning("%s 수집 실패: %s", svc, e)
            continue
        totals[svc] = len(rows)
        for row in rows:
            rec = normalize(svc, row)
            if not rec["name"]:
                continue
            rec["ingredients"] = match_ids(rec, matchers)
            recs.append(rec)
        time.sleep(fp.PAUSE_BETWEEN_CALLS)
    if not recs:
        log.warning("수집된 원료 데이터가 없어 기존 파일을 유지합니다.")
        return 0

    grouped = group_records(recs)
    matched = [g for g in grouped if g["ingredients"]]
    meta = {
        "source": "mfds",
        "sourceLabel": "식품의약품안전처 식품안전나라 건강기능식품 기능성 원료 정보",
        "services": {s: {"label": SERVICE_LABEL.get(s, s), "rows": totals.get(s, 0)} for s in services},
        "updatedAt": now_iso(),
        "total": len(grouped),
        "matched": len(matched),
    }
    write_json(out_path, {"_meta": meta, "items": grouped}, compact=True)

    mdir = DATA_DIR / "materials"
    mdir.mkdir(exist_ok=True)
    by_ing: dict[str, list[dict]] = {}
    for g in matched:
        for iid in g["ingredients"]:
            by_ing.setdefault(iid, []).append(g)
    wanted = set()
    for iid, lst in by_ing.items():
        # 성분 페이지에서는 기능성 내용이 채워진 원료를 먼저, 그다음 최근 인정순
        lst = sorted(lst, key=lambda g: (0 if g["function"] else 1, -(int((g["recognizedAt"] or "0000-00-00").replace("-", "") or 0))))
        write_json(mdir / f"{iid}.json", {"_meta": {"ingredient": iid, "updatedAt": meta["updatedAt"], "total": len(lst)}, "items": lst}, compact=True, quiet=True)
        wanted.add(f"{iid}.json")
    for stale in mdir.glob("*.json"):
        if stale.name not in wanted:
            stale.unlink()
    log.info("완료: 원료 %s건(원본 %s행) · 성분 매칭 %s건 · 성분별 파일 %d개", f"{len(grouped):,}", f"{len(recs):,}", f"{len(matched):,}", len(wanted))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("기능성 원료 수집 실패: %s — 기존 데이터를 유지합니다.", e)
        if env("CI"):
            print(f"::warning title=기능성 원료 수집 실패::{e}")
            sys.exit(0)
        sys.exit(1)
