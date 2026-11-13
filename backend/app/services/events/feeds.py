from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Feed:
    """Bitta yangilik/tadbir manbasi (RSS feed)."""

    name: str  # ko'rsatiladigan nom
    url: str  # RSS feed manzili
    lang: str = "uz"  # til
    category: str = "news"  # "news" | "events" | ...
    enabled: bool = True


# =========================================================================
#  O'ZBEKISTON MANBALARI
#  Bu ro'yxatni foydalanuvchi bergan saytlar bilan to'ldiramiz/tuzatamiz.
#  Har bir manba RSS bo'lishi afzal. RSS yo'q bo'lsa — alohida parser yoziladi.
#  Ishlamaydigan feed avtomatik o'tkazib yuboriladi (butun ro'yxat yiqilmaydi).
# =========================================================================
FEEDS: list[Feed] = [
    # --- Dastlabki na'munalar (foydalanuvchi ro'yxati bilan almashtiriladi) ---
    Feed("Gazeta.uz (UZ)", "https://www.gazeta.uz/uz/rss/", lang="uz"),
    Feed("Gazeta.uz (RU)", "https://www.gazeta.uz/ru/rss/", lang="ru"),
    Feed("Kun.uz (UZ)", "https://kun.uz/uz/news/rss", lang="uz"),
]


def enabled_feeds() -> list[Feed]:
    return [f for f in FEEDS if f.enabled]
