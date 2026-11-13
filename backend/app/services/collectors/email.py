from __future__ import annotations

import hashlib

import dns.asyncresolver
import httpx
from email_validator import EmailNotValidError, validate_email

from app.services.collectors.base import BaseCollector, CollectResult

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class EmailCollector(BaseCollector):
    """Email bo'yicha ochiq signallar: sintaksis, MX, Gravatar."""

    name = "email"

    async def run(self, query: str) -> list[CollectResult]:
        email = query.strip()
        results: list[CollectResult] = []

        # 1) Sintaksis
        try:
            info = validate_email(email, check_deliverability=False)
            normalized = info.normalized
            domain = info.domain
            results.append(
                CollectResult(
                    source="Sintaksis",
                    type="email",
                    value=normalized,
                    detail="To'g'ri formatdagi email",
                    status="found",
                    confidence=1.0,
                )
            )
        except EmailNotValidError as exc:
            results.append(
                CollectResult(
                    source="Sintaksis",
                    type="email",
                    value=email,
                    detail=str(exc),
                    status="error",
                    confidence=0.0,
                )
            )
            return results  # Noto'g'ri bo'lsa, davom etmaymiz

        # 2) MX yozuvlari (domen pochta qabul qiladimi)
        try:
            answers = await dns.asyncresolver.resolve(domain, "MX")
            hosts = sorted(str(r.exchange).rstrip(".") for r in answers)
            results.append(
                CollectResult(
                    source="MX (pochta serveri)",
                    type="dns",
                    value=domain,
                    detail=", ".join(hosts[:3]) + (" ..." if len(hosts) > 3 else ""),
                    status="found",
                    confidence=0.9,
                )
            )
        except Exception:
            results.append(
                CollectResult(
                    source="MX (pochta serveri)",
                    type="dns",
                    value=domain,
                    detail="MX yozuvi topilmadi — domen email qabul qilmasligi mumkin",
                    status="not_found",
                    confidence=0.0,
                )
            )

        # 3) Gravatar (ochiq avatar/profil xizmati)
        md5 = hashlib.md5(normalized.lower().encode("utf-8")).hexdigest()
        avatar_url = f"https://www.gravatar.com/avatar/{md5}?d=404"
        profile_url = f"https://gravatar.com/{md5}"
        try:
            async with httpx.AsyncClient(
                timeout=8.0, headers={"User-Agent": _USER_AGENT}
            ) as client:
                resp = await client.get(avatar_url)
            if resp.status_code == 200:
                results.append(
                    CollectResult(
                        source="Gravatar",
                        type="profile",
                        value=normalized,
                        url=profile_url,
                        detail="Gravatar avatari mavjud",
                        status="found",
                        confidence=0.8,
                    )
                )
            else:
                results.append(
                    CollectResult(
                        source="Gravatar",
                        type="profile",
                        value=normalized,
                        detail="Gravatar topilmadi",
                        status="not_found",
                        confidence=0.0,
                    )
                )
        except httpx.HTTPError:
            results.append(
                CollectResult(
                    source="Gravatar",
                    type="profile",
                    value=normalized,
                    detail="Gravatar'ga ulanib bo'lmadi",
                    status="error",
                    confidence=0.0,
                )
            )

        return results
