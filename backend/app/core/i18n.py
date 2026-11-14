"""Backend matnlarini lokalizatsiya qilish: kichik katalog (uz — standart, ru, en).

- `lang_from_header` — Accept-Language (q-qiymatlar bilan) → "uz" | "ru" | "en".
- `t(code, lang, **params)` — katalogdan matn (`str.format` parametrlari bilan).
- `current_lang()` — joriy so'rov tili (contextvar; `LangMiddleware` o'rnatadi), chuqur kod
  (collectorlar) uchun: `t("c_email_syntax_src", current_lang())`.
Saqlangan natijalar o'zgarmaydi — faqat YANGI so'rovlar tanlangan tilda matn oladi.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

LANGS = ("uz", "ru", "en")
DEFAULT_LANG = "uz"

_lang_var: ContextVar[str] = ContextVar("osint_lang", default=DEFAULT_LANG)


def lang_from_header(accept_language: str | None) -> str:
    """'ru-RU,ru;q=0.9,en;q=0.8' → 'ru'. Qo'llab-quvvatlanmasa yoki bo'sh bo'lsa 'uz'."""
    if not accept_language:
        return DEFAULT_LANG
    ranked: list[tuple[float, int, str]] = []
    for i, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, *params = [p.strip() for p in piece.split(";")]
        q = 1.0
        for p in params:
            if p.lower().startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    q = 0.0
        primary = tag.lower().split("-", 1)[0]
        if q > 0 and primary in LANGS:
            ranked.append((-q, i, primary))
    return min(ranked)[2] if ranked else DEFAULT_LANG


def current_lang() -> str:
    return _lang_var.get()


def set_lang(lang: str) -> None:
    _lang_var.set(lang if lang in LANGS else DEFAULT_LANG)


class LangMiddleware:
    """Pure ASGI: har so'rovda Accept-Language'dan tilni contextvar'ga yozadi."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            raw = next((v for k, v in scope.get("headers", []) if k == b"accept-language"), b"")
            _lang_var.set(lang_from_header(raw.decode("latin-1")))
        await self.app(scope, receive, send)


async def request_lang() -> str:
    """FastAPI dependency: `lang: RequestLang`."""
    return current_lang()


try:  # FastAPI dependency turi (i18n.py fastapi'siz ham import qilinadi)
    from typing import Annotated

    from fastapi import Depends

    RequestLang = Annotated[str, Depends(request_lang)]
except ImportError:  # pragma: no cover
    pass


class CodedValueError(ValueError):
    """Kodli ValueError (collector so'rovi yaroqsiz). str(exc) — uz matni."""

    def __init__(self, code: str, **params: Any) -> None:
        self.code = code
        self.params = params
        super().__init__(t(code, DEFAULT_LANG, **params))


def t(code: str, lang: str | None = None, /, **params: Any) -> str:
    entry = MESSAGES.get(code)
    if entry is None:
        return code
    text = entry.get(lang or DEFAULT_LANG) or entry[DEFAULT_LANG]
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        return text


# fmt: off
MESSAGES: dict[str, dict[str, str]] = {
    "too_many_requests": {
        "uz": "So'rovlar juda ko'p. {seconds} soniyadan keyin qayta urinib ko'ring",
        "ru": "Слишком много запросов. Повторите через {seconds} с",
        "en": "Too many requests. Try again in {seconds} s"},
    # ------------------------------------------------------------ HTTP xatolar
    "not_authenticated": {
        "uz": "Autentifikatsiya talab qilinadi",
        "ru": "Требуется аутентификация",
        "en": "Authentication required"},
    "validation_error": {
        "uz": "So'rov ma'lumotlari noto'g'ri",
        "ru": "Некорректные данные запроса",
        "en": "Invalid request data"},
    "invalid_credentials": {
        "uz": "Email yoki parol noto'g'ri",
        "ru": "Неверный email или пароль",
        "en": "Incorrect email or password"},
    "email_taken": {
        "uz": "Bu email allaqachon ro'yxatdan o'tgan",
        "ru": "Этот email уже зарегистрирован",
        "en": "This email is already registered"},
    "registration_closed": {
        "uz": "Ro'yxatdan o'tish yopiq",
        "ru": "Регистрация закрыта",
        "en": "Registration is closed"},
    "account_disabled": {
        "uz": "Akkaunt o'chirilgan",
        "ru": "Аккаунт отключён",
        "en": "Account is disabled"},
    "invalid_token": {
        "uz": "Noto'g'ri yoki muddati o'tgan token",
        "ru": "Недействительный или просроченный токен",
        "en": "Invalid or expired token"},
    "admin_only": {
        "uz": "Bu amal faqat administrator uchun",
        "ru": "Это действие доступно только администратору",
        "en": "This action is for administrators only"},
    "search_not_found": {
        "uz": "Qidiruv topilmadi",
        "ru": "Поиск не найден",
        "en": "Search not found"},
    "invalid_query": {
        "uz": "{message}",
        "ru": "Некорректный запрос: {message}",
        "en": "Invalid query: {message}"},
    "event_not_found": {
        "uz": "Hodisa topilmadi",
        "ru": "Событие не найдено",
        "en": "Event not found"},
    "source_not_found": {
        "uz": "Manba topilmadi",
        "ru": "Источник не найден",
        "en": "Source not found"},
    "category_not_found": {
        "uz": "Kategoriya topilmadi",
        "ru": "Категория не найдена",
        "en": "Category not found"},
    "category_slug_not_found": {
        "uz": "Kategoriya topilmadi: {slug}",
        "ru": "Категория не найдена: {slug}",
        "en": "Category not found: {slug}"},
    "source_name_taken": {
        "uz": "Bu nomli manba bor",
        "ru": "Источник с таким названием уже существует",
        "en": "A source with this name already exists"},
    "slug_taken": {
        "uz": "Bu slug band",
        "ru": "Этот slug уже занят",
        "en": "This slug is already taken"},
    "source_kind_unknown": {
        "uz": "Noma'lum manba turi: {kind}",
        "ru": "Неизвестный тип источника: {kind}",
        "en": "Unknown source kind: {kind}"},
    "config_invalid": {
        "uz": "{message}",
        "ru": "Неверная конфигурация: {message}",
        "en": "Invalid configuration: {message}"},
    "category_other_protected": {
        "uz": "'other' — zaxira kategoriya, o'chirib bo'lmaydi",
        "ru": "'other' — резервная категория, её нельзя отключить",
        "en": "'other' is the fallback category and cannot be disabled"},
    "category_system_protected": {
        "uz": "Tizim kategoriyasini o'chirib bo'lmaydi — faqat disable",
        "ru": "Системную категорию нельзя удалить — только отключить",
        "en": "A system category cannot be deleted — only disabled"},
    "ids_invalid": {
        "uz": "Noma'lum yoki takroriy ID",
        "ru": "Неизвестные или повторяющиеся ID",
        "en": "Unknown or duplicate IDs"},
    "source_busy": {
        "uz": "Bu manba hozir yig'ilmoqda",
        "ru": "Этот источник сейчас обрабатывается",
        "en": "This source is being collected right now"},
    "telegram_not_configured": {
        "uz": "{message}",
        "ru": "Telegram не настроен: {message}",
        "en": "Telegram is not configured: {message}"},
    "tg_connected": {
        "uz": "Ulangan ✅",
        "ru": "Подключено ✅",
        "en": "Connected ✅"},
    "tg_env_missing": {
        "uz": "TG_API_ID / TG_API_HASH backend/.env da yo'q",
        "ru": "TG_API_ID / TG_API_HASH отсутствуют в backend/.env",
        "en": "TG_API_ID / TG_API_HASH are missing from backend/.env"},

    # ------------------------------------------------------------ so'rov (query) xatolari — collectorlar
    "invalid_username_query": {
        "uz": "Username faqat harf, raqam, '.', '_', '-' dan iborat bo'lishi kerak",
        "ru": "Username может содержать только буквы, цифры, '.', '_', '-'",
        "en": "Username may contain only letters, digits, '.', '_', '-'"},
    "invalid_telegram_query": {
        "uz": "Telegram username (@nom yoki t.me/nom: 4–32 belgi, lotin harf, raqam, _) yoki raqamli ID kiriting",
        "ru": "Введите Telegram username (@имя или t.me/имя: 4–32 символа, латиница, цифры, _) или числовой ID",
        "en": "Enter a Telegram username (@name or t.me/name: 4–32 chars, Latin letters, digits, _) or a numeric ID"},
    "domain_query_empty": {
        "uz": "Domen yoki IP manzil kiriting",
        "ru": "Введите домен или IP-адрес",
        "en": "Enter a domain or an IP address"},
    "domain_not_found": {
        "uz": "Domen yoki IP manzil topilmadi — to'g'ri qiymat kiriting",
        "ru": "Домен или IP-адрес не найден — введите корректное значение",
        "en": "No domain or IP address found — enter a valid value"},
    "invalid_ipv6": {
        "uz": "IPv6 manzil formati noto'g'ri",
        "ru": "Неверный формат IPv6-адреса",
        "en": "Invalid IPv6 address format"},
    "invalid_port": {
        "uz": "Port noto'g'ri — domen yoki IP manzil kiriting",
        "ru": "Неверный порт — введите домен или IP-адрес",
        "en": "Invalid port — enter a domain or an IP address"},
    "invalid_idna": {
        "uz": "Domen nomi noto'g'ri (IDNA/punycode xatosi)",
        "ru": "Неверное доменное имя (ошибка IDNA/punycode)",
        "en": "Invalid domain name (IDNA/punycode error)"},
    "invalid_domain": {
        "uz": "Yaroqsiz domen yoki IP manzil (masalan: example.uz yoki 8.8.8.8)",
        "ru": "Недопустимый домен или IP-адрес (например: example.uz или 8.8.8.8)",
        "en": "Invalid domain or IP address (for example: example.uz or 8.8.8.8)"},

    # ------------------------------------------------------------ email collector
    "c_email_syntax_src": {"uz": "Sintaksis", "ru": "Синтаксис", "en": "Syntax"},
    "c_email_syntax_ok": {
        "uz": "To'g'ri formatdagi email",
        "ru": "Email корректного формата",
        "en": "Email with a valid format"},
    "c_email_mx_src": {
        "uz": "MX (pochta serveri)", "ru": "MX (почтовый сервер)", "en": "MX (mail server)"},
    "c_email_mx_none": {
        "uz": "MX yozuvi topilmadi — domen email qabul qilmasligi mumkin",
        "ru": "MX-запись не найдена — домен, возможно, не принимает почту",
        "en": "No MX record found — the domain may not accept email"},
    "c_gravatar_yes": {
        "uz": "Gravatar avatari mavjud",
        "ru": "Аватар Gravatar существует",
        "en": "Gravatar avatar exists"},
    "c_gravatar_no": {
        "uz": "Gravatar topilmadi", "ru": "Gravatar не найден", "en": "Gravatar not found"},
    "c_gravatar_err": {
        "uz": "Gravatar'ga ulanib bo'lmadi",
        "ru": "Не удалось подключиться к Gravatar",
        "en": "Could not connect to Gravatar"},

    # ------------------------------------------------------------ phone collector
    "c_phone_parsing_src": {"uz": "Parsing", "ru": "Разбор номера", "en": "Parsing"},
    "c_phone_unparsable": {
        "uz": "Raqamni o'qib bo'lmadi: {error}. Xalqaro formatda kiriting, masalan +998901234567",
        "ru": "Не удалось разобрать номер: {error}. Введите в международном формате, например +998901234567",
        "en": "Could not parse the number: {error}. Enter it in international format, e.g. +998901234567"},
    "c_phone_valid_src": {"uz": "Yaroqlilik", "ru": "Валидность", "en": "Validity"},
    "c_phone_valid": {"uz": "Raqam yaroqli", "ru": "Номер действителен", "en": "The number is valid"},
    "c_phone_invalid": {
        "uz": "Raqam yaroqsiz ko'rinadi",
        "ru": "Номер выглядит недействительным",
        "en": "The number looks invalid"},
    "c_phone_format_src": {"uz": "Format", "ru": "Формат", "en": "Format"},
    "c_phone_intl": {"uz": "Xalqaro: {number}", "ru": "Международный: {number}", "en": "International: {number}"},
    "c_phone_region_src": {"uz": "Hudud", "ru": "Регион", "en": "Region"},
    "c_phone_region": {
        "uz": "Davlat/hudud: {country} (kod +{code})",
        "ru": "Страна/регион: {country} (код +{code})",
        "en": "Country/region: {country} (code +{code})"},
    "c_phone_carrier_src": {"uz": "Operator", "ru": "Оператор", "en": "Carrier"},
    "c_phone_carrier": {"uz": "Operator: {name}", "ru": "Оператор: {name}", "en": "Carrier: {name}"},
    "c_phone_type_src": {"uz": "Raqam turi", "ru": "Тип номера", "en": "Number type"},
    "c_phone_type": {"uz": "Tur: {label}", "ru": "Тип: {label}", "en": "Type: {label}"},
    "c_phone_tz_src": {"uz": "Vaqt mintaqasi", "ru": "Часовой пояс", "en": "Time zone"},
    "c_pt_mobile": {"uz": "Mobil", "ru": "Мобильный", "en": "Mobile"},
    "c_pt_fixed": {"uz": "Statsionar", "ru": "Стационарный", "en": "Fixed line"},
    "c_pt_fixed_or_mobile": {
        "uz": "Statsionar yoki mobil", "ru": "Стационарный или мобильный", "en": "Fixed line or mobile"},
    "c_pt_toll_free": {"uz": "Bepul (toll-free)", "ru": "Бесплатный (toll-free)", "en": "Toll-free"},
    "c_pt_voip": {"uz": "VoIP", "ru": "VoIP", "en": "VoIP"},
    "c_pt_premium": {"uz": "Premium", "ru": "Премиум", "en": "Premium"},
    "c_pt_unknown": {"uz": "Noma'lum", "ru": "Неизвестно", "en": "Unknown"},

    # ------------------------------------------------------------ domain / IP collector
    "c_dom_timeout": {"uz": "vaqt tugadi", "ru": "время истекло", "en": "timed out"},
    "c_dom_unreachable": {
        "uz": "manbaga ulanib bo'lmadi", "ru": "не удалось подключиться к источнику", "en": "could not reach the source"},
    "c_dom_check_failed": {
        "uz": "Tekshirib bo'lmadi: {msg}", "ru": "Не удалось проверить: {msg}", "en": "Check failed: {msg}"},
    "c_dom_expiry_src": {"uz": "Domen muddati", "ru": "Срок действия домена", "en": "Domain expiry"},
    "c_dom_expired": {
        "uz": "OGOHLANTIRISH: domen muddati {days} kun oldin tugagan ({date})",
        "ru": "ВНИМАНИЕ: срок действия домена истёк {days} дн. назад ({date})",
        "en": "WARNING: the domain expired {days} days ago ({date})"},
    "c_dom_expiring": {
        "uz": "OGOHLANTIRISH: muddati tugashiga {days} kun qoldi ({date})",
        "ru": "ВНИМАНИЕ: до истечения срока осталось {days} дн. ({date})",
        "en": "WARNING: {days} days left until expiry ({date})"},
    "c_dom_expires_in": {
        "uz": "Muddati tugashiga {days} kun qoldi ({date})",
        "ru": "До истечения срока осталось {days} дн. ({date})",
        "en": "{days} days left until expiry ({date})"},
    "c_dom_addr_none": {
        "uz": "A/AAAA yozuvi topilmadi — domen mavjud emas yoki IP manziliga ega emas",
        "ru": "A/AAAA-записи не найдены — домена не существует или у него нет IP-адреса",
        "en": "No A/AAAA records found — the domain does not exist or has no IP address"},
    "c_dom_ns_none": {
        "uz": "NS yozuvi topilmadi (domen mavjud emas yoki bu subdomen)",
        "ru": "NS-записи не найдены (домена не существует или это поддомен)",
        "en": "No NS records found (the domain does not exist or this is a subdomain)"},
    "c_dom_mx_none": {
        "uz": "MX yozuvi yo'q — domen pochta qabul qilmasligi mumkin",
        "ru": "MX-записи нет — домен, возможно, не принимает почту",
        "en": "No MX record — the domain may not accept mail"},
    "c_dom_mx_item": {
        "uz": "{host} (prioritet {priority})",
        "ru": "{host} (приоритет {priority})",
        "en": "{host} (priority {priority})"},
    "c_dom_spf_none": {
        "uz": "SPF yo'q — domen nomidan soxta xat yuborilishi osonroq",
        "ru": "SPF нет — подделать письмо от имени домена проще",
        "en": "No SPF — it is easier to spoof email from this domain"},
    "c_dom_dmarc_none": {
        "uz": "DMARC yo'q — domen nomidan soxta xat yuborish osonroq",
        "ru": "DMARC нет — подделать письмо от имени домена проще",
        "en": "No DMARC — it is easier to spoof email from this domain"},
    "c_dom_whois_no_server": {
        "uz": ".{tld} uchun RDAP ham, WHOIS serveri ham topilmadi",
        "ru": "Для .{tld} не найден ни RDAP, ни сервер WHOIS",
        "en": "No RDAP or WHOIS server found for .{tld}"},
    "c_dom_unregistered": {
        "uz": "Domen ro'yxatdan o'tmagan (WHOIS: topilmadi)",
        "ru": "Домен не зарегистрирован (WHOIS: не найден)",
        "en": "The domain is not registered (WHOIS: not found)"},
    "c_dom_registrar": {"uz": "Registrator: {v}", "ru": "Регистратор: {v}", "en": "Registrar: {v}"},
    "c_dom_created": {"uz": "Ro'yxatdan o'tgan: {v}", "ru": "Зарегистрирован: {v}", "en": "Registered: {v}"},
    "c_dom_expires": {"uz": "Tugaydi: {v}", "ru": "Истекает: {v}", "en": "Expires: {v}"},
    "c_dom_status": {"uz": "Holat: {v}", "ru": "Статус: {v}", "en": "Status: {v}"},
    "c_dom_info_found": {"uz": "Ma'lumot topildi", "ru": "Данные найдены", "en": "Data found"},
    "c_dom_subs_src": {"uz": "Subdomenlar (CT)", "ru": "Поддомены (CT)", "en": "Subdomains (CT)"},
    "c_dom_crt_http": {
        "uz": "crt.sh javob bermadi (HTTP {status})",
        "ru": "crt.sh не ответил (HTTP {status})",
        "en": "crt.sh did not respond (HTTP {status})"},
    "c_dom_crt_unreadable": {
        "uz": "crt.sh javobini o'qib bo'lmadi",
        "ru": "Не удалось прочитать ответ crt.sh",
        "en": "Could not read the crt.sh response"},
    "c_dom_subs_none": {
        "uz": "Sertifikat shaffofligi (CT) loglarida subdomen topilmadi",
        "ru": "В логах Certificate Transparency (CT) поддомены не найдены",
        "en": "No subdomains found in Certificate Transparency (CT) logs"},
    "c_dom_subs_count": {"uz": "{n} ta subdomen", "ru": "Поддоменов: {n}", "en": "{n} subdomains"},
    "c_dom_net_no_a": {
        "uz": "A yozuvi yo'q — hosting aniqlab bo'lmadi",
        "ru": "Нет A-записи — не удалось определить хостинг",
        "en": "No A record — could not identify the hosting"},
    "c_dom_net_no_asn": {
        "uz": "{ip} uchun ASN ma'lumoti topilmadi",
        "ru": "Данные ASN для {ip} не найдены",
        "en": "No ASN data found for {ip}"},
    "c_ip_kind_src": {"uz": "IP turi", "ru": "Тип IP", "en": "IP type"},
    "c_ip_unspecified": {"uz": "Aniqlanmagan", "ru": "Неопределённый", "en": "Unspecified"},
    "c_ip_private": {"uz": "Xususiy (ichki) tarmoq", "ru": "Частная (внутренняя) сеть", "en": "Private (internal) network"},
    "c_ip_reserved": {"uz": "Zaxiralangan", "ru": "Зарезервированный", "en": "Reserved"},
    "c_ip_nonglobal": {
        "uz": "Ochiq internetda marshrutlanmaydigan",
        "ru": "Не маршрутизируемый в открытом интернете",
        "en": "Not routable on the public internet"},
    "c_ip_kind_detail": {
        "uz": "{label} manzili — ochiq manbalarda ma'lumot yo'q",
        "ru": "Адрес типа «{label}» — в открытых источниках данных нет",
        "en": "{label} address — no data in open sources"},
    "c_ip_ptr_none": {
        "uz": "PTR yozuvi yo'q — teskari DNS nomi belgilanmagan",
        "ru": "PTR-записи нет — обратное DNS-имя не задано",
        "en": "No PTR record — no reverse DNS name is set"},
    "c_ip_asn_src": {"uz": "ASN / tarmoq", "ru": "ASN / сеть", "en": "ASN / network"},
    "c_ip_asn_none": {"uz": "ASN ma'lumoti topilmadi", "ru": "Данные ASN не найдены", "en": "No ASN data found"},
    "c_ip_rdap_src": {"uz": "RDAP tarmoq", "ru": "RDAP сеть", "en": "RDAP network"},
    "c_ip_rdap_404": {
        "uz": "RDAP'da tarmoq topilmadi", "ru": "Сеть в RDAP не найдена", "en": "Network not found in RDAP"},
    "c_ip_rdap_http": {
        "uz": "RDAP javob bermadi (HTTP {status})",
        "ru": "RDAP не ответил (HTTP {status})",
        "en": "RDAP did not respond (HTTP {status})"},
    "c_ip_rdap_name": {"uz": "Tarmoq: {v}", "ru": "Сеть: {v}", "en": "Network: {v}"},
    "c_ip_rdap_range": {"uz": "Diapazon: {v}", "ru": "Диапазон: {v}", "en": "Range: {v}"},
    "c_ip_rdap_country": {"uz": "Davlat: {v}", "ru": "Страна: {v}", "en": "Country: {v}"},
    "c_ip_rdap_org": {"uz": "Tashkilot: {v}", "ru": "Организация: {v}", "en": "Organization: {v}"},
    "c_ip_rdap_empty": {
        "uz": "RDAP'da foydali ma'lumot yo'q",
        "ru": "В RDAP нет полезных данных",
        "en": "No useful data in RDAP"},

    # ------------------------------------------------------------ Telegram account collector
    "tg_months": {
        "uz": "yan,fev,mar,apr,may,iyun,iyul,avg,sen,okt,noy,dek",
        "ru": "янв,фев,мар,апр,мая,июн,июл,авг,сен,окт,ноя,дек",
        "en": "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec"},
    "tg_kind_user": {"uz": "foydalanuvchi", "ru": "пользователь", "en": "user"},
    "tg_kind_bot": {"uz": "bot", "ru": "бот", "en": "bot"},
    "tg_kind_channel": {"uz": "kanal", "ru": "канал", "en": "channel"},
    "tg_kind_group": {"uz": "guruh", "ru": "группа", "en": "group"},
    "tg_src_account": {"uz": "Telegram akkaunt", "ru": "Аккаунт Telegram", "en": "Telegram account"},
    "tg_not_connected": {
        "uz": "Telegram akkaunti ulanmagan: {error}",
        "ru": "Аккаунт Telegram не подключён: {error}",
        "en": "Telegram account is not connected: {error}"},
    "tg_flood": {
        "uz": "Telegram so'rovlarni vaqtincha chekladi — {seconds} soniyadan keyin urinib ko'ring.",
        "ru": "Telegram временно ограничил запросы — повторите через {seconds} с.",
        "en": "Telegram has temporarily rate-limited requests — try again in {seconds} s."},
    "tg_username_free": {
        "uz": "Bu username hozir hech kimga tegishli emas (bo'sh yoki o'zgartirilgan).",
        "ru": "Этот username сейчас никому не принадлежит (свободен или изменён).",
        "en": "This username currently belongs to no one (free or changed)."},
    "tg_src_moved": {
        "uz": "Username boshqa akkauntda", "ru": "Username у другого аккаунта", "en": "Username on another account"},
    "tg_moved_detail": {
        "uz": "ID {id} avval @{name} bilan ko'rilgan edi; hozir bu username boshqa akkauntga (ID {new_id}) tegishli — egasi usernameni o'zgartirgan.",
        "ru": "ID {id} ранее был замечен с @{name}; сейчас этот username принадлежит другому аккаунту (ID {new_id}) — владелец сменил username.",
        "en": "ID {id} was previously seen as @{name}; this username now belongs to another account (ID {new_id}) — the owner changed their username."},
    "tg_id_unresolved": {
        "uz": "Bu ID'ni ochib bo'lmadi. Telegram ID bo'yicha faqat akkauntingiz avval ko'rgan (umumiy guruhda uchragan yoki username orqali qidirilgan) akkauntlarni ochadi. Username bilan bir marta qidiring — keyin ID ishlaydi.",
        "ru": "Не удалось открыть этот ID. По ID Telegram открывает только аккаунты, которые ваш аккаунт уже видел (встречался в общей группе или искался по username). Найдите его один раз по username — после этого ID заработает.",
        "en": "This ID could not be opened. Telegram resolves an ID only for accounts your account has already seen (met in a shared group or looked up by username). Search once by username — then the ID will work."},
    "tg_flag_deleted": {"uz": "o'chirilgan akkaunt", "ru": "удалённый аккаунт", "en": "deleted account"},
    "tg_flag_verified": {"uz": "tasdiqlangan", "ru": "подтверждён", "en": "verified"},
    "tg_flag_premium": {"uz": "Premium", "ru": "Premium", "en": "Premium"},
    "tg_flag_scam": {"uz": "SCAM belgisi", "ru": "метка SCAM", "en": "SCAM flag"},
    "tg_flag_fake": {"uz": "FAKE belgisi", "ru": "метка FAKE", "en": "FAKE flag"},
    "tg_flag_restricted": {"uz": "cheklangan", "ru": "ограничен", "en": "restricted"},
    "tg_flag_contact": {"uz": "kontaktlaringizda", "ru": "в ваших контактах", "en": "in your contacts"},
    "tg_detail_user": {
        "uz": "Tur: {kind} · Ism: {name}", "ru": "Тип: {kind} · Имя: {name}", "en": "Type: {kind} · Name: {name}"},
    "tg_detail_chat": {
        "uz": "Tur: {kind} · Nomi: {name}", "ru": "Тип: {kind} · Название: {name}", "en": "Type: {kind} · Title: {name}"},
    "tg_members": {"uz": "a'zolar: {n}", "ru": "участников: {n}", "en": "members: {n}"},
    "tg_src_username": {"uz": "Username", "ru": "Username", "en": "Username"},
    "tg_no_username": {"uz": "Username yo'q", "ru": "Username нет", "en": "No username"},
    "tg_active_usernames": {
        "uz": "Faol usernamelar: {n}", "ru": "Активных username: {n}", "en": "Active usernames: {n}"},
    "tg_no_public_username": {
        "uz": "Akkauntda hozir ochiq username yo'q (o'chirilgan yoki umuman qo'yilmagan).",
        "ru": "У аккаунта сейчас нет публичного username (удалён или не задавался).",
        "en": "The account has no public username right now (removed or never set)."},
    "tg_src_bio": {"uz": "Bio", "ru": "Bio", "en": "Bio"},
    "tg_src_about": {"uz": "Tavsif", "ru": "Описание", "en": "Description"},
    "tg_src_personal_channel": {"uz": "Shaxsiy kanal", "ru": "Личный канал", "en": "Personal channel"},
    "tg_personal_channel_detail": {
        "uz": "ID {id} · profilida ko'rsatilgan kanal",
        "ru": "ID {id} · канал, указанный в профиле",
        "en": "ID {id} · channel shown on the profile"},
    "tg_src_prev_owner": {
        "uz": "Username avvalgi egasi", "ru": "Прежний владелец username", "en": "Previous owner of username"},
    "tg_prev_owner_detail": {
        "uz": "@{name} {first} – {last} oralig'ida boshqa akkauntda (ID {id}) ko'rilgan.",
        "ru": "@{name} в период {first} – {last} был замечен у другого аккаунта (ID {id}).",
        "en": "@{name} was seen on another account (ID {id}) between {first} and {last}."},
    "tg_orphan_detail": {
        "uz": "@{name} {first} – {last} oralig'ida ID {id} akkauntida ko'rilgan. Shu ID bo'yicha qidirsangiz, joriy usernamesi chiqadi.",
        "ru": "@{name} в период {first} – {last} был замечен у аккаунта ID {id}. Если поискать по этому ID, появится его текущий username.",
        "en": "@{name} was seen on account ID {id} between {first} and {last}. Search by that ID to see its current username."},
    "tg_src_history": {"uz": "Username tarixi", "ru": "История username", "en": "Username history"},
    "tg_hist_none_value": {
        "uz": "O'zgarish qayd etilmagan", "ru": "Изменений не зафиксировано", "en": "No changes recorded"},
    "tg_hist_none_detail": {
        "uz": "Kuzatuv boshlangan: {since}. Telegram o'tgan o'zgarishlarni bermaydi — platforma har qidiruvda holatni yozib boradi; username o'zgarsa, keyingi qidiruvda (ID bo'yicha ham) shu yerda chiqadi.",
        "ru": "Наблюдение начато: {since}. Telegram не отдаёт прошлые изменения — платформа записывает состояние при каждом поиске; если username изменится, при следующем поиске (в том числе по ID) это появится здесь.",
        "en": "Tracking started: {since}. Telegram does not provide past changes — the platform records the state on every search; if the username changes, it will show up here on the next search (including by ID)."},
    "tg_hist_step": {
        "uz": "{prev} → {cur}: {a} va {b} oralig'ida",
        "ru": "{prev} → {cur}: между {a} и {b}",
        "en": "{prev} → {cur}: between {a} and {b}"},
    "tg_hist_count": {"uz": "{n} ta o'zgarish", "ru": "Изменений: {n}", "en": "{n} changes"},
    "tg_hist_since": {
        "uz": "Kuzatuv boshlangan: {since} ({names})",
        "ru": "Наблюдение начато: {since} ({names})",
        "en": "Tracking started: {since} ({names})"},
    "tg_hist_no_username": {"uz": "username yo'q", "ru": "username нет", "en": "no username"},
    "tg_src_common": {"uz": "Umumiy guruhlar", "ru": "Общие группы", "en": "Common groups"},
    "tg_not_checked": {"uz": "Tekshirilmadi", "ru": "Не проверено", "en": "Not checked"},
    "tg_rpc_error": {"uz": "Telegram xatosi: {name}", "ru": "Ошибка Telegram: {name}", "en": "Telegram error: {name}"},
    "tg_common_none_value": {"uz": "Yo'q", "ru": "Нет", "en": "None"},
    "tg_common_none_detail": {
        "uz": "Sizning Telegram akkauntingiz a'zo bo'lgan guruhlarning hech birida bu akkaunt yo'q. Telegram faqat umumiy guruhlarni ko'rsatadi — boshqa guruhlari ko'rinmaydi.",
        "ru": "Этого аккаунта нет ни в одной из групп, в которых состоит ваш аккаунт Telegram. Telegram показывает только общие группы — остальные его группы не видны.",
        "en": "This account is not in any group your Telegram account belongs to. Telegram only shows common groups — its other groups are not visible."},
    "tg_common_group": {"uz": "Umumiy guruh", "ru": "Общая группа", "en": "Common group"},
    "tg_public": {"uz": " (ochiq)", "ru": " (публичная)", "en": " (public)"},
    "tg_private": {"uz": " (yopiq)", "ru": " (закрытая)", "en": " (private)"},
    "tg_group_src": {"uz": "Guruh: {title}", "ru": "Группа: {title}", "en": "Group: {title}"},
    "tg_act_none": {
        "uz": "bu akkauntdan xabar topilmadi", "ru": "сообщений от этого аккаунта не найдено",
        "en": "no messages from this account found"},
    "tg_act_counts": {
        "uz": "xabarlar: {total} (birinchi: {first}, oxirgi: {last})",
        "ru": "сообщений: {total} (первое: {first}, последнее: {last})",
        "en": "messages: {total} (first: {first}, last: {last})"},
    "tg_act_flood": {
        "uz": "xabarlar sanalmadi (Telegram cheklovi, {seconds} s)",
        "ru": "сообщения не подсчитаны (ограничение Telegram, {seconds} с)",
        "en": "messages not counted (Telegram rate limit, {seconds} s)"},
    "tg_act_denied": {
        "uz": "xabarlar sanalmadi (ruxsat yo'q)", "ru": "сообщения не подсчитаны (нет доступа)",
        "en": "messages not counted (no access)"},

    # ------------------------------------------------------------ Telegram "Saved Messages" ogohlantirishi
    "alert_header": {
        "uz": "🚨 OSINT: Markaziy Osiyo bo'yicha {n} ta yangi hodisa",
        "ru": "🚨 OSINT: новых событий по Центральной Азии: {n}",
        "en": "🚨 OSINT: {n} new events for Central Asia"},
    "alert_more": {
        "uz": "... va yana {n} ta. Platformada ko'ring.",
        "ru": "... и ещё {n}. Смотрите на платформе.",
        "en": "... and {n} more. See them on the platform."},
    "user_not_found": {
        "uz": "Foydalanuvchi topilmadi",
        "ru": "Пользователь не найден",
        "en": "User not found"},
    "last_admin": {
        "uz": "Oxirgi faol administratorni o'zgartirib yoki o'chirib bo'lmaydi",
        "ru": "Нельзя изменить или отключить последнего активного администратора",
        "en": "The last active administrator cannot be demoted or deactivated"},
    "alert_not_found": {
        "uz": "Ogohlantirish topilmadi",
        "ru": "Уведомление не найдено",
        "en": "Alert not found"},
}
# fmt: on
