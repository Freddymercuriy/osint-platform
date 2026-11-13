"""Telegram akkauntiga BIR MARTA interaktiv login.

Ishga tushirish (o'z terminalingizda, interaktiv):
    docker-compose exec backend python scripts/tg_login.py

Telefon raqam, Telegram'ga keladigan kod va (bo'lsa) 2FA parol so'raladi.
Natijada backend/data/tg_session.session fayli yaratiladi — uni hech kimga bermang.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient  # noqa: E402

from app.core.config import settings  # noqa: E402


async def main() -> None:
    if not (settings.tg_api_id and settings.tg_api_hash):
        print("❌ backend/.env da TG_API_ID va TG_API_HASH yo'q. my.telegram.org dan oling.")
        return
    Path(settings.tg_session_path).parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(settings.tg_session_path, settings.tg_api_id, settings.tg_api_hash)
    await client.start()  # telefon / kod / parolni so'raydi
    me = await client.get_me()
    print(f"✅ Kirildi: {me.first_name} (@{me.username}). Session saqlandi.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
