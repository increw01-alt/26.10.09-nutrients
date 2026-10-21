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
    # ---- 2026-10 보강: 허가정보에서 영문으로 남던 이름 (빈도순 점검 결과)
    # 소화효소 (뒤의 역가 표기 'Cellulase 2000 II', 'Lipase AP6' 는 ENZYME_RE 가 붙여 준다)
    "diastase": "디아스타제", "biodiastase": "비오디아스타제", "protease": "프로테아제", "hemicellulase": "헤미셀룰라제", "prozyme": "프로자임",
    "pancellase": "판셀라제", "panprosin": "판프로신", "newlase": "뉴라제", "pancrelipase": "판크렐리파제", "papain": "파파인", "pepsin": "펩신",
    "saccharated pepsin": "당화펩신", "beta-galactosidase": "베타-갈락토시다제", "pancreatin enteric": "판크레아틴장용",
    "pancreatin enteric tablets": "판크레아틴장용정", "pancreatin enteric pellets": "판크레아틴장용펠렛", "aspirin enteric": "아스피린장용",
    "pancrease": "판크레아스", "peg": "폴리에틸렌글리콜", "ox bile": "우담즙", "alginic acid": "알긴산", "cholecalciferol mixture": "콜레칼시페롤",
    "sodium sulfamethoxazole": "설파메톡사졸나트륨", "sodium n-acetylaspartylglutamate": "N-아세틸아스파틸글루탐산나트륨", "belladonna alkaloid": "벨라돈나알칼로이드",
    # 비타민·미네랄·아미노산
    "vitamin a": "비타민A", "vitamin c": "비타민C", "vitamin d": "비타민D", "vitamin d3": "비타민D3", "vitamin e": "비타민E",
    "vitamin b1": "비타민B1", "vitamin b2": "비타민B2", "vitamin b6": "비타민B6", "vitamin b12": "비타민B12",
    "alpha-tocopherol": "알파-토코페롤", "dl-alpha-tocopherol": "dl-알파-토코페롤", "alpha-tocopherol acetate": "알파-토코페롤아세테이트",
    "tocopheryl acetate": "토코페릴아세테이트", "d-alpha-tocopheryl acetate": "d-알파-토코페릴아세테이트", "dl-alpha-tocopheryl acetate": "dl-알파-토코페릴아세테이트",
    "thiamine monophosphate": "티아민일인산", "thiamine disulfide": "티아민디설피드", "pantethine": "판테틴", "calcium folinate": "폴린산칼슘",
    "yeast": "효모", "molybden": "몰리브덴", "chromic chloride": "염화크롬", "copper sulfate": "황산구리", "zinc histidine": "히스티딘아연",
    "pyrithione zinc": "피리티온아연", "magnesium aspartate": "아스파르트산마그네슘", "magnesium pidolate": "피돌산마그네슘",
    "magnesium lactate": "젖산마그네슘", "magnesium hydrogen phosphate": "인산수소마그네슘", "light magnesium oxide": "경질산화마그네슘",
    "heavy magnesium oxide": "중질산화마그네슘", "potassium l-aspartate": "L-아스파르트산칼륨", "sennoside calcium": "센노시드칼슘",
    "sodium ferric gluconate complex": "글루콘산제이철나트륨착염", "iron acetyl transferrin": "철아세틸트랜스페린", "ferric manitol ovalbumin": "철만니톨오브알부민",
    "chlorophyllin copper": "클로로필린구리", "chlorophyllin copper complex sodium": "클로로필린구리나트륨착염",
    "l-glutamine": "L-글루타민", "glutamine": "글루타민", "l-alanine": "L-알라닌", "alanine": "알라닌", "l-glutamic acid": "L-글루탐산",
    "glutamic acid": "글루탐산", "l-citrulline": "L-시트룰린", "l-ornithine": "L-오르니틴", "levocarnitine": "레보카르니틴",
    "carnitine orotate": "카르니틴오로트산염", "arginine tidiacicate": "아르기닌티디아시케이트", "dl-phosphoserine": "DL-포스포세린",
    "l-phosphoserine": "L-포스포세린", "l-phosphothreonine": "L-포스포트레오닌", "glucuronolactone": "글루쿠로노락톤", "adenine": "아데닌",
    "cytidine": "시티딘", "uridine": "우리딘", "orotic acid": "오로트산", "beta-sitosterol": "베타-시토스테롤",
    "unsaponifiable matter of soybean oil": "대두유불검화물", "antitoxic liver": "항독성간장", "liver hydrolysate": "간장가수분해물", "cattle gallstone": "우황",
    # 해열·진통·감기·소화기·기타 약물
    "nizatidine": "니자티딘", "domperidone": "돔페리돈", "berberine tannate": "베르베린탄닌산염", "nifuroxazide": "니푸록사지드",
    "flubendazole": "플루벤다졸", "sobrerol": "소브레롤", "troxerutin": "트록세루틴", "casanthranol": "카산트라놀", "lactitol": "락티톨",
    "bismuth subcarbonate": "차탄산비스무트", "boehmite": "보에마이트", "methylmethionine sulfonium chloride": "메틸메티오닌설포늄염화물",
    "dihydroxydibutyl ether": "디히드록시디부틸에테르", "isopropylantipyrine": "이소프로필안티피린", "allylisopropylacetylurea": "알릴이소프로필아세틸우레아",
    "ibuprofen arginine": "이부프로펜아르기닌", "ibuprofen lysine": "이부프로펜리신", "prednisolone valeroacetate": "프레드니솔론발레로아세테이트",
    "d-chlorpheniramine": "d-클로르페니라민", "dexchlorpheniramine": "덱스클로르페니라민", "pheniramine": "페니라민", "clemastine": "클레마스틴",
    "cyproheptadine": "시프로헵타딘", "l-carbocisteine": "L-카르보시스테인", "butamirate citrate": "구연산부타미레이트", "benproperine": "벤프로페린",
    "levocloperastine fendizoate": "레보클로페라스틴펜디조산염", "diprophylline": "디프로필린", "ammonium chloride": "염화암모늄",
    "ammonium glycyrrhizinate": "글리시리진산암모늄", "difenidol": "디페니돌", "glycopyrrolate": "글리코피롤레이트", "brimonidine": "브리모니딘",
    "sodium cromoglicate": "크로몰린나트륨", "nicotine polacrilex": "니코틴폴라크릴렉스", "medicinal carbon": "약용탄", "alfatradiol": "알파트라디올",
    "ethyl aminobenzoate": "아미노안식향산에틸", "diclofenac diethylamine": "디클로페낙디에틸아민", "diclofenac epolamine": "디클로페낙에폴아민",
    "diethylamine salicylate": "살리실산디에틸아민", "mucopolysaccharide polysulfate": "뮤코폴리사카리드폴리설페이트",
    "purified and flavonoid fraction": "미세정제플라보노이드분획물", "standardized lyophyllized of bacterial lysate": "표준화동결건조세균용해물",
    # 외용·소독·항진균
    "butenafine": "부테나핀", "econazole": "에코나졸", "isoconazole": "이소코나졸", "sertaconazole": "세르타코나졸", "nifuratel": "니푸라텔",
    "nystatin": "니스타틴", "fusidic acid": "푸시드산", "hinokitiol": "히노키티올", "azelaic acid": "아젤라산", "benzoyl peroxide": "과산화벤조일",
    "carbamide peroxide": "카바마이드퍼옥사이드", "hydrogen peroxide": "과산화수소", "peracetic acid": "과아세트산", "sodium percarbonate": "과탄산나트륨",
    "sodium hypochlorite": "차아염소산나트륨", "ethylene oxide": "에틸렌옥사이드", "propanol": "프로판올", "octenidine": "옥테니딘",
    "phenoxyethanol": "페녹시에탄올", "alkyldiaminoethylglycine": "알킬디아미노에틸글리신", "methylbenzethonium chloride": "메틸벤제토늄염화물",
    "9-aminoacridine undecylenate": "9-아미노아크리딘운데실렌산염", "nonoxynol 9": "노녹시놀9", "tannic acid": "탄닌산", "lanolin": "라놀린",
    "trolamine": "트롤아민", "piperonyl butoxide": "피페로닐부톡시드", "pyrethrin": "피레트린", "sodium fluoride": "불화나트륨", "guaiacol": "구아야콜",
    "dl-menthol": "dl-멘톨", "borneol": "보르네올", "camphen": "캄펜", "camphene": "캄펜", "anethole": "아네톨", "fenchone": "펜콘", "pinene": "피넨",
    "menthone": "멘톤", "cineole": "시네올", "sterile water for irrigation": "관류용멸균증류수", "sterile sea water": "멸균해수",
    "sterile isotonic sea water": "멸균등장해수",
    # 부형제·염류
    "carbomer": "카보머", "povidone": "포비돈", "polysorbate 80": "폴리소르베이트80", "polyethylene glycol 400": "폴리에틸렌글리콜400",
    "polyethylene glycol 3350": "폴리에틸렌글리콜3350", "polyethylene glycol 4000": "폴리에틸렌글리콜4000", "d-sorbitol": "D-소르비톨",
    "sorbitol": "소르비톨", "lactose": "유당", "potassium citrate": "구연산칼륨", "sodium citrate": "구연산나트륨", "potassium bicarbonate": "탄산수소칼륨",
    "dibasic potassium phosphate": "인산수소칼륨", "monobasic sodium phosphate": "인산이수소나트륨", "sodium hydrogen phosphate": "인산수소나트륨",
    "ammonium lactate": "젖산암모늄",
    # 유산균
    "enterococcus lactis sf68": "엔테로코쿠스락티스SF68", "enterococcus faecalis bio-4r": "엔테로코쿠스페칼리스BIO-4R",
    "bacteria culture of lactobacillus rhamnosus r0011 and lactobacillus helveticus r0052": "락토바실루스람노수스R0011·헬베티쿠스R0052배양물",
    # 생약 (대한약전 생약명)
    "liriope tuber": "맥문동", "oryzae semen": "갱미", "angelica gigas root": "당귀", "angelica dahurica root": "백지", "coptis rhizome": "황련",
    "polygala root": "원지", "swertia herb": "당약", "gentian root and rhizome": "용담", "atractylodes rhizome white": "백출", "cnidium rhizome": "천궁",
    "lycium fruit": "구기자", "apricot kernel": "행인", "perilla leaf": "자소엽", "hawthorn fruit": "산사", "poncirus immature fruit": "지실",
    "aurantii fructus immaturus": "지실", "rhubarb": "대황", "mume fruit": "오매", "coix seed": "의이인", "arctium fruit": "우방자",
    "forsythia fruit": "연교", "schizonepeta spike": "형개", "gypsum fibrosum": "석고", "ostericum root": "강활", "saposhnikovia root": "방풍",
    "lonicera flower": "금은화", "lophatheri herba": "담죽엽", "mentha herb": "박하", "glycine semen preparatum": "담두시",
    "gazellae seu saigae cornu": "영양각", "aucklandiae radix": "목향", "scutellaria root": "황금", "curcuma root": "울금", "curcuma root radix": "울금",
    "moutan root bark": "목단피", "lithospermum root": "자근", "bupleurum root": "시호", "magnoliae flos": "신이", "trichosanthes seed": "과루인",
    "raw ginger": "생강", "cervi parvum cornu": "녹용", "eucommiae cortex": "두충", "polygonatum rhizome": "황정", "epimedium herb": "음양곽",
    "astragali radix": "황기", "artemisiae capillaris herba": "인진호", "nandina domestica thunberg": "남천", "ivy leaf": "아이비엽",
    "vitis vinifera leaf": "포도엽", "bilberry fruit": "빌베리", "aesculus hippocastanum l. seeds": "서양칠엽수씨", "cardus marianus": "카르두스마리아누스",
    "milk-thistle fruit": "밀크씨슬열매", "st. john's wort": "세인트존스워트", "chamomilla": "카모밀라", "chamomiila": "카모밀라", "cepae": "양파",
    "allium sativum": "마늘", "geranium herb": "현초", "plantago herb": "차전초", "psyllium husk": "차전자피", "senega": "세네가", "capsicum": "고추",
    "sennae fructus": "센나열매", "senna fruit": "센나열매", "tinnevelly senna fruit": "센나열매",
    # 한방 처방 (영문 음역)
    "bangpungtongsungsan": "방풍통성산", "socheongryongtang": "소청룡탕", "ssanghwatang": "쌍화탕", "hyangsosan": "향소산", "maegmundongtang": "맥문동탕",
    # 처방약·위장약 성분 (약별 영양제 가이드 drug-pairings.json 규칙의 대표 성분 표기용 — e약은요 수집분에는 드문 전문의약품 포함)
    "aluminium phosphate": "인산알루미늄", "lansoprazole": "란소프라졸", "rabeprazole": "라베프라졸", "tegoprazan": "테고프라잔", "fexuprazan": "펙수프라잔",
    "sodium picosulfate": "피코설페이트나트륨", "picosulfate": "피코설페이트",
    "atorvastatin": "아토르바스타틴", "rosuvastatin": "로수바스타틴", "simvastatin": "심바스타틴", "pravastatin": "프라바스타틴", "pitavastatin": "피타바스타틴",
    "fluvastatin": "플루바스타틴", "lovastatin": "로바스타틴", "ezetimibe": "에제티미브",
    "levothyroxine": "레보티록신", "liothyronine": "리오티로닌", "warfarin": "와파린", "clonixin": "클로닉신",
    "doxycycline": "독시사이클린", "minocycline": "미노사이클린", "tetracycline": "테트라사이클린", "ciprofloxacin": "시프로플록사신", "levofloxacin": "레보플록사신",
    "ofloxacin": "오플록사신", "moxifloxacin": "목시플록사신",
    "alendronate": "알렌드로네이트", "alendronic acid": "알렌드론산", "risedronate": "리세드로네이트", "ibandronate": "이반드로네이트",
    "metformin": "메트포르민", "drospirenone": "드로스피레논",
    "furosemide": "푸로세미드", "hydrochlorothiazide": "히드로클로로티아지드", "chlorthalidone": "클로르탈리돈", "torsemide": "토르세미드", "indapamide": "인다파미드",
    "isotretinoin": "이소트레티노인", "tretinoin": "트레티노인", "acitretin": "아시트레틴", "alitretinoin": "알리트레티노인",
    "methotrexate": "메토트렉세이트", "methylprednisolone": "메틸프레드니솔론", "deflazacort": "데플라자코트",
}
# 염·형태 접미사 (영문 끝말 → 한글 접미)
SALT_KO: dict[str, str] = {
    "hydrochloride hydrate": "염산염수화물", "hydrobromide hydrate": "브롬화수소산염수화물", "sodium hydrate": "나트륨수화물", "phosphate hydrate": "인산염수화물",
    "hydrochloride": "염산염", "hydrobromide": "브롬화수소산염", "maleate": "말레산염", "nitrate": "질산염", "sulfate": "황산염", "sulphate": "황산염",
    "sodium phosphate": "인산나트륨", "sodium": "나트륨", "potassium": "칼륨", "acetate": "아세테이트", "tartrate": "타르타르산염", "bitartrate": "중타르타르산염",
    "citrate": "시트르산염", "phosphate": "인산염", "gluconate": "글루콘산염", "fumarate": "푸마르산염", "succinate": "숙신산염", "mesylate": "메실산염",
    "besylate": "베실산염", "butyrate": "부티르산염", "lactate": "젖산염", "pamoate": "파모산염", "valerate": "발레레이트", "propionate": "프로피오네이트", "orotate": "오로트산염",
    "dipropionate": "디프로피오네이트", "palmitate": "팔미테이트", "hibenzate": "히벤즈산염", "lysinate": "리시네이트", "methylsulfate": "메틸황산염",
    "chloride": "염화물", "oxide": "산화물", "hemihydrate": "반수화물", "monohydrate": "일수화물", "dihydrate": "이수화물", "trihydrate": "삼수화물", "pentahydrate": "오수화물",
}
# 제형 접미사 (긴 것부터). '30% Ethanol Fluid Extract' 처럼 앞의 농도 표기는 _norm 이 지운다
FORM_KO = [
    (" ethanol soft extract", "연조엑스"), (" methanol soft extract", "연조엑스"), (" soft extract", "연조엑스"),
    (" ethanol dried extract", "건조엑스"), (" methanol dried extract", "건조엑스"), (" dried extract", "건조엑스"),
    (" ethanol fluid extract", "유동엑스"), (" fluid extract", "유동엑스"), (" fluidextract", "유동엑스"),
    (" ethanol extract", "엑스"), (" extract", "엑스"), (" ethanol tincture", "팅크"), (" tincture", "팅크"), (" oil", "유"),
    (" culture", "배양물"), (" decoction", "탕"),
]
# 접두사 (Dried Ferrous Sulfate → 건조황산철, Light Magnesium Oxide → 경질산화마그네슘)
PREFIX_KO = [("dried ", "건조"), ("light ", "경질"), ("heavy ", "중질"), ("synthetic ", "합성"), ("precipitated ", "침강"), ("sterile ", "멸균")]
# 소화효소 + 역가 표기: 'Cellulase 2000 II' → 셀룰라제2000II, 'Lipase AP6' → 리파제AP6, 'Protease N 1' → 프로테아제N1
_DESIG = r"(?:[a-z]{0,3}\d+[a-z]*|i{1,3}|n)"
ENZYME_RE = re.compile(r"^(diastase|biodiastase|protease|cellulase|hemicellulase|lipase|prozyme|pancellase|panprosin|newlase|pancreatin|pancrelipase|papain|pepsin|trypsin|bromelain|lysozyme)"
                       rf"(?:\s+({_DESIG}(?:\s+{_DESIG})*))?$")
STRIP_RE = re.compile(r"\b(powder|granules?|granular|coated|concentrate|concentrated|fine|micronized|microencapsulated|dry|anhydrous|hydrous|solution|crystalline|crystallized|usp|ep|kp|bp|liquid|d\.c)\b")


def _norm(token: str) -> str:
    low = token.lower().strip()
    low = re.sub(r"\s*\([^)]*\)", "", low)
    low = re.sub(r"\d+(\.\d+)?\s*%", " ", low)
    low = STRIP_RE.sub(" ", low)
    low = re.sub(r"\s+type\s*\S+$", "", low)          # 'Calcium Pantothenate Type S', 'Cholecalciferol Type100CWS'
    low = re.sub(r"\s+", " ", low).strip(" ,.")
    return re.sub(r"\s+dried$", "", low)               # 'Phytonadione Dried Powder' → powder 를 지우고 끝에 남은 dried


def _translate(low: str) -> str | None:
    """정규화된 소문자 영문 → 한글 (사전·제형·염·접두사를 재귀로 조합). 못 바꾸면 None."""
    if not low:
        return None
    if low in KO:
        return KO[low]
    m = ENZYME_RE.match(low)
    if m and m.group(1) in KO:
        return KO[m.group(1)] + (m.group(2) or "").replace(" ", "").upper()
    m = re.fullmatch(r"(.+?) in (?:dried )?yeast", low)   # 'Selenium in Dried Yeast' → 셀레늄효모
    if m:
        inner = _translate(m.group(1))
        if inner:
            return inner + "효모"
    for suffix, ko in FORM_KO:                             # ~ extract / tincture / oil
        if low.endswith(suffix):
            inner = _translate(low[: -len(suffix)].strip())
            if inner:
                return inner + ko
    for salt in sorted(SALT_KO, key=len, reverse=True):    # 염·수화물 접미 (겹치면 안쪽부터: Lidocaine Hydrochloride Monohydrate)
        if low.endswith(" " + salt):
            inner = _translate(low[: -len(salt) - 1].strip())
            if inner:
                return inner + SALT_KO[salt]
    if low.endswith(" hydrate"):                           # '… Hydrate' 는 수화물
        inner = _translate(low[: -len(" hydrate")].strip())
        if inner:
            return inner + "수화물"
    for prefix, ko in PREFIX_KO:
        if low.startswith(prefix):
            inner = _translate(low[len(prefix):].strip())
            if inner:
                return ko + inner
    return None


def to_korean(token: str) -> str:
    """영문 주성분 한 개 → 한글 표시명 (모르면 원문)."""
    raw = (token or "").strip()
    if not raw or re.search(r"[가-힣]", raw):
        return raw
    return _translate(_norm(raw)) or raw


def coverage(tokens) -> float:
    """토큰 목록 중 한글로 바꾼 비율 (점검용)."""
    toks = [t for t in tokens if t]
    return sum(1 for t in toks if to_korean(t) != t) / len(toks) if toks else 0.0
