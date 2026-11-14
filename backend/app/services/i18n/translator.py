"""Tarjima provayderlari. Rasmiy Google Cloud Translation API (Basic, v2) — API kalit bilan.

`googletrans` kabi ochiq veb-endpoint'ni "qirib oladigan" kutubxonalar ishlatilmaydi: ular ogohlantirishsiz buziladi
va server manzilini bloklatadi.
"""

from __future__ import annotations

from typing import Protocol

from app.services.connectors.base import AuthMissing, ConnectorError, RateLimited
from app.services.connectors.http import HttpFetcher, parse_retry_after

GOOGLE_V2 = "https://translation.googleapis.com/language/translate/v2"
MAX_STRINGS = 128  # bitta so'rovda (hujjat bo'yicha)
MAX_CHARS = 25_000  # bitta so'rovdagi tavsiya etilgan chegara (30K dan past)


def _error(code: int, body: str, retry_after: str | None) -> ConnectorError:
    """Google xato javobi → xato turi (kalit matni hech qayerga yozilmaydi)."""
    low = body.lower()
    if code == 429 or "ratelimitexceeded" in low or "quota" in low or "dailylimit" in low:
        return RateLimited(f"Google Translate limiti (HTTP {code})", http_status=code,
                           retry_after=parse_retry_after(retry_after) or 3600)
    if code in (401, 403) or (code == 400 and "api key" in low):
        return AuthMissing(f"Google Translate kaliti rad etildi yoki API yoqilmagan (HTTP {code})", http_status=code)
    return ConnectorError(f"Google Translate: HTTP {code}", http_status=code)


class Translator(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]: ...


class GoogleTranslator:
    name = "google"

    def __init__(self, api_key: str | None, http: HttpFetcher) -> None:
        self.api_key = api_key
        self.http = http

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]:
        if not self.api_key:
            raise AuthMissing("GOOGLE_TRANSLATE_API_KEY sozlanmagan")
        resp = await self.http.post(
            GOOGLE_V2,
            # Kalit sarlavhada — URL'da (va loglarda) ko'rinmasin
            headers={"X-Goog-Api-Key": self.api_key},
            data={"q": texts, "source": source, "target": target, "format": "text"},
            raise_errors=False,
        )
        if resp.status_code != 200:
            raise _error(resp.status_code, resp.text[:2000], resp.headers.get("retry-after"))
        data = resp.json()
        items = (data.get("data") or {}).get("translations") or []
        if len(items) != len(texts):
            raise ConnectorError(f"Google Translate: {len(texts)} ta matn uchun {len(items)} ta javob")
        return [i.get("translatedText") or "" for i in items]


class FakeTranslator:
    """Testlar uchun: "[target] matn" qaytaradi va chaqiruvlarni yozib boradi."""

    name = "fake"

    def __init__(self, fail: Exception | None = None, cyrillic_uz: bool = False) -> None:
        self.calls: list[tuple[str, str, list[str]]] = []
        self.fail = fail
        self.cyrillic_uz = cyrillic_uz

    @property
    def configured(self) -> bool:
        return True

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]:
        self.calls.append((source, target, list(texts)))
        if self.fail:
            raise self.fail
        if target == "uz" and self.cyrillic_uz:
            return [f"Ўзбекча: {t}" for t in texts]
        return [f"[{target}] {t}" for t in texts]
