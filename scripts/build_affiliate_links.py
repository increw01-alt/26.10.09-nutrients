#!/usr/bin/env python3
"""
쿠팡 파트너스 Open API 로 검색어별 제휴 딥링크를 생성해 data/deeplinks.json 에 저장합니다.
(프런트엔드 assets/js/affiliate.js 가 이 파일을 읽어 쿠팡 버튼에 적용)

환경변수:
  COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY   필수 (없으면 건너뜀)
  COUPANG_SUB_ID                           선택 (채널 구분)
  COUPANG_MAX_NEW                          선택. 1회 실행당 새로 생성할 최대 링크 수 (기본 100)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, env, load_ingredients, log, now_iso, read_json, write_json  # noqa: E402

DOMAIN = "https://api-gateway.coupang.com"
PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"
BATCH = 20
TIMEOUT = 20


def authorization(method: str, path: str, query: str, access_key: str, secret_key: str) -> str:
    signed_date = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    message = signed_date + method + path + query
    signature = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={signed_date}, signature={signature}"


def make_deeplinks(urls: list[str], ak: str, sk: str, sub_id: str) -> dict[str, str]:
    body: dict = {"coupangUrls": urls}
    if sub_id:
        body["subId"] = sub_id
    headers = {"Authorization": authorization("POST", PATH, "", ak, sk), "Content-Type": "application/json;charset=UTF-8"}
    r = requests.post(DOMAIN + PATH, headers=headers, data=json.dumps(body), timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if str(data.get("rCode")) != "0":
        raise RuntimeError(f"쿠팡 API 오류: {data.get('rMessage')}")
    return {d["originalUrl"]: d["shortenUrl"] for d in data.get("data", []) if d.get("shortenUrl")}


def main() -> int:
    ak, sk = env("COUPANG_ACCESS_KEY"), env("COUPANG_SECRET_KEY")
    out_path = DATA_DIR / "deeplinks.json"
    existing = read_json(out_path, {"_meta": {}, "coupang": {}})
    if not ak or not sk:
        log.warning("COUPANG_ACCESS_KEY/SECRET_KEY 가 없어 딥링크 생성을 건너뜁니다.")
        return 0
    sub_id = env("COUPANG_SUB_ID")
    max_new = int(env("COUPANG_MAX_NEW", "100") or 100)

    queries: list[str] = []
    for it in load_ingredients():
        if it.get("shopQuery"):
            queries.append(it["shopQuery"])
    products = read_json(DATA_DIR / "products.json", {"items": []})
    for p in products.get("items", []):
        if p.get("source") != "sample" and p.get("shopQuery"):
            queries.append(p["shopQuery"])
    queries = list(dict.fromkeys(queries))
    links: dict[str, str] = dict(existing.get("coupang", {}))
    todo = [q for q in queries if q not in links][:max_new]
    log.info("검색어 %d개 중 신규 %d개 딥링크 생성", len(queries), len(todo))

    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        url_map = {f"https://www.coupang.com/np/search?q={quote(q)}": q for q in chunk}
        try:
            result = make_deeplinks(list(url_map.keys()), ak, sk, sub_id)
            for original, short in result.items():
                links[url_map.get(original, original)] = short
            log.info("생성 %d/%d", min(i + BATCH, len(todo)), len(todo))
        except Exception as e:  # noqa: BLE001
            log.warning("딥링크 배치 실패: %s", e)
        time.sleep(1.2)

    write_json(out_path, {"_meta": {"note": existing.get("_meta", {}).get("note", ""), "updatedAt": now_iso(), "total": len(links)}, "coupang": links})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("딥링크 생성 실패: %s", e)
        sys.exit(0)
