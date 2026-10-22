"""홈 가이드 탭(assets/js/pages/home.js 의 GUIDE_GROUPS)과 index.html 정적 카드를 data/guides.json 기준으로 생성.

가이드를 추가하면 SHORT(짧은 제목)와 ORDER(탭별 순서)에 slug 를 넣고 `python scripts/home_tabs.py` 를 실행한 뒤 build_site.py 를 돌린다.
인수 없이 실행하면 저장소 루트를 기준으로 동작한다."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
g = json.loads((ROOT / "data/guides.json").read_text(encoding="utf-8"))
by_slug = {it["slug"]: it for it in g["items"]}

SHORT = {
    "fatigue": "피로회복", "eye-health": "눈 건강", "gut-health": "장 건강", "sleep": "수면", "immunity": "면역력", "joint-health": "관절",
    "stress": "스트레스", "cholesterol": "콜레스테롤", "blood-sugar": "혈당 관리", "skin-health": "피부", "hair-health": "탈모·모발", "diet": "다이어트",
    "eye-twitch": "눈 떨림", "anemia": "빈혈·철분", "gastritis": "위염·역류", "liver-health": "간 건강", "menopause": "갱년기", "blood-circulation": "혈행",
    "acne": "여드름", "exercise": "운동·헬스", "mouth-ulcer": "입병·구내염", "gout": "통풍·요산",
    "20s": "20대", "30s-men": "30대 남자", "40s-women": "40대 여성", "50s-plus": "50대 이상", "seniors-70": "70대 이상", "pregnancy": "임산부·임신 준비",
    "breastfeeding": "수유부", "kids": "어린이", "students": "수험생", "office-workers": "직장인", "shift-workers": "교대 근무", "parents-gift": "부모님 선물",
    "vegan": "채식·비건", "smokers": "흡연자", "hypertension": "혈압약 복용자", "nsaid-users": "관절염 약 복용자", "thyroid": "갑상선 질환자", "kidney": "신장 질환자",
    "diabetes-meds": "당뇨약 복용자", "cancer-treatment": "항암 치료 중", "weight-loss-drugs": "다이어트 약 복용자", "teens": "청소년·성장기",
    "kids-by-age": "어린이 연령별", "postpartum": "산후 회복", "antidepressant-users": "우울·불안 약 복용자", "liver-disease": "간 질환자",
    "osteoporosis-meds": "골다공증 약 복용자", "surgery": "수술 전후",
    "contraceptive-users": "피임약·호르몬 치료", "antibiotics": "항생제 복용 중", "migraine": "편두통", "dental": "치과·구강 건강",
    "dialysis": "투석 환자", "athletes": "운동선수·도핑",
    "numbness": "손발 저림", "dryness": "안구·구강 건조", "prostate": "야간 빈뇨·전립선", "hair-loss-meds": "탈모약 복용자",
    "bariatric": "위 절제·비만수술 후", "pregnancy-symptoms": "입덧·임신 변비",
    "atopy-kids": "소아 아토피·알레르기", "ppi-users": "위산억제제 복용자", "pms": "생리통·PMS", "tinnitus-dizziness": "이명·어지럼",
    "sarcopenia": "노인 근감소증", "memory": "기억력·인지",
    "pcos": "다낭성난소증후군", "gout-meds": "통풍약 복용자", "antihistamine-users": "비염약 복용자", "travel-jetlag": "장거리 여행·시차",
    "when-to-take": "먹는 시간", "how-to-combine": "조합 원칙", "do-not-take-together": "같이 먹으면 안되는 영양제", "empty-stomach": "공복 영양제",
    "daily-limit": "권장량·과다복용", "with-medication": "약과 영양제", "storage-expiry": "유통기한·보관", "multivitamin-guide": "종합비타민 고르기",
    "omega3-guide": "오메가3 고르기", "magnesium-guide": "마그네슘 종류", "vitamin-d-guide": "비타민D 고르기", "zinc-guide": "아연 고르기",
    "calcium-guide": "칼슘 고르기", "vitamin-c-guide": "비타민C 고르기", "collagen-guide": "콜라겐 고르기", "probiotics-guide": "유산균 균주",
}
ORDER = {
    "concerns": ["fatigue", "eye-health", "gut-health", "sleep", "immunity", "joint-health", "stress", "cholesterol", "blood-sugar", "skin-health", "hair-health", "diet", "memory",
                 "eye-twitch", "anemia", "gastritis", "liver-health", "menopause", "blood-circulation", "acne", "exercise", "mouth-ulcer", "gout", "migraine", "dental", "numbness", "dryness", "prostate", "pms", "tinnitus-dizziness", "pcos"],
    "people": ["20s", "30s-men", "40s-women", "50s-plus", "seniors-70", "sarcopenia", "teens", "kids", "kids-by-age", "atopy-kids", "pregnancy", "pregnancy-symptoms", "breastfeeding", "postpartum", "students",
               "office-workers", "shift-workers", "parents-gift", "vegan", "smokers", "hypertension", "diabetes-meds", "nsaid-users", "thyroid", "kidney",
               "liver-disease", "osteoporosis-meds", "antidepressant-users", "contraceptive-users", "hair-loss-meds", "antibiotics", "antihistamine-users", "ppi-users", "gout-meds", "dialysis", "athletes", "weight-loss-drugs", "cancer-treatment", "surgery", "bariatric", "travel-jetlag"],
    "safety": ["when-to-take", "how-to-combine", "do-not-take-together", "empty-stomach", "daily-limit", "with-medication", "storage-expiry", "multivitamin-guide",
               "omega3-guide", "magnesium-guide", "vitamin-d-guide", "zinc-guide", "calcium-guide", "vitamin-c-guide", "collagen-guide", "probiotics-guide"],
}
missing = [s for lst in ORDER.values() for s in lst if s not in by_slug]
assert not missing, f"guides.json 에 없는 slug: {missing}"
uncovered = sorted(set(by_slug) - {s for lst in ORDER.values() for s in lst})
print("탭에 넣지 않은 가이드:", uncovered or "없음")
LABELS = {"concerns": "고민별 가이드", "people": "대상별 가이드", "safety": "복용법·안전 가이드"}


def item_js(slug):
    return '{ slug: "%s", title: "%s", icon: "%s" }' % (slug, SHORT[slug], by_slug[slug]["icon"])


lines = ["  var GUIDE_GROUPS = {   // guides.json 의 모든 가이드. 순서·짧은 제목은 scripts/build_site.py 가 아니라 여기서 관리 (데스크톱 6열 그리드)"]
for key, lst in ORDER.items():
    rows = [", ".join(item_js(s) for s in lst[i:i + 3]) for i in range(0, len(lst), 3)]
    lines.append('    %s: { label: "%s", items: [' % (key, LABELS[key]))
    lines.append(",\n".join("      " + r for r in rows) + " ] }" + ("," if key != "safety" else ""))
lines.append("  };")
js_block = "\n".join(lines)

home = ROOT / "assets/js/pages/home.js"
s = home.read_text(encoding="utf-8")
m = re.search(r"  var GUIDE_GROUPS = \{.*?\n  \};", s, re.S)
assert m, "GUIDE_GROUPS 블록을 찾지 못함"
s = s[: m.start()] + js_block + s[m.end():]
home.write_text(s, encoding="utf-8", newline="")

# index.html 정적 카드 (고민별 탭 초기 표시)
idx = ROOT / "index.html"
h = idx.read_text(encoding="utf-8")
m = re.search(r'(<div class="category-grid[^"]*" id="category-grid"[^>]*>\n)(.*?)(\n\s*</div>\n\s*<div class="category-more")', h, re.S)
assert m, "category-grid 블록을 찾지 못함"
pal = [("#fbf1db", "#b48a3d"), ("#eaf1e3", "#789664"), ("#f8e9e0", "#bc9479"), ("#ececf7", "#9393b3"), ("#e9f1f5", "#7c9dad"), ("#f2ede2", "#a79876")]
tmpl = '<a class="category-card" href="guide/{slug}.html" aria-label="{title} 가이드 읽기"><span class="category-icon" style="--cat-bg:{bg};--cat-color:{fg}"><i data-lucide="{icon}" class="icon"></i></span><h3>{title}</h3><span class="category-subtitle">가이드 살펴보기</span></a>'
indent = re.match(r"\s*", m.group(2)).group(0)
cards = "\n".join(indent + tmpl.format(slug=sl, title=SHORT[sl], bg=pal[i % 6][0], fg=pal[i % 6][1], icon=by_slug[sl]["icon"]) for i, sl in enumerate(ORDER["concerns"]))
h = h[: m.start(2)] + cards + h[m.end(2):]
idx.write_text(h, encoding="utf-8", newline="")
print("home.js 탭:", {k: len(v) for k, v in ORDER.items()}, "| index.html 정적 카드:", len(ORDER["concerns"]))
