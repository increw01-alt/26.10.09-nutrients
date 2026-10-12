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
    rec["function"] = re.sub(r"[ \t]+", " ", rec["function"]).strip()
    rec["caution"] = re.sub(r"[ \t]+", " ", rec["caution"]).strip()
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
    func = rec["function"].lower()
    found = []
    for iid, (names, _claims, _shared, _ok) in nut.items():
        if any(k in name for k in names):
            found.append(iid)
    for iid, (kws, claims) in herb.items():
        if any(k in name for k in kws) or any(c in func for c in claims):
            found.append(iid)
    return found


def norm_key(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def group_records(recs: list[dict]) -> list[dict]:
    """같은 원료명+기능성 내용은 하나로 묶고 업체·인정번호를 모읍니다."""
    groups: dict[str, dict] = {}
    for r in recs:
        key = norm_key(r["name"]) + "|" + norm_key(r["function"])[:80]
        g = groups.get(key)
        if not g:
            g = groups[key] = {
                "name": r["name"], "type": r["type"], "function": r["function"], "intake": r["intake"], "caution": r["caution"],
                "recognitionNo": r["recognitionNo"], "recognizedAt": r["recognizedAt"], "companies": [], "services": [], "ingredients": r["ingredients"], "count": 0,
                "extra": r["extra"],
            }
        g["count"] += 1
        if r["company"] and r["company"] not in g["companies"]:
            g["companies"].append(r["company"])
        if r["service"] not in g["services"]:
            g["services"].append(r["service"])
        if r["recognizedAt"] and (not g["recognizedAt"] or r["recognizedAt"] < g["recognizedAt"]):
            g["recognizedAt"] = r["recognizedAt"]
            g["recognitionNo"] = r["recognitionNo"] or g["recognitionNo"]
        for f in ("intake", "caution", "function"):
            if not g[f] and r[f]:
                g[f] = r[f]
        for iid in r["ingredients"]:
            if iid not in g["ingredients"]:
                g["ingredients"].append(iid)
    out = []
    for g in groups.values():
        g["companyCount"] = len(g["companies"])
        g["companies"] = g["companies"][:6]
        g["id"] = re.sub(r"[^0-9a-z가-힣]", "", g["name"].lower())[:40] + "-" + (g["recognitionNo"] or str(abs(hash(g["function"])) % 100000)).replace("/", "-")
        out.append(g)
    out.sort(key=lambda g: (g["recognizedAt"] or "9999"), reverse=True)
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
