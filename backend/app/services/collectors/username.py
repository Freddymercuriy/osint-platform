from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import httpx

from app.services.collectors.base import BaseCollector, CollectResult

# Realistik User-Agent — shaxsiy ma'lumotsiz, generic brauzer
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass
class SiteCheck:
    """Bitta saytni tekshirish qoidasi.

    exists_codes/absent_codes: HTTP status bo'yicha aniqlash.
    absent_text: 200 qaytsa ham, javobda shu matn bo'lsa — profil yo'q.
    """

    name: str
    url: str  # {} o'rniga username qo'yiladi
    exists_codes: tuple[int, ...] = (200,)
    absent_codes: tuple[int, ...] = (404,)
    absent_text: str | None = None
    allow_redirects: bool = False


# Faqat ochiq profil sahifalari. Ba'zi saytlar scraperlarni bloklashi mumkin —
# bunday holda natija "error" bo'ladi va butun qidiruvni to'xtatmaydi.
SITES: list[SiteCheck] = [
    SiteCheck("GitHub", "https://github.com/{}"),
    SiteCheck("GitLab", "https://gitlab.com/{}"),
    SiteCheck("Reddit", "https://www.reddit.com/user/{}/about.json"),
    SiteCheck("Twitch", "https://m.twitch.tv/{}"),
    SiteCheck("Telegram", "https://t.me/{}", absent_text="tgme_page_additional"),
    SiteCheck("Medium", "https://medium.com/@{}"),
    SiteCheck("Dev.to", "https://dev.to/{}"),
    SiteCheck("Replit", "https://replit.com/@{}"),
    SiteCheck("SoundCloud", "https://soundcloud.com/{}"),
    SiteCheck("Pinterest", "https://www.pinterest.com/{}/"),
    SiteCheck("Steam", "https://steamcommunity.com/id/{}"),
    SiteCheck("HackerNews", "https://news.ycombinator.com/user?id={}", absent_text="No such user."),
    SiteCheck("Keybase", "https://keybase.io/{}"),
]


class UsernameCollector(BaseCollector):
    """Berilgan username'ni bir nechta ochiq saytda tekshiradi."""

    name = "username"

    def __init__(self, concurrency: int = 8, timeout: float = 8.0) -> None:
        self._sem = asyncio.Semaphore(concurrency)
        self._timeout = timeout

    async def _check(self, client: httpx.AsyncClient, site: SiteCheck, username: str) -> CollectResult:
        url = site.url.format(username)
        base = CollectResult(source=site.name, type="profile", value=username, url=url)
        async with self._sem:
            try:
                resp = await client.get(url, follow_redirects=site.allow_redirects)
            except (httpx.HTTPError, asyncio.TimeoutError):
                base.status = "error"
                base.confidence = 0.0
                return base

        code = resp.status_code
        if code in site.absent_codes:
            base.status = "not_found"
            base.confidence = 0.0
        elif code in site.exists_codes:
            if site.absent_text and site.absent_text in resp.text:
                base.status = "not_found"
                base.confidence = 0.0
            else:
                base.status = "found"
                base.confidence = 0.85
        else:
            # Noaniq (masalan 301/403/429) — ishonchsiz
            base.status = "error"
            base.confidence = 0.0
        base.raw = {"http_status": code}
        return base

    async def run(self, query: str) -> list[CollectResult]:
        username = query.strip().lstrip("@")
        if not _USERNAME_RE.match(username):
            raise ValueError("Username faqat harf, raqam, '.', '_', '-' dan iborat bo'lishi kerak")

        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            tasks = [self._check(client, site, username) for site in SITES]
            return await asyncio.gather(*tasks)
