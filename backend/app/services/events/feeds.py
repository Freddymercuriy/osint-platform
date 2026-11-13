from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Feed:
    """Bitta Events manbasi.

    kind:
      - "rss"             — oddiy RSS/Atom feed (url = feed manzili)
      - "telegram"        — ochiq Telegram kanal (url = kanal nomi, masalan "kunuzofficial")
      - "ransomware_live" — ransomware.live API (url = davlat kodi, masalan "UZ")
    uz_filter: True bo'lsa, faqat O'zbekistonga oid kalit so'zli postlar qoldiriladi
               (umumiy leak/threat kanallari uchun).
    """

    name: str
    url: str
    kind: str = "rss"
    lang: str = "uz"
    category: str = "news"  # "news" | "ransomware" | "telegram" | "leak"
    uz_filter: bool = False
    ttl: int = 600  # kesh muddati (soniya)
    enabled: bool = True


# O'zbekistonga oid kalit so'zlar (kichik harfda)
UZ_KEYWORDS: tuple[str, ...] = (
    "uzbek", "o'zbek", "o‘zbek", "ozbek", "tashkent", "toshkent", "samarkand", "samarqand",
    ".uz", "узбек", "ўзбек", "ташкент", "самарканд",
)


# =========================================================================
#  MANBALAR. Yangi manba = bitta qator.
#  Faqat ochiq (login'siz) manbalar. Cloudflare/captcha/login chetlab o'tilmaydi.
# =========================================================================
FEEDS: list[Feed] = [
    # --- Threat intel ---
    Feed("ransomware.live", "UZ", kind="ransomware_live", lang="en",
         category="ransomware", ttl=900),

    # --- Yangiliklar (RSS) ---
    Feed("Gazeta.uz (UZ)", "https://www.gazeta.uz/uz/rss/", lang="uz"),
    Feed("Gazeta.uz (RU)", "https://www.gazeta.uz/ru/rss/", lang="ru"),
    Feed("Kun.uz (UZ)", "https://kun.uz/uz/news/rss", lang="uz"),

    # --- Telegram: o'z akkauntingiz orqali (a'zo bo'lgan kanal/guruhlar) ---
    # Sozlash: backend/.env → TG_API_ID, TG_API_HASH, TG_CHATS ...; login: scripts/tg_login.py
    Feed("Telegram (akkaunt)", "", kind="telegram_user", category="telegram", ttl=300),

    # --- Telegram ochiq kanallar (login'siz, t.me/s) ---
    # Na'muna: Feed("Kanal nomi", "kanal_username", kind="telegram",
    #               category="telegram", uz_filter=True),
]


def enabled_feeds() -> list[Feed]:
    return [f for f in FEEDS if f.enabled]
