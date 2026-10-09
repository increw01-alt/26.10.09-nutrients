#!/usr/bin/env python3
"""
영양제·건강기능식품 관련 뉴스를 수집해 data/news.json 으로 저장합니다.

소스:
  1) 구글 뉴스 RSS (키 불필요)  https://news.google.com/rss/search?q=...
  2) 네이버 뉴스 검색 API (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 설정 시)
     발급: https://developers.naver.com/apps  (검색 API)

사용법:
  python scripts/fetch_news.py
환경변수:
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET  선택
  NEWS_QUERIES   선택. 쉼표로 구분한 검색어 (기본값은 아래 QUERIES)
  NEWS_KEEP      선택. 보관 건수 (기본 60)
"""
from __future__ import annotations

import hashlib
import html
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, KST, env, log, now_iso, read_json, write_json  # noqa: E402

QUERIES = ["건강기능식품", "영양제", "식약처 건강기능식품", "비타민 연구", "오메가3 유산균"]
TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (compatible; SuppleNoteBot/1.0; +https://supplenote.example.com)"}
MFDS_PAT = re.compile(r"식약처|식품의약품안전처|식품안전나라|보건복지부|질병관리청|소비자원|공정거래위원회")
RESEARCH_PAT = re.compile(r"연구|논문|학회|임상|대학|연구팀|저널|메타분석")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def to_iso(dt_str: str) -> str:
    try:
        dt = parsedate_to_datetime(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).replace(microsecond=0).isoformat()
    except Exception:  # noqa: BLE001
        return now_iso()


def categorize(title: str, source: str) -> str:
    t = f"{title} {source}"
    if MFDS_PAT.search(t):
        return "mfds"
    if RESEARCH_PAT.search(t):
        return "research"
    return "news"


def item_id(link: str, title: str) -> str:
    return hashlib.sha1((link or title).encode("utf-8")).hexdigest()[:16]


def fetch_google(query: str) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    r = requests.get(url, timeout=TIMEOUT, headers=UA)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        title = strip_tags(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = strip_tags(src_el.text if src_el is not None else "")
        # 구글 뉴스 제목은 " - 언론사" 꼬리가 붙는 경우가 많아 정리
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        summary = strip_tags(it.findtext("description") or "")
        if summary.startswith(title):
            summary = summary[len(title):].strip(" -·|")
        out.append({
            "id": item_id(link, title), "title": title, "link": link, "source": source or "Google News",
            "publishedAt": to_iso(it.findtext("pubDate") or ""), "summary": summary[:200],
            "category": categorize(title, source), "query": query, "provider": "google",
        })
    return out


def fetch_naver(query: str, cid: str, csec: str) -> list[dict]:
    url = f"https://openapi.naver.com/v1/search/news.json?query={quote(query)}&display=30&sort=date"
    r = requests.get(url, timeout=TIMEOUT, headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec, **UA})
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        title = strip_tags(it.get("title", ""))
        link = it.get("originallink") or it.get("link") or ""
        source = re.sub(r"^https?://(www\.)?", "", link).split("/")[0]
        out.append({
            "id": item_id(link, title), "title": title, "link": link, "source": source,
            "publishedAt": to_iso(it.get("pubDate", "")), "summary": strip_tags(it.get("description", ""))[:200],
            "category": categorize(title, source), "query": query, "provider": "naver",
        })
    return out


def main() -> int:
    out_path = DATA_DIR / "news.json"
    existing = read_json(out_path, {"_meta": {}, "items": []})
    queries = [q.strip() for q in env("NEWS_QUERIES").split(",") if q.strip()] or QUERIES
    keep = int(env("NEWS_KEEP", "60") or 60)
    cid, csec = env("NAVER_CLIENT_ID"), env("NAVER_CLIENT_SECRET")

    collected: list[dict] = []
    errors = 0
    for q in queries:
        try:
            got = fetch_google(q)
            log.info("구글 뉴스 '%s': %d건", q, len(got))
            collected += got
        except Exception as e:  # noqa: BLE001
            errors += 1
            log.warning("구글 뉴스 '%s' 실패: %s", q, e)
        if cid and csec:
            try:
                got = fetch_naver(q, cid, csec)
                log.info("네이버 뉴스 '%s': %d건", q, len(got))
                collected += got
            except Exception as e:  # noqa: BLE001
                errors += 1
                log.warning("네이버 뉴스 '%s' 실패: %s", q, e)

    if not collected:
        log.warning("수집된 뉴스가 없어 기존 파일을 유지합니다.")
        return 0

    # 기존(실데이터)과 병합 후 제목 기준 중복 제거
    prev_items = [i for i in existing.get("items", []) if existing.get("_meta", {}).get("source") != "sample"]
    seen: set[str] = set()
    merged: list[dict] = []
    for it in sorted(collected + prev_items, key=lambda x: x.get("publishedAt", ""), reverse=True):
        key = re.sub(r"[^0-9a-zA-Z가-힣]", "", it["title"]).lower()[:40]
        if not it.get("title") or not it.get("link") or key in seen:
            continue
        seen.add(key)
        merged.append(it)
        if len(merged) >= keep:
            break

    write_json(out_path, {
        "_meta": {
            "source": "live", "sourceLabel": "구글 뉴스 RSS" + (" + 네이버 뉴스 API" if cid and csec else ""),
            "updatedAt": now_iso(), "queries": queries, "errors": errors, "total": len(merged),
        },
        "items": merged,
    })
    log.info("완료: 뉴스 %d건 저장", len(merged))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log.error("뉴스 수집 실패: %s — 기존 데이터를 유지합니다.", e)
        sys.exit(0)
