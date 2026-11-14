from __future__ import annotations

import phonenumbers
from phonenumbers import carrier, geocoder, timezone

from app.core.i18n import current_lang, t
from app.services.collectors.base import BaseCollector, CollectResult

# raqam turi → katalog kodi
_NUMBER_TYPE_CODES = {
    phonenumbers.PhoneNumberType.MOBILE: "c_pt_mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE: "c_pt_fixed",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "c_pt_fixed_or_mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "c_pt_toll_free",
    phonenumbers.PhoneNumberType.VOIP: "c_pt_voip",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "c_pt_premium",
}


class PhoneCollector(BaseCollector):
    """Telefon raqami bo'yicha offline metadata (davlat, operator, tur)."""

    name = "phone"

    async def run(self, query: str) -> list[CollectResult]:
        raw = query.strip()
        lang = current_lang()
        results: list[CollectResult] = []

        try:
            # Xalqaro format ("+") talab qilinadi, aks holda region kerak
            num = phonenumbers.parse(raw, None)
        except phonenumbers.NumberParseException as exc:
            return [
                CollectResult(
                    source=t("c_phone_parsing_src", lang),
                    type="phone",
                    value=raw,
                    detail=t("c_phone_unparsable", lang, error=exc),
                    status="error",
                    confidence=0.0,
                )
            ]

        valid = phonenumbers.is_valid_number(num)
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        intl = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

        results.append(
            CollectResult(
                source=t("c_phone_valid_src", lang),
                type="phone",
                value=e164,
                detail=t("c_phone_valid" if valid else "c_phone_invalid", lang),
                status="found" if valid else "not_found",
                confidence=1.0 if valid else 0.3,
            )
        )
        results.append(
            CollectResult(
                source=t("c_phone_format_src", lang),
                type="phone",
                value=e164,
                detail=t("c_phone_intl", lang, number=intl),
                status="found",
                confidence=1.0,
            )
        )

        country = geocoder.description_for_number(num, "en")
        if country:
            results.append(
                CollectResult(
                    source=t("c_phone_region_src", lang),
                    type="geo",
                    value=str(num.country_code),
                    detail=t("c_phone_region", lang, country=country, code=num.country_code),
                    status="found",
                    confidence=0.9,
                )
            )

        carrier_name = carrier.name_for_number(num, "en")
        if carrier_name:
            results.append(
                CollectResult(
                    source=t("c_phone_carrier_src", lang),
                    type="carrier",
                    value=carrier_name,
                    detail=t("c_phone_carrier", lang, name=carrier_name),
                    status="found",
                    confidence=0.7,
                )
            )

        number_type = phonenumbers.number_type(num)
        type_label = t(_NUMBER_TYPE_CODES.get(number_type, "c_pt_unknown"), lang)
        results.append(
            CollectResult(
                source=t("c_phone_type_src", lang),
                type="line_type",
                value=type_label,
                detail=t("c_phone_type", lang, label=type_label),
                status="found",
                confidence=0.7,
            )
        )

        zones = timezone.time_zones_for_number(num)
        if zones:
            results.append(
                CollectResult(
                    source=t("c_phone_tz_src", lang),
                    type="timezone",
                    value=", ".join(zones),
                    detail=", ".join(zones),
                    status="found",
                    confidence=0.6,
                )
            )

        return results
