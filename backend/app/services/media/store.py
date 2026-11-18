"""Rasm fayllari: yo'l, JPEG kodlash, atomik yozish, versiya (kesh) va imzolangan URL.

Har hodisa — ikki fayl: `<id>_l.jpg` (1280×720, Telegram va katta ko'rinish) va `<id>_s.jpg` (640×360, kartalar).
Fayllar `MEDIA_DIR/events/<id // 1000>/` da (bitta papkada minglab fayl bo'lmasin); jadvaldagi `version` — katta
faylning SHA-256 boshi: URL'da turadi, rasm almashsa brauzer keshi yangilanadi.

URL imzosi: `<img>` so'rovida Authorization sarlavhasi bo'lmaydi, shuning uchun havola HMAC (SECRET_KEY) bilan
imzolanadi — imzosiz yoki boshqa hodisa imzosi bilan rasm berilmaydi (ID'larni sanab chiqib bo'lmaydi).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import settings

LARGE = (1280, 720)
SMALL = (640, 360)
APP_ROOT = Path(__file__).resolve().parents[3]  # backend/ (konteynerda /app)


def media_root() -> Path:
    root = Path(settings.media_dir)
    return root if root.is_absolute() else APP_ROOT / root


def file_path(event_id: int, size: str = "l") -> Path:
    suffix = "s" if size == "s" else "l"
    return media_root() / "events" / f"{event_id // 1000:05d}" / f"{event_id}_{suffix}.jpg"


def encode(img: Image.Image) -> tuple[bytes, bytes]:
    """RGB 16:9 rasm → (katta, kichik) JPEG; EXIF va boshqa meta yozilmaydi."""
    large = img.convert("RGB")
    if large.size != LARGE:
        large = large.resize(LARGE, Image.Resampling.LANCZOS)
    big = BytesIO()
    large.save(big, "JPEG", quality=85, optimize=True, progressive=True)
    small = BytesIO()
    large.resize(SMALL, Image.Resampling.LANCZOS).save(small, "JPEG", quality=80, optimize=True, progressive=True)
    return big.getvalue(), small.getvalue()


def version_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def write(event_id: int, large: bytes, small: bytes) -> str:
    """Ikkala faylni atomik yozadi (vaqtinchalik fayl → os.replace); versiyani qaytaradi."""
    for size, data in (("l", large), ("s", small)):
        path = file_path(event_id, size)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return version_of(large)


def exists(event_id: int) -> bool:
    return file_path(event_id, "l").is_file() and file_path(event_id, "s").is_file()


def read(event_id: int, size: str = "l") -> bytes | None:
    path = file_path(event_id, size)
    try:
        return path.read_bytes()
    except OSError:
        return None


def remove(event_id: int) -> None:
    for size in ("l", "s"):
        try:
            file_path(event_id, size).unlink()
        except OSError:
            pass


def sign(event_id: int) -> str:
    key = (settings.secret_key or "").encode()
    return hmac.new(key, f"event-image:{event_id}".encode(), hashlib.sha256).hexdigest()[:20]


def verify(event_id: int, sig: str | None) -> bool:
    return bool(sig) and hmac.compare_digest(sign(event_id), sig)


def urls(event_id: int, version: str | None) -> dict[str, str]:
    """API javobi uchun nisbiy havolalar (frontend API manzilini oldiga qo'shadi)."""
    base = f"/api/media/events/{event_id}.jpg"
    tail = f"v={version or '0'}&sig={sign(event_id)}"
    return {"url": f"{base}?size=l&{tail}", "thumb": f"{base}?size=s&{tail}"}


def stored_ids() -> set[int]:
    """Diskdagi rasmlari bor hodisalar (yetim fayllarni tozalash uchun)."""
    out: set[int] = set()
    root = media_root() / "events"
    if not root.is_dir():
        return out
    for path in root.glob("*/*_l.jpg"):
        head = path.name.split("_", 1)[0]
        if head.isdigit():
            out.add(int(head))
    return out
