from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # "TG_API_ID=" kabi bo'sh qiymatlar → default (None)
    )

    app_name: str = "OSINT Platform"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://osint:osint@localhost:5432/osint"
    db_echo: bool = False  # SQL so'rovlarni logga chiqarish (faqat debug uchun)

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

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
    events_poll_seconds: int = 300  # har necha soniyada yig'ish
    # Ogohlantirish: shu kategoriyalardagi yangi hodisalar saytdagi 🔔 da ko'rsatiladi.
    # notify_telegram=True bo'lsa, qo'shimcha ravishda Telegram "Saved Messages" ga ham yuboriladi.
    notify_telegram: bool = False
    notify_categories: str = "leak,ransomware"

    @property
    def notify_categories_list(self) -> list[str]:
        return [c.strip() for c in self.notify_categories.split(",") if c.strip()]

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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
