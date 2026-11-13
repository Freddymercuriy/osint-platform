from __future__ import annotations

import phonenumbers
from phonenumbers import carrier, geocoder, timezone

from app.services.collectors.base import BaseCollector, CollectResult

_NUMBER_TYPE_LABELS = {
    phonenumbers.PhoneNumberType.MOBILE: "Mobil",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Statsionar",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Statsionar yoki mobil",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Bepul (toll-free)",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium",
}


class PhoneCollector(BaseCollector):
    """Telefon raqami bo'yicha offline metadata (davlat, operator, tur)."""

    name = "phone"

    async def run(self, query: str) -> list[CollectResult]:
        raw = query.strip()
        results: list[CollectResult] = []

        try:
            # Xalqaro format ("+") talab qilinadi, aks holda region kerak
            num = phonenumbers.parse(raw, None)
        except phonenumbers.NumberParseException as exc:
            return [
                CollectResult(
                    source="Parsing",
                    type="phone",
                    value=raw,
                    detail=f"Raqamni o'qib bo'lmadi: {exc}. Xalqaro formatda kiriting, masalan +998901234567",
                    status="error",
                    confidence=0.0,
                )
            ]

        valid = phonenumbers.is_valid_number(num)
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        intl = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

        results.append(
            CollectResult(
                source="Yaroqlilik",
                type="phone",
                value=e164,
                detail="Raqam yaroqli" if valid else "Raqam yaroqsiz ko'rinadi",
                status="found" if valid else "not_found",
                confidence=1.0 if valid else 0.3,
            )
        )
        results.append(
            CollectResult(
                source="Format",
                type="phone",
                value=e164,
                detail=f"Xalqaro: {intl}",
                status="found",
                confidence=1.0,
            )
        )

        country = geocoder.description_for_number(num, "en")
        if country:
            results.append(
                CollectResult(
                    source="Hudud",
                    type="geo",
                    value=str(num.country_code),
                    detail=f"Davlat/hudud: {country} (kod +{num.country_code})",
                    status="found",
                    confidence=0.9,
                )
            )

        carrier_name = carrier.name_for_number(num, "en")
        if carrier_name:
            results.append(
                CollectResult(
                    source="Operator",
                    type="carrier",
                    value=carrier_name,
                    detail=f"Operator: {carrier_name}",
                    status="found",
                    confidence=0.7,
                )
            )

        number_type = phonenumbers.number_type(num)
        type_label = _NUMBER_TYPE_LABELS.get(number_type, "Noma'lum")
        results.append(
            CollectResult(
                source="Raqam turi",
                type="line_type",
                value=type_label,
                detail=f"Tur: {type_label}",
                status="found",
                confidence=0.7,
            )
        )

        zones = timezone.time_zones_for_number(num)
        if zones:
            results.append(
                CollectResult(
                    source="Vaqt mintaqasi",
                    type="timezone",
                    value=", ".join(zones),
                    detail=", ".join(zones),
                    status="found",
                    confidence=0.6,
                )
            )

        return results
