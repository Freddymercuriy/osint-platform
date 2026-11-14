from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Feed:
    """Bitta Events manbasi.

    kind:
      - "rss"             — oddiy RSS/Atom feed (url = feed manzili)
      - "telegram"        — ochiq Telegram kanal (url = kanal nomi, masalan "kunuzofficial")
      - "telegram_user"   — foydalanuvchi akkaunti orqali Telegram
      - "ransomware_live" — ransomware.live API (url = davlat kodlari, vergul bilan:
                            "UZ,KZ,KG,TJ,TM"); bitta /v2/recentvictims so'rovi
      - "google_news"     — Google News RSS qidiruvi (url = qidiruv so'rovi, masalan
                            'site:example.com (Uzbekistan OR Kazakhstan) when:7d').
                            Bot-himoyasi tufayli to'g'ridan-to'g'ri o'qib bo'lmaydigan saytlar
                            uchun: saytning o'ziga murojaat qilinmaydi, faqat Google indeksidagi
                            sarlavha + havola olinadi. Google maqolaning to'liq matni bo'yicha
                            qidiradi, shuning uchun so'rovdagi shart sarlavhada ko'rinmasligi mumkin.

    Filtrlar (title + summary bo'yicha):
      region_filter: True bo'lsa, faqat Markaziy Osiyo (UZ/KZ/KG/TJ/TM) kalit so'zlari
                     uchraganlari qoladi. Xalqaro kiber-saytlar uchun (mavzu manbadan ma'lum).
      cyber_filter:  True bo'lsa, faqat kiberxavfsizlik / data leak mavzusidagilar qoladi.
                     Mahalliy umumiy yangilik saytlari uchun (hudud manbadan ma'lum).
      Ikkalasi ham True bo'lsa — ikkala shart ham bajarilishi kerak.
      Faqat cyber_filter (mahalliy sayt) bo'lsa, qo'shimcha qoida: matnda chet el belgisi
      (FOREIGN_MARKERS: AQSH, FQB, KXDR, "global" ...) bo'lib, Markaziy Osiyo so'zi umuman
      uchramasa — yozuv tashlanadi (mahalliy sayt qayta bosgan jahon yangiligi).
    """

    name: str
    url: str
    kind: str = "rss"
    lang: str = "uz"
    category: str = "news"  # "news" | "ransomware" | "telegram" | "tg_group" | "leak"
    region_filter: bool = False
    cyber_filter: bool = False
    ttl: int = 600  # kesh muddati (soniya)
    min_interval: int = 0  # fon yig'uvchi (force) ham shundan tez-tez so'ramaydi (soniya)
    enabled: bool = True

    @property
    def uz_filter(self) -> bool:
        """Eski nom (orqaga moslik): endi region_filter bilan bir xil."""
        return self.region_filter


# =========================================================================
#  HUDUD kalit so'zlari — Markaziy Osiyo: UZ, KZ, KG, TJ, TM (kichik harfda).
#  Aggregator'dagi _kw_regex bo'yicha: o'zak (prefiks) — chap chegara bilan:
#  "uzbek" → "uzbekistan" ga mos, "xuzbek" ga emas.  "'" belgisi har xil
#  apostroflarga (' ‘ ’ ʻ ʼ `) va ularning yo'qligiga mos keladi.
#  ".uz" kabi domenlar — domen oxiri sifatida (davomi bo'lmasligi kerak).
#  Ataylab TASHLANGAN (yolg'on mos kelish): "osh", "semey", "kaspi" (Каспий),
#  "karshi", "talas", "naryn", "mary", "petropavl".
# =========================================================================
REGION_KEYWORDS: tuple[str, ...] = (
    # --- O'zbekiston ---
    "uzbek", "o'zbek", "узбек", "ўзбек", "ӯзбек",
    "tashkent", "toshkent", "ташкент", "тошкент",
    "samarkand", "samarqand", "самарканд", "самарқанд",
    "bukhara", "buxoro", "бухара", "бухоро",
    "andijan", "andijon", "андижан", "андижон",
    "namangan", "наманган", "fergana", "ferghana", "farg'ona", "фергана", "фарғона",
    "nukus", "нукус", "urgench", "urganch", "ургенч", "termez", "termiz", "термез",
    "kokand", "qo'qon", "коканд", "qoraqalpoq", "karakalpak", "каракалпак",
    "khorezm", "xorazm", "хорезм",
    # --- Qozog'iston ---
    "kazakh", "kazakstan", "kazahstan", "qozoq", "qozog'", "қозоқ", "қозоғ",
    "казах", "қазақ", "astana", "астана", "nur-sultan", "нур-султан",
    "almaty", "алматы", "алма-ата", "shymkent", "шымкент", "chimkent", "чимкент",
    "karaganda", "караганд", "қарағанды", "aktobe", "актобе", "ақтөбе",
    "atyrau", "атырау", "aktau", "актау", "pavlodar", "павлодар",
    "kostanay", "костанай", "kyzylorda", "кызылорда", "oskemen", "усть-каменогорск",
    # --- Qirg'iziston ---
    "kyrgyz", "kirghiz", "kirgiz", "qirg'iz", "киргиз", "кыргыз", "қирғиз", "қырғыз",
    "bishkek", "бишкек", "jalal-abad", "джалал-абад",
    # --- Tojikiston ---
    "tajik", "tadjik", "tojik", "таджик", "тоҷик", "тожик", "тоҷик",
    "dushanbe", "душанбе", "khujand", "xo'jand", "худжанд", "хуҷанд", "khatlon", "хатлон",
    # --- Turkmaniston ---
    "turkmen", "turkman", "туркмен", "ashgabat", "ashkhabad", "ashgabad",
    "ашхабад", "ашгабат", "turkmenbashi", "dashoguz", "дашогуз",
    # --- Butun mintaqa ---
    "central asia", "centralasia", "markaziy osiyo", "o'rta osiyo", "марказий осиё",
    "орталық азия", "центральная ази", "центральной ази", "центральную ази",
    "центральной азией", "центральноазиат", "средняя ази", "средней ази",
    "среднюю ази", "средней азией",
    # --- Milliy domenlar ---
    ".uz", ".kz", ".kg", ".tj", ".tm",
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
#  Regex ichida "'" — ixtiyoriy apostrof (aggregator moslashtiradi).
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


# =========================================================================
#  MANBALAR. Yangi manba = bitta qator.
#  Faqat ochiq (login'siz) manbalar. Cloudflare/captcha/login chetlab o'tilmaydi.
#  (BleepingComputer, CyberNews, CISA, The Cyber Express — 403 berdi, qo'shilmagan.)
# =========================================================================
_INTL = 900  # xalqaro kiber-saytlar ttl

# Google News so'rovlari uchun mintaqa / mavzu shartlari
_GN_EVERY = 1800  # Google News'ni 30 daqiqada bir martadan ko'p so'ramaymiz
_CA_EN = '(Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia")'
_CA_RU = "(Узбекистан OR Казахстан OR Кыргызстан OR Таджикистан OR Туркменистан)"
_CYBER_EN = ('(hackers OR cyberattack OR ransomware OR "data breach" OR "data leak" OR phishing '
             "OR malware)")
_CYBER_RU = ('(хакеры OR кибератака OR "утечка данных" OR взлом OR фишинг OR кибербезопасность)')

FEEDS: list[Feed] = [
    # --- Threat intel: bitta /v2/recentvictims so'rovi, 5 davlat bo'yicha filtr ---
    Feed("ransomware.live", "UZ,KZ,KG,TJ,TM", kind="ransomware_live", lang="en",
         category="ransomware", ttl=900),

    # --- O'zbekiston: yangilik (mavzu filtri) ---
    Feed("Gazeta.uz (UZ)", "https://www.gazeta.uz/uz/rss/", lang="uz", cyber_filter=True),
    Feed("Gazeta.uz (RU)", "https://www.gazeta.uz/ru/rss/", lang="ru", cyber_filter=True),
    Feed("Kun.uz (UZ)", "https://kun.uz/uz/news/rss", lang="uz", cyber_filter=True),
    Feed("Kun.uz (RU)", "https://kun.uz/ru/news/rss", lang="ru", cyber_filter=True),
    Feed("Spot.uz (RU)", "https://www.spot.uz/ru/rss/", lang="ru", cyber_filter=True),
    Feed("Spot.uz (UZ)", "https://www.spot.uz/rss/", lang="uz", cyber_filter=True),
    Feed("Daryo.uz (UZ)", "https://daryo.uz/feed/", lang="uz", cyber_filter=True),
    Feed("Daryo.uz (RU)", "https://daryo.uz/ru/feed/", lang="ru", cyber_filter=True),
    Feed("UzDaily (EN)", "https://uzdaily.uz/en/rss", lang="en", cyber_filter=True),
    Feed("UzDaily (RU)", "https://uzdaily.uz/ru/rss", lang="ru", cyber_filter=True),
    Feed("Nuz.uz", "https://nuz.uz/feed/", lang="ru", cyber_filter=True),
    # UZCERT — o'zi kiber manba, filtrsiz
    Feed("UZCERT", "https://uzcert.uz/rss", lang="uz"),

    # --- Qozog'iston ---
    Feed("Tengrinews.kz", "https://tengrinews.kz/news.rss", lang="ru", cyber_filter=True),
    Feed("Kursiv.media (KZ)", "https://kz.kursiv.media/feed/", lang="ru", cyber_filter=True),
    Feed("Profit.kz", "https://profit.kz/rss/", lang="ru", cyber_filter=True),
    Feed("DigitalBusiness.kz", "https://digitalbusiness.kz/feed/", lang="ru",
         cyber_filter=True),
    Feed("Sputnik Казахстан", "https://sputnik.kz/export/rss2/archive/index.xml", lang="ru",
         cyber_filter=True),

    # --- Qirg'iziston ---
    Feed("24.kg", "https://24.kg/rss/", lang="ru", cyber_filter=True),
    Feed("Kaktus.media", "https://kaktus.media/?rss", lang="ru", cyber_filter=True),
    Feed("AKIpress", "https://akipress.com/rss/news.rss", lang="en", cyber_filter=True),
    Feed("Kloop.kg", "https://kloop.kg/feed/", lang="ru", cyber_filter=True),
    Feed("Kabar.kg", "https://kabar.kg/rss/", lang="ru", cyber_filter=True),
    Feed("Sputnik Кыргызстан", "https://ru.sputnik.kg/export/rss2/archive/index.xml",
         lang="ru", cyber_filter=True),

    # --- Tojikiston ---
    Feed("Asia-Plus (RU)", "https://asiaplustj.info/ru/rss", lang="ru", cyber_filter=True),
    Feed("Asia-Plus (EN)", "https://asiaplustj.info/en/rss", lang="en", cyber_filter=True),
    Feed("Sputnik Таджикистан", "https://tj.sputniknews.ru/export/rss2/archive/index.xml",
         lang="ru", cyber_filter=True),

    # --- Turkmaniston ---
    Feed("Turkmen.news", "https://turkmen.news/feed/", lang="ru", cyber_filter=True),
    Feed("Хроника Туркменистана", "https://www.hronikatm.com/feed/", lang="ru",
         cyber_filter=True),

    # --- Butun mintaqa ---
    Feed("CentralAsia.media", "https://centralasia.media/rss", lang="ru", cyber_filter=True),

    # --- Xalqaro kiberxavfsizlik (hudud filtri) ---
    Feed("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("SecurityWeek", "https://www.securityweek.com/feed/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("The Record", "https://therecord.media/feed", lang="en", region_filter=True, ttl=_INTL),
    Feed("DataBreaches.net", "https://databreaches.net/feed/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Securelist", "https://securelist.com/feed", lang="en", region_filter=True, ttl=_INTL),
    Feed("Securelist (RU)", "https://securelist.ru/feed/", lang="ru",
         region_filter=True, ttl=_INTL),
    Feed("Security Affairs", "https://securityaffairs.com/feed", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("HackRead", "https://hackread.com/feed/", lang="en", region_filter=True, ttl=_INTL),
    Feed("Krebs on Security", "https://krebsonsecurity.com/feed/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Dark Reading", "https://www.darkreading.com/rss.xml", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Help Net Security", "https://www.helpnetsecurity.com/feed/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Infosecurity Magazine", "https://www.infosecurity-magazine.com/rss/news/",
         lang="en", region_filter=True, ttl=_INTL),
    Feed("The Register (Security)", "https://www.theregister.com/security/headlines.atom",
         lang="en", region_filter=True, ttl=_INTL),
    Feed("CyberScoop", "https://cyberscoop.com/feed/", lang="en", region_filter=True,
         ttl=_INTL),
    Feed("WeLiveSecurity (ESET)", "https://www.welivesecurity.com/en/rss/feed/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Cisco Talos", "https://blog.talosintelligence.com/rss/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Bitdefender Labs", "https://www.bitdefender.com/blog/api/rss/labs/", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("Malwarebytes", "https://www.malwarebytes.com/blog/feed/index.xml", lang="en",
         region_filter=True, ttl=_INTL),
    Feed("SANS ISC", "https://isc.sans.edu/rssfeed.xml", lang="en", region_filter=True,
         ttl=_INTL),
    # Rus tilidagi kiber-saytlar
    Feed("Xakep.ru", "https://xakep.ru/feed/", lang="ru", region_filter=True, ttl=_INTL),
    Feed("SecurityLab.ru", "https://www.securitylab.ru/_services/export/rss/", lang="ru",
         region_filter=True, ttl=_INTL),
    Feed("Anti-Malware.ru", "https://www.anti-malware.ru/news/feed", lang="ru",
         region_filter=True, ttl=_INTL),
    Feed("Habr: Информационная безопасность", "https://habr.com/ru/rss/hub/infosecurity/all/",
         lang="ru", region_filter=True, ttl=_INTL),
    Feed("Kaspersky Daily (RU)", "https://www.kaspersky.ru/blog/feed/", lang="ru",
         region_filter=True, ttl=_INTL),

    # --- Google News RSS orqali (saytning o'zi 403/Cloudflare beradi — unga murojaat qilinmaydi) ---
    # Kiber-saytlar: mintaqa sharti so'rovning o'zida (Google to'liq matn bo'yicha qidiradi) → filtrsiz.
    Feed("BleepingComputer", f"site:bleepingcomputer.com {_CA_EN} when:7d", kind="google_news",
         lang="en", min_interval=_GN_EVERY),
    Feed("CyberNews", f"site:cybernews.com {_CA_EN} when:7d", kind="google_news",
         lang="en", min_interval=_GN_EVERY),
    Feed("The Cyber Express", f"site:thecyberexpress.com {_CA_EN} when:7d", kind="google_news",
         lang="en", min_interval=_GN_EVERY),
    # Mahalliy sayt: mavzu sharti so'rovda + sarlavha bo'yicha mavzu filtri
    Feed("Turkmenportal", f"site:turkmenportal.com {_CYBER_RU} when:7d", kind="google_news",
         lang="ru", cyber_filter=True, min_interval=_GN_EVERY),
    # Umumiy qidiruv: istalgan nashr (Reuters, The Record ...) — mintaqa so'rovda, mavzu sarlavhada
    Feed("Google News (EN)", f"{_CA_EN} {_CYBER_EN} when:7d", kind="google_news",
         lang="en", cyber_filter=True, min_interval=_GN_EVERY),
    Feed("Google News (RU)", f"{_CA_RU} {_CYBER_RU} when:7d", kind="google_news",
         lang="ru", cyber_filter=True, min_interval=_GN_EVERY),

    # --- Leak kuzatuvchilar: forumlarning o'zi emas, ular haqidagi ochiq xulosa (faqat metadata) ---
    Feed("Dark Web Informer", "https://darkwebinformer.com/rss/", lang="en", category="leak",
         region_filter=True, ttl=_INTL),
    Feed("Have I Been Pwned", "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
         lang="en", category="leak", region_filter=True, ttl=_INTL),

    # --- Telegram: o'z akkauntingiz orqali (a'zo bo'lgan kanal/guruhlar) ---
    # Sozlash: backend/.env → TG_API_ID, TG_API_HASH, TG_CHATS ...; login: scripts/tg_login.py
    # TG_UZ_FILTER=true bo'lsa — Markaziy Osiyo (5 davlat) kalit so'zlari filtri.
    Feed("Telegram (akkaunt)", "", kind="telegram_user", category="telegram", ttl=300),

    # --- Telegram ochiq kanallar (login'siz, t.me/s) ---
    # Na'muna: Feed("Kanal nomi", "kanal_username", kind="telegram",
    #               category="telegram", region_filter=True),
]


def enabled_feeds() -> list[Feed]:
    return [f for f in FEEDS if f.enabled]
