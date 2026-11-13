from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollectResult:
    """Bitta OSINT topilma — barcha collectorlar shu formatda qaytaradi."""

    source: str  # qaysi manba (masalan "github")
    type: str  # topilma turi (masalan "profile", "email", "domain")
    value: str  # asosiy qiymat
    url: str | None = None  # topilma havolasi
    detail: str | None = None  # qo'shimcha matn (masalan "MX: gmail.com", "Operator: Beeline")
    status: str = "found"  # "found" | "not_found" | "error"
    confidence: float = 1.0  # 0..1 ishonch darajasi
    raw: dict[str, Any] = field(default_factory=dict)  # xom ma'lumot


class BaseCollector(ABC):
    """Barcha OSINT yig'uvchilar uchun umumiy interfeys.

    Yangi modul qo'shish uchun shu klassdan meros ol, `name` ber va `run` yoz.
    """

    name: str = "base"

    @abstractmethod
    async def run(self, query: str) -> list[CollectResult]:
        """Berilgan so'rov bo'yicha ochiq manbalardan ma'lumot yig'adi."""
        raise NotImplementedError
