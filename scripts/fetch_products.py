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
  FOODSAFETY_MAX_ROWS  선택. 최대 수집 행 수 (기본 0 = 전체).
  FOODSAFETY_SERVICE   선택. 서비스 ID (기본 C003).
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

API_BASE = "http://openapi.foodsafetykorea.go.kr/api"
PAGE = 1000
TIMEOUT = 30
RETRY = 3
PER_INGREDIENT_CAP = 400       # 성분별 최대 보관 제품 수 (최신 신고순)
CHANGELOG_KEEP = 200

# 성분별 매칭 키워드 보정 (별칭이 너무 짧거나 오탐이 많은 성분)
MATCH_OVERRIDES: dict[str, list[str]] = {
    "copper": ["구리", "글루콘산구리", "황산구리", "구연산구리"],
    "iron": ["철분", "헴철", "푸마르산철", "황산철", "피로인산철", "구연산철", "비스글리시네이트철", "철(II)"],
    "vitamin-a": ["비타민A", "비타민 A", "레티놀", "레티닐", "베타카로틴", "베타-카로틴"],
    "vitamin-b-complex": ["비타민B1", "비타민B2", "비타민B6", "비타민 B1", "비타민 B2", "비타민 B6", "나이아신", "판토텐산", "티아민", "리보플라빈", "피리독신", "비타민B군", "비타민 B군"],
    "vitamin-b12": ["비타민B12", "비타민 B12", "코발라민", "시아노코발라민", "메틸코발라민"],
    "vitamin-c": ["비타민C", "비타민 C", "아스코르브산", "아스코르빈산"],
    "vitamin-d": ["비타민D", "비타민 D", "콜레칼시페롤", "비타민D3"],
    "vitamin-e": ["비타민E", "비타민 E", "토코페롤"],
    "vitamin-k": ["비타민K", "비타민 K", "메나퀴논", "필로퀴논", "MK-7"],
    "msm": ["MSM", "디메틸설폰", "식이유황", "메틸설포닐메탄"],
    "psyllium": ["차전자피", "질경이씨", "차전자"],
    "arginine": ["아르기닌", "알지닌", "시트룰린"],
    "theanine": ["테아닌"],
    "omega-3": ["EPA", "DHA", "오메가3", "오메가-3", "오메가 3", "피쉬오일", "크릴오일", "알티지"],
    "multivitamin": [],            # 아래 규칙(비타민·미네랄 5종 이상)으로 판단
}
VITAMIN_MINERAL_IDS = {
    "vitamin-a", "vitamin-c", "vitamin-d", "vitamin-e", "vitamin-k", "vitamin-b-complex", "vitamin-b12",
    "folate", "biotin", "calcium", "magnesium", "zinc", "iron", "selenium", "copper",
}


def build_matchers(ingredients: list[dict]) -> list[tuple[str, list[str]]]:
    out = []
    for it in ingredients:
        if it["id"] in MATCH_OVERRIDES:
            kws = MATCH_OVERRIDES[it["id"]]
        else:
            kws = [it["name"].split(" (")[0]] + [a for a in it.get("aliases", []) if len(a) >= 2]
            kws = [k for k in kws if not re.fullmatch(r"[A-Za-z]{1,2}", k)]
        out.append((it["id"], sorted(set(k.lower() for k in kws if k), key=len, reverse=True)))
    return out


def match_ingredients(row: dict, matchers) -> list[str]:
    text = " ".join([row.get("PRDLST_NM", ""), row.get("RAWMTRL_NM", ""), row.get("PRIMARY_FNCLTY", "")]).lower()
    found = [iid for iid, kws in matchers if any(k in text for k in kws)]
    if len(VITAMIN_MINERAL_IDS.intersection(found)) >= 5 and "multivitamin" not in found:
        found.append("multivitamin")
    return found


def api_get(key: str, service: str, start: int, end: int) -> dict:
    url = f"{API_BASE}/{key}/{service}/json/{start}/{end}"
    last_err = None
    for attempt in range(1, RETRY + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            body = data.get(service) or {}
            result = body.get("RESULT", {})
            code = result.get("CODE", "")
            if code and code != "INFO-000":
                if code == "INFO-200":   # 해당하는 데이터가 없습니다
                    return {"row": [], "total_count": body.get("total_count", "0")}
                raise RuntimeError(f"API 오류 {code}: {result.get('MSG')}")
            return body
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("API 호출 실패 (%d/%d) %s: %s", attempt, RETRY, url.replace(key, "***"), e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"API 호출 반복 실패: {last_err}")


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
        "function": (row.get("PRIMARY_FNCLTY") or "").strip(),
        "rawMaterials": (row.get("RAWMTRL_NM") or "").strip(),
        "intake": (row.get("NTK_MTHD") or "").strip(),
        "caution": (row.get("IFTKN_ATNT_MATR_CN") or "").strip(),
        "shape": (row.get("PRDT_SHAP_CD_NM") or "").strip(),
        "shelfLife": (row.get("POG_DAYCNT") or "").strip(),
        "ingredients": ingredient_ids,
        "shopQuery": re.sub(r"\s+", " ", re.sub(r"[\[\]\(\)【】]", " ", name))[:40].strip(),
        "source": "mfds",
    }


def diff_changelog(old_items: list[dict], new_items: list[dict]) -> dict:
    old = {p["id"]: p for p in old_items if p.get("source") != "sample"}
    new = {p["id"]: p for p in new_items}
    entries = []
    for pid, p in new.items():
        if pid not in old:
            entries.append({"type": "added", "name": p["name"], "company": p["company"], "id": pid})
        else:
            o = old[pid]
            for field, label in (("name", "제품명"), ("function", "기능성"), ("rawMaterials", "원재료"), ("caution", "주의사항"), ("intake", "섭취방법"), ("lastUpdated", "식약처 정보 갱신")):
                if (o.get(field) or "") != (p.get(field) or ""):
                    entries.append({"type": "changed", "name": p["name"], "company": p["company"], "id": pid, "field": label})
                    break
    for pid, o in old.items():
        if pid not in new:
            entries.append({"type": "removed", "name": o["name"], "company": o.get("company", ""), "id": pid})
    counts = {t: sum(1 for e in entries if e["type"] == t) for t in ("added", "removed", "changed")}
    return {"updatedAt": now_iso(), "added": counts["added"], "removed": counts["removed"], "changed": counts["changed"], "items": entries[:CHANGELOG_KEEP]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="API 호출 없이 기존 파일 유지")
    args = ap.parse_args()

    out_path = DATA_DIR / "products.json"
    existing = read_json(out_path, {"_meta": {}, "changelog": {}, "items": []})
    key = env("FOODSAFETY_API_KEY")
    if args.sample or not key:
        log.warning("FOODSAFETY_API_KEY 가 없어 제품 수집을 건너뜁니다. 기존 데이터(%s)를 유지합니다.", existing.get("_meta", {}).get("source", "?"))
        return 0

    service = env("FOODSAFETY_SERVICE", "C003")
    max_rows = int(env("FOODSAFETY_MAX_ROWS", "0") or 0)
    ingredients = load_ingredients()
    matchers = build_matchers(ingredients)

    first = api_get(key, service, 1, PAGE)
    total = int(first.get("total_count") or 0)
    log.info("총 %s건 (서비스 %s)", f"{total:,}", service)
    rows = list(first.get("row") or [])
    start = PAGE + 1
    limit = min(total, max_rows) if max_rows else total
    while start <= limit:
        end = min(start + PAGE - 1, limit)
        body = api_get(key, service, start, end)
        chunk = body.get("row") or []
        if not chunk:
            break
        rows.extend(chunk)
        log.info("수집 %s / %s", f"{len(rows):,}", f"{limit:,}")
        start = end + 1
        time.sleep(0.3)

    items: dict[str, dict] = {}
    for row in rows:
        ids = match_ingredients(row, matchers)
        if not ids:
            continue
        p = normalize(row, ids)
        if not p["name"]:
            continue
        items[p["id"]] = p

    # 성분별 상한 적용 (최신 신고순)
    per: dict[str, int] = {}
    kept: dict[str, dict] = {}
    for p in sorted(items.values(), key=lambda x: x["registeredAt"], reverse=True):
        keep = False
        for iid in p["ingredients"]:
            if per.get(iid, 0) < PER_INGREDIENT_CAP:
                keep = True
        if keep:
            kept[p["id"]] = p
            for iid in p["ingredients"]:
                per[iid] = per.get(iid, 0) + 1

    new_items = sorted(kept.values(), key=lambda x: x["registeredAt"], reverse=True)
    changelog = diff_changelog(existing.get("items", []), new_items)
    added_ids = {e["id"] for e in changelog["items"] if e["type"] == "added"}
    was_sample = existing.get("_meta", {}).get("source") == "sample"
    for p in new_items:
        if p["id"] in added_ids and not was_sample:
            p["isNew"] = True

    out = {
        "_meta": {
            "source": "mfds",
            "sourceLabel": "식품의약품안전처 식품안전나라 건강기능식품 품목제조신고",
            "service": service,
            "updatedAt": now_iso(),
            "total": len(new_items),
            "scanned": len(rows),
            "fields": existing.get("_meta", {}).get("fields", {}),
        },
        "changelog": changelog if not was_sample else {"updatedAt": now_iso(), "added": 0, "removed": 0, "changed": 0, "items": []},
        "items": new_items,
    }
    write_json(out_path, out)
    log.info("완료: 제품 %s건 (신규 %d · 변경 %d · 삭제 %d)", f"{len(new_items):,}", changelog["added"], changelog["changed"], changelog["removed"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("제품 수집 실패: %s — 기존 데이터를 유지합니다.", e)
        sys.exit(0 if env("CI") else 1)
