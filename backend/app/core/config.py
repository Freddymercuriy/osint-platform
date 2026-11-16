import ipaddress
import os
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env.example va kod ichidagi standart qiymatlar — production'da ishga tushishga yo'l qo'yilmaydi
INSECURE_SECRET_KEYS = frozenset({"change-me", "change-me-to-a-long-random-string", "secret", ""})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Testlar haqiqiy .env (Telegram, kalitlar) ni o'qimasligi uchun yo'lni almashtirish mumkin
        env_file=os.getenv("OSINT_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # "TG_API_ID=" kabi bo'sh qiymatlar → default (None)
    )

    app_name: str = "OSINT Platform"
    environment: str = "development"  # development | production | test
    debug: bool = True

    database_url: str = "postgresql+asyncpg://osint:osint@localhost:5432/osint"
    db_echo: bool = False  # SQL so'rovlarni logga chiqarish (faqat debug uchun)

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # Rollar: shu manzillar admin bo'ladi (vergul bilan). Bo'sh bo'lsa — eng eski faol foydalanuvchi.
    admin_emails: str = ""
    # Ochiq ro'yxatdan o'tish. Berilmasa: development'da yoqiq, boshqa muhitda o'chiq.
    registration_open: bool | None = None

    cors_origins: str = "http://localhost:3000"

    # Telegram user API (my.telegram.org → API development tools)
    tg_api_id: int | None = None
    tg_api_hash: str | None = None
    tg_session_path: str = "data/tg_session"  # .session fayli — MAXFIY, git'ga tushmaydi
    # Qaysi chatlarni o'qish: bo'sh = a'zo bo'lgan barcha kanal/guruhlar,
    # yoki vergul bilan: "kanal_username,-1001234567890"
    tg_chats: str = ""
    tg_dialog_limit: int = 100  # nechta dialogni ko'rib chiqish
    tg_messages_per_chat: int = 30  # har chatdan nechta so'nggi xabar
    tg_uz_filter: bool = True  # faqat O'zbekistonga oid xabarlar
    tg_extra_keywords: str = ""  # qo'shimcha kalit so'zlar, vergul bilan
    tg_leak_chats: str = ""  # shu chatlardagi xabarlar "leak" kategoriyasiga tushadi

    # Fon yig'uvchi (Events)
    events_poll_enabled: bool = True
    # Ogohlantirish: shu kategoriyalardagi yangi hodisalar saytdagi 🔔 da ko'rsatiladi.
    # notify_telegram=True bo'lsa, qo'shimcha ravishda Telegram "Saved Messages" ga ham yuboriladi.
    notify_telegram: bool = False
    notify_categories: str = "leak,ransomware"
    # Retention: shu kundan eski hodisalar bazadan o'chiriladi (0 = o'chirilmaydi).
    # events_retention_keep dagi kategoriyalar hech qachon o'chirilmaydi (kam uchraydigan, muhim hodisalar).
    events_retention_days: int = 90
    events_retention_keep: str = "ransomware,leak"
    # Boshlanish sanasi: shundan OLDINGI hodisalar (barcha kategoriyalar) yig'ilmaydi va bazadan o'chiriladi.
    # "2026-11-14" (kun boshi, Toshkent vaqti UTC+5) yoki to'liq ISO vaqt. Bo'sh = chegara yo'q.
    events_since: str = ""

    # Tashqi manbalar kalitlari (bo'sh — manba `auth_missing` holatida o'chiq turadi). Manba yozuvida faqat
    # o'zgaruvchi NOMI saqlanadi (`sources.api_key_env`), qiymat — shu yerda / muhitda.
    ransomware_live_api_key: str | None = None
    abusech_auth_key: str | None = None
    otx_api_key: str | None = None
    nvd_api_key: str | None = None
    cloudflare_api_token: str | None = None

    # Rate limiting (jarayon xotirasida): urinishlar soni / oyna (soniya)
    rate_limit_enabled: bool = True
    login_rate_ip: int = 20  # bitta IP dan 15 daqiqada
    login_rate_email: int = 10  # bitta email uchun 15 daqiqada
    login_rate_window: int = 900
    search_rate: int = 30  # tekshiruvlar: foydalanuvchi boshiga daqiqada
    search_rate_window: int = 60
    refresh_rate: int = 5  # qo'lda yig'ish: foydalanuvchi boshiga 10 daqiqada
    refresh_rate_window: int = 600
    # Ishonchli reverse proxy'lar (IP yoki CIDR, vergul bilan). Faqat so'rov shulardan kelsa `X-Forwarded-For`
    # o'qiladi (o'ngdan birinchi ishonchsiz manzil = mijoz). Bo'sh — sarlavha e'tiborsiz (to'g'ridan-to'g'ri ulanish).
    trusted_proxies: str = ""

    # Statistika vaqt bo'laklari (soat/kun/hafta) shu zonada
    app_timezone: str = "Asia/Tashkent"

    # Manba shuncha soat davomida down/blocked bo'lsa — adminlarga ogohlantirish
    source_down_alert_hours: int = 3

    # Tarjima — o'z NLLB servisimiz (facebook/nllb-200, FLORES-200 kodlari, kalitsiz). Bo'sh URL — tarjimalar "pending".
    translate_api_url: str = "https://translate.deepcore.uz"
    translate_timeout_seconds: float = 30.0
    translate_enabled: bool = True
    # Oylik belgilar chegarasi; 0 — chegarasiz (o'z servisimiz, to'lov yo'q). Hisob statistika uchun baribir yuritiladi.
    translate_monthly_char_limit: int = 0

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in ("development", "dev", "local", "test")

    @property
    def registration_allowed(self) -> bool:
        if self.registration_open is not None:
            return self.registration_open
        return self.is_development

    @property
    def admin_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def secret_key_is_default(self) -> bool:
        return self.secret_key in INSECURE_SECRET_KEYS or len(self.secret_key) < 32

    @property
    def notify_categories_list(self) -> list[str]:
        return [c.strip() for c in self.notify_categories.split(",") if c.strip()]

    @property
    def events_since_dt(self) -> datetime | None:
        value = self.events_since.strip()
        if not value:
            return None
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:  # sana yoki zonasiz vaqt → Toshkent vaqti
            dt = dt.replace(tzinfo=timezone(timedelta(hours=5)))
        return dt.astimezone(UTC)

    @property
    def events_retention_keep_list(self) -> list[str]:
        return [c.strip() for c in self.events_retention_keep.split(",") if c.strip()]

    @staticmethod
    def _split_chats(value: str) -> list[str]:
        return [c.strip().lstrip("@") for c in value.split(",") if c.strip()]

    @property
    def tg_chats_list(self) -> list[str]:
        return self._split_chats(self.tg_chats)

    @property
    def tg_leak_chats_list(self) -> list[str]:
        return self._split_chats(self.tg_leak_chats)

    @property
    def tg_extra_keywords_list(self) -> list[str]:
        return [k.strip().lower() for k in self.tg_extra_keywords.split(",") if k.strip()]

    @field_validator("trusted_proxies")
    @classmethod
    def _check_trusted_proxies(cls, value: str) -> str:
        """Noto'g'ri IP/CIDR — ishga tushishdayoq xato (birinchi login so'rovida emas)."""
        for part in value.split(","):
            if part.strip():
                ipaddress.ip_network(part.strip(), strict=False)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
