"""의약품 허가정보의 영문 주성분명(INN) → 한글 표시명.

공공데이터포털 '의약품 제품 허가정보' 목록의 ITEM_INGR_NAME 은 영문으로 온다(예: Ursodeoxycholic Acid).
사이트에는 한글로 보여주기 위해 자주 쓰이는 성분·염·제형 표현을 번역한다. 사전에 없는 이름은 영문 그대로 둔다.
사용: from drug_ingr_ko import to_korean
"""
from __future__ import annotations

import re

# 기본 성분명 (소문자, 염·제형 수식어 제거 후)
KO: dict[str, str] = {
    # 해열·진통·소염
    "acetaminophen": "아세트아미노펜", "ibuprofen": "이부프로펜", "dexibuprofen": "덱시부프로펜", "naproxen": "나프록센", "aspirin": "아스피린",
    "loxoprofen": "록소프로펜", "ketoprofen": "케토프로펜", "flurbiprofen": "플루르비프로펜", "diclofenac": "디클로페낙", "piroxicam": "피록시캄",
    "felbinac": "펠비낙", "indometacin": "인도메타신", "indomethacin": "인도메타신", "ethenzamide": "에텐자미드", "clonixin lysinate": "클로닉신리시네이트",
    "ibuprofen piconol": "이부프로펜피코놀", "aceclofenac": "아세클로페낙", "mefenamic acid": "메페남산", "tramadol": "트라마돌",
    "glycol salicylate": "살리실산글리콜", "methyl salicylate": "살리실산메틸", "salicylic acid": "살리실산", "benzyl nicotinate": "니코틴산벤질",
    "caffeine": "카페인", "anhydrous caffeine": "카페인무수물", "pamabrom": "파마브롬", "chlorzoxazone": "클로르족사존", "aminocaproic acid": "아미노카프로산",
    # 감기·알레르기·기침
    "chlorpheniramine": "클로르페니라민", "cetirizine": "세티리진", "loratadine": "로라타딘", "fexofenadine": "펙소페나딘", "triprolidine": "트리프롤리딘",
    "diphenhydramine": "디펜히드라민", "dimenhydrinate": "디멘히드리네이트", "doxylamine": "독실아민", "carbinoxamine": "카르비녹사민", "brompheniramine": "브롬페니라민",
    "ketotifen": "케토티펜", "meclizine": "메클리진", "scopolamine": "스코폴라민", "dextromethorphan": "덱스트로메토르판", "guaifenesin": "구아이페네신",
    "dl-methylephedrine": "dl-메틸에페드린", "methylephedrine": "메틸에페드린", "pseudoephedrine": "슈도에페드린", "ephedrine": "에페드린", "phenylephrine": "페닐에프린",
    "noscapine": "노스카핀", "tipepidine": "티페피딘", "pentoxyverine": "펜톡시베린", "cloperastine": "클로페라스틴", "trimetoquinol": "트리메토퀴놀",
    "acetylcysteine": "아세틸시스테인", "erdosteine": "에르도스테인", "ambroxol": "암브록솔", "bromhexine": "브롬헥신", "carbocisteine": "카르보시스테인",
    "potassium guaiacolsulfonate": "구아야콜설폰산칼륨", "lysozyme": "리소짐", "oxymetazoline": "옥시메타졸린", "xylometazoline": "자일로메타졸린",
    "naphazoline": "나파졸린", "tetrahydrozoline": "테트라히드로졸린", "benzydamine": "벤지다민", "cetylpyridinium": "세틸피리디늄",
    "belladonna total alkaloid": "벨라돈나총알칼로이드", "dicyclomine": "디시클로민", "papaverine": "파파베린",
    # 소화기
    "ursodeoxycholic acid": "우르소데옥시콜산", "famotidine": "파모티딘", "ranitidine": "라니티딘", "cimetidine": "시메티딘", "omeprazole": "오메프라졸",
    "esomeprazole": "에스오메프라졸", "pantoprazole": "판토프라졸", "almagate": "알마게이트", "hydrotalcite": "히드로탈시트", "magnesium hydroxide": "수산화마그네슘",
    "aluminium hydroxide": "수산화알루미늄", "aluminium hydroxide gel": "수산화알루미늄겔", "aluminium phosphate gel": "인산알루미늄겔", "colloidal aluminium phosphate": "콜로이드인산알루미늄",
    "sodium bicarbonate": "탄산수소나트륨", "simethicone": "시메티콘", "dimethicone": "디메티콘", "trimebutine": "트리메부틴", "bisacodyl": "비사코딜",
    "docusate": "도큐세이트", "sennoside": "센노시드", "senna leaf": "센나엽", "loperamide": "로페라미드", "dioctahedral smectite": "디옥타헤드랄스멕타이트",
    "pancreatin": "판크레아틴", "bromelain": "브로멜라인", "lipase": "리파제", "cellulase": "셀룰라제", "diastase·protease·cellulase": "디아스타제·프로테아제·셀룰라제",
    "ox bile extract": "우담즙엑스", "betaine": "베타인", "oxethazaine": "옥세타자인", "magnesium aluminometasilicate": "메타규산알루민산마그네슘",
    "magnesium aluminosilicate": "규산알루민산마그네슘", "synthetic aluminium silicate": "합성규산알루미늄", "bismuth subnitrate": "차질산비스무트",
    "lactulose": "락툴로오스", "scopolia extract": "스코폴리아엑스", "glycyrrhizic acid": "글리시리진산", "dipotassium glycyrrhizinate": "글리시리진산이칼륨",
    "glycyrrhiza": "감초", "glycyrrhiza extract": "감초엑스", "licorice": "감초", "enoxolone": "에녹솔론", "gentian": "겐티아나",
    # 비타민·미네랄·영양
    "thiamine": "티아민", "fursultiamine": "푸르설티아민", "benfotiamine": "벤포티아민", "bisbentiamine": "비스벤티아민", "octotiamine": "옥토티아민",
    "riboflavin": "리보플라빈", "pyridoxine": "피리독신", "pyridoxal": "피리독살", "nicotinamide": "니코틴산아미드", "nicotinic acid": "니코틴산",
    "calcium pantothenate": "판토텐산칼슘", "pantothenic acid": "판토텐산", "dexpanthenol": "덱스판테놀", "panthenol": "판테놀",
    "cyanocobalamin": "시아노코발라민", "mecobalamin": "메코발라민", "hydroxocobalamin": "히드록소코발라민", "folic acid": "엽산", "biotin": "비오틴", "d-biotin": "D-비오틴",
    "ascorbic acid": "아스코르브산", "sodium ascorbate": "아스코르브산나트륨", "calcium ascorbate": "아스코르브산칼슘", "ascorbic acid d.c": "아스코르브산",
    "tocopherol": "토코페롤", "tocopherol acetate": "토코페롤아세테이트", "tocopherol calcium succinate": "토코페롤숙신산칼슘", "cholecalciferol": "콜레칼시페롤",
    "cholecalciferol oil": "콜레칼시페롤유", "ergocalciferol": "에르고칼시페롤", "alfacalcidol": "알파칼시돌", "retinol": "레티놀", "retinol acetate": "레티놀아세테이트",
    "retinol palmitate": "레티놀팔미테이트", "retinol palmitate oil": "레티놀팔미테이트유", "beta-carotene": "베타카로틴", "beta-carotene suspension": "베타카로틴",
    "phytonadione": "피토나디온", "menatetrenone": "메나테트레논", "inositol": "이노시톨", "choline": "콜린", "gamma-oryzanol": "감마오리자놀",
    "ubidecarenone": "유비데카레논", "taurine": "타우린", "l-arginine": "L-아르기닌", "arginine": "아르기닌", "l-arginine-l-aspartate": "L-아르기닌-L-아스파르트산",
    "l-ornithine-l-aspartate": "L-오르니틴-L-아스파르트산", "citrulline malate": "시트룰린말산염", "l-carnitine": "L-카르니틴", "dl-carnitine": "dl-카르니틴",
    "carnitine": "카르니틴", "glutathione": "글루타티온", "l-cystine": "L-시스틴", "l-cysteine": "L-시스테인", "dl-methionine": "dl-메티오닌", "l-methionine": "L-메티오닌",
    "l-lysine": "L-라이신", "l-isoleucine": "L-이소류신", "l-leucine": "L-류신", "l-valine": "L-발린", "l-threonine": "L-트레오닌", "l-phenylalanine": "L-페닐알라닌",
    "l-tryptophan": "L-트립토판", "glycine": "글리신", "keratin": "케라틴", "glucosamine": "글루코사민", "sodium chondroitin sulfate": "콘드로이틴황산나트륨",
    "sodium hyaluronate": "히알루론산나트륨", "collagen": "콜라겐", "royal jelly": "로열젤리", "medicinal yeast": "약용효모", "trehalose": "트레할로오스", "glucose": "포도당",
    "magnesium oxide": "산화마그네슘", "magnesium carbonate": "탄산마그네슘", "magnesium glycerophosphate": "글리세로인산마그네슘", "magnesium sulfate": "황산마그네슘",
    "magnesium citrate": "구연산마그네슘", "magnesium chloride": "염화마그네슘", "calcium carbonate": "탄산칼슘", "precipitated calcium carbonate": "침강탄산칼슘",
    "calcium citrate": "구연산칼슘", "calcium gluconate": "글루콘산칼슘", "calcium lactate": "젖산칼슘", "calcium phosphate": "인산칼슘", "dibasic calcium phosphate": "인산수소칼슘",
    "tribasic calcium phosphate": "제삼인산칼슘", "calcium glycerophosphate": "글리세로인산칼슘", "calcium chloride": "염화칼슘", "calcium hydroxyapatite": "칼슘히드록시아파타이트",
    "zinc oxide": "산화아연", "zinc sulfate": "황산아연", "zinc gluconate": "글루콘산아연", "zinc pyrithione": "피리티온아연", "bacitracin zinc": "바시트라신아연",
    "ferrous sulfate": "황산철", "ferrous fumarate": "푸마르산철", "ferrous gluconate": "글루콘산철", "ferric hydroxide polymaltose complex": "수산화제이철폴리말토오스복합체",
    "iron protein succinylate": "철단백숙시닐레이트", "polysaccharide iron complex": "폴리사카라이드철복합체", "carbonyl iron": "카르보닐철", "ferritin extract": "페리틴엑스",
    "selenium": "셀레늄", "selenium in yeast": "셀레늄효모", "sodium selenite": "아셀렌산나트륨", "sodium selenite pentahydrate": "아셀렌산나트륨",
    "chromium in yeast": "크롬효모", "manganese sulfate": "황산망간", "cupric sulfate": "황산구리", "cupric oxide": "산화구리", "copper gluconate": "글루콘산구리",
    "potassium iodide": "요오드화칼륨", "potassium chloride": "염화칼륨", "sodium chloride": "염화나트륨", "potassium sulfate": "황산칼륨", "citric acid": "구연산",
    "cod liver oil": "간유", "safflower oil": "홍화유", "omega-3": "오메가3", "eicosapentaenoic acid": "EPA", "docosahexaenoic acid": "DHA",
    "lutein": "루테인", "p-aminobenzoic acid": "파라아미노벤조산",
    # 유산균
    "lactobacillus": "락토바실루스", "lactobacillus sporogenes": "락토바실루스스포로게네스", "bacillus licheniformis": "바실루스리케니포르미스", "bacillus subtilis": "바실루스서브틸리스",
    "bifidobacterium": "비피도박테리움", "streptococcus faecalis": "스트렙토코쿠스페칼리스", "enterococcus faecium": "엔테로코쿠스페시움",
    "saccharomyces boulardii": "사카로미세스보울라르디", "clostridium butyricum": "클로스트리디움부티리쿰",
    # 피부·외용
    "lidocaine": "리도카인", "benzocaine": "벤조카인", "dibucaine": "디부카인", "pramoxine": "프라목신", "hydrocortisone": "히드로코르티손", "prednisolone": "프레드니솔론",
    "betamethasone": "베타메타손", "dexamethasone": "덱사메타손", "terbinafine": "테르비나핀", "clotrimazole": "클로트리마졸", "ketoconazole": "케토코나졸",
    "miconazole": "미코나졸", "naftifine": "나프티핀", "amorolfine": "아모롤핀", "ciclopirox": "시클로피록스", "gentamicin": "겐타마이신", "neomycin": "네오마이신",
    "mupirocin": "무피로신", "sodium fusidate": "푸시드산나트륨", "polymyxin b": "폴리믹신B", "bacitracin": "바시트라신", "tyrothricin": "티로트리신",
    "povidone iodine": "포비돈요오드", "chlorhexidine": "클로르헥시딘", "benzalkonium": "벤잘코늄", "benzethonium": "벤제토늄", "acrinol": "아크리놀",
    "nitrofurazone": "니트로푸라존", "acyclovir": "아시클로버", "crotamiton": "크로타미톤", "minoxidil": "미녹시딜", "isopropyl methylphenol": "이소프로필메틸페놀",
    "allantoin": "알란토인", "urea": "요소", "heparin": "헤파린", "heparinoid": "헤파리노이드", "aescin": "에스신", "aescin amorphous": "에스신",
    "l-menthol": "L-멘톨", "menthol": "멘톨", "dl-camphor": "dl-캄파", "d-camphor": "d-캄파", "camphor": "캄파", "thymol": "티몰", "eucalyptol": "유칼립톨",
    "vanillyl nonylamide": "노닐산바닐릴아미드", "capsaicin": "캡사이신", "capsicum tincture": "고추팅크", "mentha herb oil": "박하유", "peppermint oil": "박하유",
    "white petrolatum": "백색바셀린", "glycerin": "글리세린", "hypromellose": "히프로멜로오스", "carboxymethylcellulose": "카르복시메틸셀룰로오스", "sodium alginate": "알긴산나트륨",
    "ethanol": "에탄올", "hydroquinone": "히드로퀴논", "tranexamic acid": "트라넥삼산", "carbazochrome": "카르바조크롬", "polydeoxyribonucleotide": "폴리데옥시리보뉴클레오티드",
    "centella titrated extract": "센텔라정량추출물", "guaiazulene": "구아야줄렌", "policresulen": "폴리크레줄렌", "aluminium chloride": "염화알루미늄", "human placenta extract": "인태반엑스",
    "dextran 70": "덱스트란70", "nicotine": "니코틴", "diosmin": "디오스민", "neostigmine": "네오스티그민", "berberine": "베르베린", "sulfamethoxazole": "설파메톡사졸",
    "albendazole": "알벤다졸", "ethinyl estradiol": "에티닐에스트라디올", "desogestrel": "데소게스트렐",
    # 생약
    "ginseng": "인삼", "red ginseng": "홍삼", "ginkgo": "은행엽", "milk-thistle fruit extract": "밀크씨슬열매엑스", "milk thistle": "밀크씨슬", "silymarin": "실리마린",
    "cinnamon bark": "계피", "ginger": "생강", "clove": "정향", "nutmeg": "육두구", "jujube": "대추", "fennel": "회향", "licorice root": "감초",
    "citrus unshiu peel": "진피", "magnolia bark": "후박", "atractylodes rhizome": "창출", "corydalis tuber": "현호색", "gambir": "아선약",
    "phellodendron bark": "황백", "gardenia fruit": "치자", "pueraria root": "갈근", "peony root": "작약", "platycodon root": "길경", "pinellia tuber": "반하",
    "schisandra fruit": "오미자", "astragalus root": "황기", "picrasma wood": "고목", "zanthoxylum peel": "산초", "ephedra herb": "마황", "asiasarum root and rhizome": "세신",
    "cyperus rhizome": "향부자", "amomum fruit": "사인", "amomum tsao-ko fruit": "초과", "bomeolum": "용뇌", "hordei fructus germinatus": "맥아",
    "massa medicata fermentata": "신곡", "patriniae radix": "패장", "piperis longi fructus": "필발", "santali albi lignum": "백단향", "santalini lignum rubrum": "자단향",
    "chaenomelis fructus": "모과", "aloe": "알로에", "onion": "양파", "galgeuntang": "갈근탕", "red ginseng ethanol": "홍삼",
    "ginkgo biloba leaf": "은행엽", "clematidis radix": "위령선", "momordicae semen": "목별자", "myrrh": "몰약", "olibanum": "유향", "ricini semen": "피마자",
    # 기타 자주 나오는 이름
    "trypsin": "트립신", "diastase·protease·cellulase 2000 ii": "디아스타제·프로테아제·셀룰라제", "hypromellose 2910": "히프로멜로오스",
    "scopolamine butylbromide": "스코폴라민부틸브롬화물", "diclofenac diethylammonium": "디클로페낙디에틸암모늄", "lactic acid": "젖산", "ciclopirox olamine": "시클로피록스올아민",
    "d-alpha-tocopherol": "d-알파-토코페롤", "mequitazine": "메퀴타진", "clostridium butyricum toa": "클로스트리디움부티리쿰", "triamcinolone acetonide": "트리암시놀론아세토니드",
    "cobamamide": "코바마미드", "soluble azulene": "수용성아줄렌", "gestodene": "게스토덴", "levonorgestrel": "레보노르게스트렐", "isopropanol": "이소프로판올",
    "lactobacillus casei var.rhamnosus lyophilizate": "락토바실루스카제이", "lactobacillus acidophilus": "락토바실루스아시도필루스", "streptococcus thermophilus": "스트렙토코쿠스써모필루스",
    "bifidobacterium longum": "비피도박테리움롱굼", "bifidobacterium bifidum": "비피도박테리움비피둠", "enterococcus faecalis": "엔테로코쿠스페칼리스",
    "lactobacillus rhamnosus": "락토바실루스람노수스", "lactobacillus plantarum": "락토바실루스플란타룸", "bacillus coagulans": "바실루스코아귤란스",
    "chlorpheniramine maleate": "클로르페니라민말레산염", "pseudoephedrine hydrochloride": "슈도에페드린염산염", "sodium selenite": "아셀렌산나트륨",
    "calcium citrate": "구연산칼슘", "manganese": "망간", "chromium": "크롬", "molybdenum": "몰리브덴", "iodine": "요오드",
}
# 염·형태 접미사 (영문 끝말 → 한글 접미)
SALT_KO: dict[str, str] = {
    "hydrochloride hydrate": "염산염수화물", "hydrobromide hydrate": "브롬화수소산염수화물", "sodium hydrate": "나트륨수화물", "phosphate hydrate": "인산염수화물",
    "hydrochloride": "염산염", "hydrobromide": "브롬화수소산염", "maleate": "말레산염", "nitrate": "질산염", "sulfate": "황산염", "sulphate": "황산염",
    "sodium phosphate": "인산나트륨", "sodium": "나트륨", "potassium": "칼륨", "acetate": "아세테이트", "tartrate": "타르타르산염", "bitartrate": "중타르타르산염",
    "citrate": "시트르산염", "phosphate": "인산염", "gluconate": "글루콘산염", "fumarate": "푸마르산염", "succinate": "숙신산염", "mesylate": "메실산염",
    "besylate": "베실산염", "butyrate": "부티르산염", "lactate": "젖산염", "pamoate": "파모산염", "valerate": "발레레이트", "propionate": "프로피오네이트",
    "dipropionate": "디프로피오네이트", "palmitate": "팔미테이트", "hibenzate": "히벤즈산염", "lysinate": "리시네이트", "methylsulfate": "메틸황산염",
    "chloride": "염화물", "oxide": "산화물", "hemihydrate": "반수화물", "monohydrate": "일수화물", "dihydrate": "이수화물", "trihydrate": "삼수화물", "pentahydrate": "오수화물",
}
FORM_KO = [(" ethanol soft extract", "연조엑스"), (" soft extract", "연조엑스"), (" dried extract", "건조엑스"), (" ethanol extract", "엑스"), (" extract", "엑스"), (" tincture", "팅크"), (" oil", "유")]
STRIP_RE = re.compile(r"\b(powder|granules?|coated|concentrate|concentrated|fine|micronized|microencapsulated|dried|dry|anhydrous|hydrous|solution|crystalline|crystallized|usp|ep|kp|bp|liquid|d\.c)\b")


def _norm(token: str) -> str:
    low = token.lower().strip()
    low = re.sub(r"\s*\([^)]*\)", "", low)
    low = re.sub(r"\d+(\.\d+)?\s*%", " ", low)
    low = STRIP_RE.sub(" ", low)
    return re.sub(r"\s+", " ", low).strip(" ,.")


def to_korean(token: str) -> str:
    """영문 주성분 한 개 → 한글 표시명 (모르면 원문)."""
    raw = (token or "").strip()
    if not raw or re.search(r"[가-힣]", raw):
        return raw
    low = _norm(raw)
    if not low:
        return raw
    if low in KO:
        return KO[low]
    for suffix, ko in FORM_KO:                       # ~ extract / tincture / oil
        if low.endswith(suffix):
            base = low[: -len(suffix)].strip()
            if base in KO:
                return KO[base] + ko
    for salt in sorted(SALT_KO, key=len, reverse=True):   # 염·수화물 접미
        if low.endswith(" " + salt):
            base = low[: -len(salt) - 1].strip()
            if base in KO:
                return KO[base] + SALT_KO[salt]
            for suffix, ko in FORM_KO:
                if base.endswith(suffix) and base[: -len(suffix)].strip() in KO:
                    return KO[base[: -len(suffix)].strip()] + ko + SALT_KO[salt]
    if low.endswith(" hydrate"):                           # '… Hydrate' 는 수화물
        inner = to_korean(low[: -len(" hydrate")].strip())
        if not re.fullmatch(r"[a-z0-9 .,()\-·%]+", inner):
            return inner + "수화물"
    return raw


def coverage(tokens) -> float:
    """토큰 목록 중 한글로 바꾼 비율 (점검용)."""
    toks = [t for t in tokens if t]
    return sum(1 for t in toks if to_korean(t) != t) / len(toks) if toks else 0.0
