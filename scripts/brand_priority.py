"""검색 순위용 브랜드 가중치 — data/brand-priority.json 의 규칙(제조사명 앞부분·제품명 키워드)으로 제품·의약품에 0~3 가중치를 매긴다.

검색 색인(data/products/names.json·names-old.json 의 p[4], data/drugs/names.json 의 p[6])에 가중치를 실어 두면
assets/js/data.js 의 nameMatcher 가 같은 등급의 일치(이름 앞부분·단어 첫머리·중간·제조사) 안에서 가중치가 높은 항목을 먼저 보여준다.
규칙 파일만 고치면 되고, 적용은 `python scripts/build_site.py`(색인 재생성) 로 한다. 식약처 데이터에는 OEM 제조사만 적혀 있어
브랜드가 제품명에만 보이는 경우가 많으므로 제조사명과 제품명 키워드를 함께 본다."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, log, read_json  # noqa: E402

MAX_WEIGHT = 3
RULES_PATH = DATA_DIR / "brand-priority.json"
_NOISE = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한회사|유한책임회사|농업회사법인|\s+")


def norm_company(s) -> str:
    """제조사명 비교용: 「(주)」·「주식회사」·「농업회사법인」·공백을 빼고 소문자로 (예: '(주) 에치와이 논산공장' → '에치와이논산공장')."""
    return _NOISE.sub("", str(s or "")).lower()


def _keyword_regex(words) -> re.Pattern | None:
    """제품명 키워드: 단어 첫머리(문자열 처음, 공백·기호 뒤, 한글↔영문·숫자 경계)에서만 맞춘다 — '삼진' 이 '홍삼진' 에 걸리지 않도록.
    영문·숫자로 끝나는 키워드는 뒤에 영문·숫자가 이어지면 제외('hy' 가 'HYOJO' 에 걸리지 않도록)."""
    parts = []
    for w in words or []:
        w = str(w or "").strip().lower()
        if not w:
            continue
        head = r"(?<![a-z0-9])" if re.match(r"[a-z0-9]", w) else r"(?<![가-힣])"
        tail = r"(?![a-z0-9])" if re.search(r"[a-z0-9]$", w) else ""
        parts.append(head + re.escape(w) + tail)
    return re.compile("|".join(parts)) if parts else None


_PAREN = re.compile(r"\([^()]*\)")


def _name_only(name) -> str:
    """키워드 비교용 이름: 괄호 안(의약품의 성분 표기 '(아토르바스타틴칼슘삼수화물)'·'(수출용)' 등)은 뺀다 — 성분명이 브랜드 키워드에 걸리지 않게."""
    s = str(name or "")
    for _ in range(3):
        s = _PAREN.sub(" ", s)
    return s.lower()


class BrandPriority:
    def __init__(self, rules: list[dict]):
        self.rules: list[tuple[int, tuple[str, ...], re.Pattern | None, str]] = []
        for r in rules or []:
            label = str(r.get("brand") or "")
            w = r.get("weight")
            if not isinstance(w, int) or not 1 <= w <= MAX_WEIGHT:
                raise ValueError(f"brand-priority.json: '{label}' 의 weight 는 1~{MAX_WEIGHT} 정수여야 합니다 (현재 {w!r})")
            comps = tuple(c for c in (norm_company(x) for x in r.get("company", [])) if c)
            kw = _keyword_regex(r.get("keywords", []))
            if not comps and kw is None:
                raise ValueError(f"brand-priority.json: '{label}' 에 company 또는 keywords 가 필요합니다")
            self.rules.append((w, comps, kw, label))
        self.rules.sort(key=lambda t: -t[0])   # 높은 가중치부터 보고 맞으면 바로 끝낸다
        self._company_cache: dict[str, int] = {}

    def _company_weight(self, company: str) -> int:
        c = norm_company(company)
        if c not in self._company_cache:
            self._company_cache[c] = max((w for w, comps, _, _ in self.rules if c and any(c.startswith(x) for x in comps)), default=0)
        return self._company_cache[c]

    def weight(self, name, company) -> int:
        """제품(의약품) 이름 + 제조사명 → 0(해당 없음)~MAX_WEIGHT."""
        best = self._company_weight(company)
        if best >= MAX_WEIGHT:
            return best
        n = _name_only(name)
        for w, _, kw, _ in self.rules:
            if w <= best:
                break
            if kw is not None and kw.search(n):
                best = w
                break
        return best

    def keyword_weight(self, name) -> int:
        """제품(의약품) 이름의 브랜드 키워드만으로 매긴 가중치(제조사명은 보지 않음) — 같은 가중치 안에서 '브랜드명이 이름에 드러난' 제품을 먼저 고를 때 쓴다(약별 가이드의 대표 제품)."""
        n = _name_only(name)
        return max((w for w, _, kw, _ in self.rules if kw is not None and kw.search(n)), default=0)

    def __len__(self) -> int:
        return len(self.rules)


def load_brand_priority(path: Path = RULES_PATH) -> BrandPriority:
    """규칙 파일을 읽어 BrandPriority 를 만든다 (파일이 없으면 가중치 없음). 형식 오류는 예외로 알린다."""
    data = read_json(path, None)
    if not data:
        log.info("브랜드 가중치 규칙 없음 (%s) — 검색 순위에 브랜드 우선 적용 안 함", path.name)
        return BrandPriority([])
    bp = BrandPriority(data.get("brands", []))
    log.info("브랜드 가중치 규칙 %d개 (%s)", len(bp), path.name)
    return bp


if __name__ == "__main__":   # 빠른 확인: python scripts/brand_priority.py "제품명" "제조사"
    bp = load_brand_priority()
    print(bp.weight(sys.argv[1] if len(sys.argv) > 1 else "", sys.argv[2] if len(sys.argv) > 2 else ""))
