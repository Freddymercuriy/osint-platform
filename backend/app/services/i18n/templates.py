"""Tuzilgan elementlar sarlavhalari (mashina tarjimasiz, uch tilda) — `extra.template` bo'yicha."""

from __future__ import annotations

from typing import Any

COUNTRY = {
    "UZ": {"en": "Uzbekistan", "ru": "Узбекистан", "uz": "O'zbekiston"},
    "KZ": {"en": "Kazakhstan", "ru": "Казахстан", "uz": "Qozog'iston"},
    "KG": {"en": "Kyrgyzstan", "ru": "Кыргызстан", "uz": "Qirg'iziston"},
    "TJ": {"en": "Tajikistan", "ru": "Таджикистан", "uz": "Tojikiston"},
    "TM": {"en": "Turkmenistan", "ru": "Туркменистан", "uz": "Turkmaniston"},
}

IOC = {
    "url": {"en": "Malicious URL", "ru": "Вредоносный URL", "uz": "Zararli URL"},
    "domain": {"en": "Malicious domain", "ru": "Вредоносный домен", "uz": "Zararli domen"},
    "ip": {"en": "Malicious IP address", "ru": "Вредоносный IP-адрес", "uz": "Zararli IP manzil"},
}
PHISH = {"en": "Phishing URL", "ru": "Фишинговый URL", "uz": "Fishing URL"}


def _num(n: Any, lang: str) -> str:
    try:
        v = int(n)
    except (TypeError, ValueError):
        return str(n or "?")
    s = f"{v:,}"
    return s.replace(",", " ") if lang in ("ru", "uz") else s


def _country(code: str | None, lang: str) -> str:
    if not code:
        return ""
    return COUNTRY.get(code.upper(), {}).get(lang, code.upper())


def render_title(extra: dict[str, Any], countries: list[str], category: str | None) -> dict[str, str] | None:
    """{en, ru, uz} sarlavhalar yoki None (shablon yo'q / ma'lumot yetarli emas)."""
    kind = (extra or {}).get("template")
    c = (countries or [None])[0]
    if kind == "ransomware_victim":
        victim, group = extra.get("victim") or "?", extra.get("group") or "?"
        return {
            "en": f"Ransomware: {victim}" + (f" ({_country(c, 'en')})" if c else "") + f" — listed by {group}",
            "ru": f"Вымогатели: {victim}" + (f" ({_country(c, 'ru')})" if c else "") + f" — группа {group}",
            "uz": f"Ransomware: {victim}" + (f" ({_country(c, 'uz')})" if c else "") + f" — {group} guruhi",
        }
    if kind == "cve":
        cve = extra.get("cve_id") or "CVE"
        what = " ".join(x for x in (extra.get("vendor"), extra.get("product")) if x) or "?"
        if extra.get("kev"):
            return {"en": f"{cve}: actively exploited vulnerability in {what}",
                    "ru": f"{cve}: эксплуатируемая уязвимость в {what}",
                    "uz": f"{cve}: {what} da faol ishlatilayotgan zaiflik"}
        return {"en": f"{cve}: critical vulnerability in {what}",
                "ru": f"{cve}: критическая уязвимость в {what}",
                "uz": f"{cve}: {what} da kritik zaiflik"}
    if kind == "breach":
        name = extra.get("breach_name") or "?"
        n = extra.get("pwn_count")
        return {"en": f"{name}: {_num(n, 'en')} accounts breached",
                "ru": f"{name}: утечка {_num(n, 'ru')} учётных записей",
                "uz": f"{name}: {_num(n, 'uz')} ta akkaunt ma'lumotlari sizib chiqqan"}
    if kind == "indicator":
        host = extra.get("host") or "?"
        threat = extra.get("threat")
        labels = PHISH if category == "phishing" else IOC.get(extra.get("ioc_type") or "url", IOC["url"])
        tail = f" ({threat})" if threat else ""
        return {"en": f"{labels['en']} on {host}{tail}", "ru": f"{labels['ru']} на {host}{tail}",
                "uz": f"{host} da {labels['uz'].lower()}{tail}"}
    if kind == "outage":
        code = extra.get("country") or c
        return {"en": f"Internet outage in {_country(code, 'en')}",
                "ru": f"Сбой интернета: {_country(code, 'ru')}",
                "uz": f"Internet uzilishi: {_country(code, 'uz')}"}
    return None
