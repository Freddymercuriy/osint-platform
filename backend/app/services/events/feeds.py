"""Kalit so'zlar va regexlar (hudud, mavzu, shovqin, chet el belgilari).

Manbalar ro'yxati endi bazada (`sources` jadvali, admin panel / API orqali boshqariladi). v1 dagi `FEEDS`
ro'yxati `migrations/versions/0004_seed_sources.py` ga muzlatib ko'chirilgan.
"""

from __future__ import annotations


# =========================================================================
#  HUDUD kalit so'zlari — Markaziy Osiyo: UZ, KZ, KG, TJ, TM (kichik harfda).
#  Aggregator'dagi _kw_regex bo'yicha: o'zak (prefiks) — chap chegara bilan:
#  "uzbek" → "uzbekistan" ga mos, "xuzbek" ga emas.  "'" belgisi har xil
#  apostroflarga (' ‘ ’ ʻ ʼ `) va ularning yo'qligiga mos keladi.
#  ".uz" kabi domenlar — domen oxiri sifatida (davomi bo'lmasligi kerak).
#  Ataylab TASHLANGAN (yolg'on mos kelish): "osh", "semey", "kaspi" (Каспий),
#  "karshi", "talas", "naryn", "mary", "petropavl".
# =========================================================================
COUNTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "UZ": (
        "uzbek", "o'zbek", "узбек", "ўзбек", "ӯзбек",
        "tashkent", "toshkent", "ташкент", "тошкент",
        "samarkand", "samarqand", "самарканд", "самарқанд",
        "bukhara", "buxoro", "бухара", "бухоро",
        "andijan", "andijon", "андижан", "андижон",
        "namangan", "наманган", "fergana", "ferghana", "farg'ona", "фергана", "фарғона",
        "nukus", "нукус", "urgench", "urganch", "ургенч", "termez", "termiz", "термез",
        "kokand", "qo'qon", "коканд", "qoraqalpoq", "karakalpak", "каракалпак",
        "khorezm", "xorazm", "хорезм",
        ".uz",
    ),
    "KZ": (
        "kazakh", "kazakstan", "kazahstan", "qozoq", "qozog'", "қозоқ", "қозоғ",
        "казах", "қазақ", "astana", "астана", "nur-sultan", "нур-султан",
        "almaty", "алматы", "алма-ата", "shymkent", "шымкент", "chimkent", "чимкент",
        "karaganda", "караганд", "қарағанды", "aktobe", "актобе", "ақтөбе",
        "atyrau", "атырау", "aktau", "актау", "pavlodar", "павлодар",
        "kostanay", "костанай", "kyzylorda", "кызылорда", "oskemen", "усть-каменогорск",
        ".kz",
    ),
    "KG": (
        "kyrgyz", "kirghiz", "kirgiz", "qirg'iz", "киргиз", "кыргыз", "қирғиз", "қырғыз",
        "bishkek", "бишкек", "jalal-abad", "джалал-абад",
        ".kg",
    ),
    "TJ": (
        "tajik", "tadjik", "tojik", "таджик", "тоҷик", "тожик",
        "dushanbe", "душанбе", "khujand", "xo'jand", "худжанд", "хуҷанд", "khatlon", "хатлон",
        ".tj",
    ),
    "TM": (
        "turkmen", "turkman", "туркмен", "ashgabat", "ashkhabad", "ashgabad",
        "ашхабад", "ашгабат", "turkmenbashi", "dashoguz", "дашогуз",
        ".tm",
    ),
}

# Butun mintaqa (aniq davlatni bildirmaydi)
REGIONWIDE_KEYWORDS: tuple[str, ...] = (
    "central asia", "centralasia", "markaziy osiyo", "o'rta osiyo", "марказий осиё",
    "орталық азия", "центральная ази", "центральной ази", "центральную ази",
    "центральной азией", "центральноазиат", "средняя ази", "средней ази",
    "среднюю ази", "средней азией",
)

REGION_KEYWORDS: tuple[str, ...] = (
    tuple(k for kws in COUNTRY_KEYWORDS.values() for k in kws if not k.startswith("."))
    + REGIONWIDE_KEYWORDS
    + tuple(k for kws in COUNTRY_KEYWORDS.values() for k in kws if k.startswith("."))
)

# Orqaga moslik: boshqa joylarda `UZ_KEYWORDS` import qilinadi.
UZ_KEYWORDS = REGION_KEYWORDS


# =========================================================================
#  MAVZU kalit so'zlari — kiberxavfsizlik / data leak.
#  1) TOPIC_STEMS — aniq o'zaklar (prefiks, chap chegara bilan).
#  2) TOPIC_PATTERNS — (belgi, regex): kontekst talab qiladigan iboralar
#     ("утечка" yolg'iz — gaz sizishi bo'lishi mumkin; "firibgarlik" yolg'iz
#     yetarli emas — faqat online/kiber kontekst bilan).
#  3) TOPIC_NOISE — mavzuga o'xshab ketadigan, lekin kiber bo'lmagan iboralar;
#     moslashishdan oldin matndan olib tashlanadi (kiberspot, jismoniy "взлом"...).
#  Regex ichida "'" — ixtiyoriy apostrof (filters.py moslashtiradi).
# =========================================================================
TOPIC_STEMS: tuple[str, ...] = (
    # umumiy kiber
    "cyber", "кибер", "kiber", "infosec", "information security",
    "информационная безопасност", "информационной безопасност", "информационную безопасност",
    "axborot xavfsizlig", "ахборот хавфсизлиг", "ақпараттық қауіпсіздік",
    # hakerlar
    "hacker", "hacked", "hacking", "hacktivis", "хакер", "ҳакер", "xaker", "хакнул",
    "взлом", "взлома", "хакнут",
    # zararli dastur / hujumlar
    "ransomware", "рэнсомвар", "рансомвар", "шифровальщик", "malware", "spyware",
    "infostealer", "info-stealer", "botnet", "ботнет", "backdoor", "бэкдор", "rootkit",
    "keylogger", "кейлоггер", "trojan", "троян", "вредонос", "зловред", "зиянды бағдарлама",
    "zararli dastur", "kompyuter virus", "компьютерный вирус", "компьютерные вирус",
    "компьютерного вирус", "phishing", "фишинг", "ddos", "ддос", "dos-атак", "dos attack",
    "zero-day", "zero day", "нулевого дня", "нулевой день", "0-day",
    "threat actor", "deepfake", "дипфейк", "sim-swap", "sim swap", "credential stuffing",
    "account takeover", "data breach", "data leak", "data leakage", "security breach",
    "dark web", "darknet", "даркнет", "дарквеб", "darkweb",
    "to'lov talab qiluvchi", "tovlamachi dastur", "troyan",
)

_G3 = r"(?:\w+[^\w.!?]+){0,3}"  # 0-3 so'z oralig'i (gap chegarasi nuqta/!/? da to'xtaydi)
_G2 = r"(?:\w+[^\w.!?]+){0,2}"
_G6 = r"(?:\w+[^\w.!?]+){0,6}"
_SEP = r"[^\w.!?]+"

TOPIC_PATTERNS: tuple[tuple[str, str], ...] = (
    # --- Zaiflik ---
    ("cve", r"cve-\d{4}-\d{3,}"),
    ("уязвимость", r"уязвимост\w*" + _SEP + _G3 +
     r"(?:по\b|программ|систем|безопасн|windows|android|ios|браузер|сервер|нулев|критическ|"
     r"cve|chrome|linux|роутер|протокол|кибер)"),
    ("vulnerability", r"vulnerabilit\w*" + _SEP + _G3 +
     r"(?:software|system|security|cve|patch|code|browser|server|network|android|windows|"
     r"ios|cyber|critical|remote|firmware|router)"),
    ("vulnerability", r"(?:security|software|critical|remote|zero-day|system|firmware)" +
     _SEP + _G2 + r"vulnerabilit"),
    ("zaiflik", r"zaiflik\w*" + _SEP + _G3 +
     r"(?:dastur|tizim|xavfsizlik|kiber|server|sayt|brauzer|aniqlan|bartaraf)"),
    ("zaiflik", r"(?:xavfsizlik|dastur\w*|tizim\w*|server\w*|brauzer\w*)" + _SEP + _G2 +
     r"zaifli"),
    ("уязвимость", r"(?:критическ\w*|нулевог\w*)" + _SEP + r"уязвимост"),
    # --- Fishing / firibgarlik (faqat online kontekst bilan) ---
    ("fishing", r"fishing" + _SEP + r"(?:hujum|sayt|havola|xabar|xat|usul|sxema|firibgar|"
                r"kampaniya)"),
    ("мошенничество онлайн", r"(?:мошенн|афер)\w*" + _SEP + _G3 +
     r"(?:онлайн|online|интернет|в сети|фишинг|аккаунт|телеграм|telegram|ссылк|сайт|"
     r"приложени|банковск\w* карт|мессенджер|вирус|соцсет|социальн\w* сет|криптовалют|"
     r"смс|sms|qr)"),
    ("мошенничество онлайн", r"(?:онлайн|интернет|кибер|сетев|телеграм|фишингов)\w*[- ]"
                             r"(?:мошенн|афер)"),
    ("firibgarlik onlayn", r"(?:firibgar|aldov|firibgarlik)\w*" + _SEP + _G3 +
     r"(?:onlayn|online|internet|tarmoq|telegram|havola|sayt|akkaunt|ilova|plastik|karta|"
     r"sms|virus|ijtimoiy|kripto)"),
    ("firibgarlik onlayn", r"(?:onlayn|online|internet|internetda|tarmoqda|telegramda)" +
     _SEP + _G2 + r"(?:firibgar|aldov)"),
    ("алаяқтық", r"алаяқ\w*" + _SEP + _G3 +
     r"(?:онлайн|интернет|желі|фишинг|аккаунт|телеграм|сілтеме|карта|смс)"),
    ("алаяқтық", r"(?:онлайн|интернет|желіл\w*)" + _SEP + _G2 + r"алаяқ"),
    # --- Ruxsatsiz kirish ---
    ("unauthorized access", r"unauthori[sz]ed" + _SEP + _G2 + r"access"),
    ("несанкц. доступ", r"несанкционированн\w*" + _SEP + r"доступ\w*" + _SEP +
     r"(?:к" + _SEP + r")?(?:данн|систем|сети|сервер|баз|информац|аккаунт|ресурс)"),
    ("ruxsatsiz kirish", r"ruxsatsiz" + _SEP + r"(?:kir|foydalan|murojaat)"),
    ("xavfsizlik buzil", r"(?:axborot|kiber|tizim|server|sayt|akkaunt)\w*" + _SEP + _G2 +
     r"(?:buzil|buzdi|buzib|hujum)"),
    # --- Hujum / zararli dastur (kontekstli) ---
    ("вымогатель", r"(?:программ\w*|вирус\w*|троян\w*)[- ]вымогател"),
    ("шпионское ПО", r"шпионск\w*" + _SEP + r"(?:программ|по\b|софт|приложени)"),
    ("apt", r"\bapt ?\d{1,2}\b"),
    ("DoS", r"\bdos\b" + _SEP + _G2 + r"(?:attack|атак|hujum)"),
    # --- Data leak: ingliz ---
    ("data leak", r"(?:data|database|databases|records|credentials|passwords?|"
                  r"personal (?:data|information)|customer data|user data|user records|"
                  r"private data|sensitive data)" + _SEP + _G3 +
     r"(?:leak|breach|exposed|stolen|compromised|dumped|hacked|for sale|sold)"),
    ("data leak", r"(?:leak\w*|breach\w*|stole|stolen|exposed|exposes|dumped|compromised)" +
     _SEP + _G3 + r"(?:data|database|records|credentials|passwords|personal information|"
                  r"customer information|user information)"),
    ("dark web", r"(?:dark ?web|darknet|даркнет|дарквеб)" + _SEP + _G6 +
     r"(?:data|database|leak|баз|данн|утеч|слив|ma'lumot|sotuv|продаж|продав|продаёт|"
     r"продает|sale|sold)"),
    ("dark web", r"(?:data|database|leak|баз|данн|утеч|слив|ma'lumot|sotuv|продаж|sale|sold)" +
     r"\w*" + _SEP + _G6 + r"(?:dark ?web|darknet|даркнет|дарквеб)"),
    # --- Data leak: rus ---
    ("утечка данных", r"утечк\w*" + _SEP + _G3 +
     r"(?:данн|информац|персональн|баз|пароле|паролей|учетн|учётн|клиент|пользовател|"
     r"сведен|конфиденциальн|документ)"),
    ("утечка данных", r"(?:данн\w*|баз\w*|информаци\w*|пароли|сведени\w*|аккаунт\w*|"
                      r"документ\w*)" + _SEP + _G3 +
     r"(?:утек|утечк|слит|слили|слив|украден|похищен|скомпрометирован|попал\w* в (?:сеть|даркнет|"
     r"открыт)|в открытом доступе|выставлен\w* на продажу|продаются|продают)"),
    ("кража данных", r"(?:краж\w*|хищен\w*|похищен\w*)" + _SEP + _G2 +
     r"(?:данн|персональн|учетн|учётн|паролей|аккаунт|криптовалют)"),
    ("кража данных", r"(?:украли|украден\w*|похитил\w*|слили|слит\w*|слил)" + _SEP + _G3 +
     r"(?:данн|персональн|баз\w* данн|паролей|аккаунт)"),
    ("слив", r"слив\w*" + _SEP + _G2 + r"(?:данн|баз|персональн|паролей|переписк)"),
    # --- Data leak: o'zbek lotin ---
    ("ma'lumot sizib", r"ma'?lumot\w*" + _SEP + _G3 +
     r"(?:sizib|sizdi|sizish|o'?g'?irla|oshkor|tarqal|tarqat|sotil|sotuvga|hack|xaker|fosh|"
     r"ochiq\w* (?:holat|tarmoq))"),
    ("ma'lumot sizib", r"(?:sizib|sizdi|o'?g'?irlan|o'?g'?irla|fosh)\w*" + _SEP + _G3 +
     r"(?:shaxsiy )?ma'?lumot"),
    ("ma'lumot o'g'irlash", r"(?:shaxsiy|maxfiy|bank|karta)\w*" + _SEP + _G2 +
     r"(?:ma'?lumot|raqam)\w*" + _SEP + _G2 + r"(?:sizib|o'?g'?irl|oshkor|sotil|fosh)"),
    # --- Data leak: o'zbek kirill ---
    ("маълумот сизиб", r"маълумот\w*" + _SEP + _G3 +
     r"(?:сизиб|сизди|ўғирла|ошкор|сотувга|тарқал|хакер)"),
    ("маълумот сизиб", r"(?:сизиб|сизди|ўғирлан|ўғирла)\w*" + _SEP + _G3 + r"маълумот"),
    # --- Data leak: qozoq ---
    ("деректер ағып", r"(?:жеке )?деректер\w*" + _SEP + _G3 +
     r"(?:ағып|ұрлан|ұрлау|жария|сатылым|сатуға|хакер)"),
)

TOPIC_NOISE: tuple[str, ...] = (
    # esports / brendlar / marketing
    r"cyber ?monday", r"cybertruck", r"cyberpunk", r"cyber-?sport\w*", r"cyber ?park",
    r"киберспорт\w*", r"киберпанк\w*", r"киберфутбол\w*", r"kibersport\w*", r"киберспорт",
    r"growth hacking", r"life ?hack\w*", r"trojan horse", r"троянск\w* кон\w*",
    # jismoniy "взлом" (kvartira, mashina, seyf...)
    r"взлом\w*" + _SEP + r"(?:\w+" + _SEP + r"){0,2}(?:квартир|дом\b|домо|двер|замк|авто|машин|"
    r"сейф|гараж|магазин|склад|офис|кассу|банкомат|окн|такси)",
    r"(?:квартир\w*|двер\w*|замк\w*|сейф\w*|гараж\w*|склад\w*|магазин\w*|банкомат\w*)" + _SEP +
    r"(?:\w+" + _SEP + r"){0,2}взлом\w*",
    # tabiiy resurs "утечка"
    r"утечк\w*" + _SEP + r"(?:газа|нефти|воды|тепла|мозгов|кадров|радиации)",
)


# =========================================================================
#  CHET EL belgilari (regex bo'laklari, chap chegara avtomatik qo'yiladi).
#  Mahalliy saytlar jahon kiber-yangiliklarini ham bosadi ("FQB: xakerlar...",
#  "KXDR xakerlari $400 mln o'g'irladi"). Lenta Markaziy Osiyo haqida bo'lishi
#  kerak, shuning uchun matnda shu belgilardan biri bo'lib, REGION_KEYWORDS dan
#  hech biri uchramasa — yozuv tashlanadi. Mintaqa so'zi bo'lsa (masalan
#  "Rossiya va O'zbekiston ...") yozuv qoladi.
#  Qisqa so'zlar o'ng chegara (\b) bilan — "usa" ≠ "usage"; o'zbekcha qisqartmalar chegarasiz
#  (qo'shimcha oladi: "AQSHda", "FQBning").
# =========================================================================
FOREIGN_MARKERS: tuple[str, ...] = (
    # rus
    r"сша\b", r"америк", r"фбр\b", r"цру\b", r"пентагон", r"росси", r"москв", r"кремл",
    r"кита[йяе]", r"кнр\b", r"кндр\b", r"северокоре", r"северн\w+ коре", r"южн\w+ коре",
    r"германи", r"немецк", r"великобритани", r"британ", r"франци", r"французск", r"украин",
    r"израил", r"иран", r"япони", r"инди[яию]\b", r"индийск", r"турци", r"турецк", r"европ",
    r"евросоюз", r"польш", r"итали", r"испани", r"канад", r"австрали", r"бразили",
    r"глобальн", r"миров\w+", r"во вс[её]м мире", r"по всему миру",
    # o'zbek (lotin)
    r"aqsh", r"amerika", r"fqb", r"rossiya", r"moskva", r"xitoy", r"kxdr",
    r"shimoliy koreya", r"janubiy koreya", r"germaniya", r"britaniya", r"fransiya", r"ukraina",
    r"isroil", r"eron(?:da|ga|ning|dan|lik|\b)", r"yaponiya", r"hindiston", r"turkiya", r"yevropa",
    r"global", r"butun dunyo", r"jahon\b", r"jahonda", r"jahon bo'ylab",
    # o'zbek (kirill) / qozoq
    r"ақш", r"фқб", r"хитой", r"кхдр", r"шимолий корея", r"жанубий корея", r"исроил",
    r"эрон(?:да|га|нинг|дан|лик|\b)", r"ҳиндистон", r"туркия", r"глобал", r"бутун дунё", r"жаҳон", r"ресей", r"қытай",
    # ingliz
    r"united states", r"u\.s\.", r"usa\b", r"american", r"fbi\b", r"cia\b", r"pentagon",
    r"russia", r"moscow", r"kremlin", r"china\b", r"chinese", r"north korea", r"south korea",
    r"german", r"britain", r"british", r"france", r"french", r"ukrain", r"israel", r"iran\b",
    r"iranian", r"japan", r"india\b", r"indian\b", r"europe", r"worldwide",
    # jahon miqyosidagi shaxs / kompaniyalar — mahalliy sayt qayta bosgan jahon yangiligi belgisi
    # ("Дуров предложил взломать его аккаунт", "Binance возместила ... при взломе").
    # Ataylab YO'Q: telegram, whatsapp, google, apple, microsoft — mahalliy firibgarlik va
    # zaiflik xabarlarida ham uchraydi.
    r"дуров", r"durov", r"binance", r"bybit", r"coinbase", r"илон\w* маск", r"маск\b", r"musk\b",
    r"openai", r"трамп", r"trump",
)
