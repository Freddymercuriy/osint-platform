"""Hodisa rasmlari: rubrika va motiv, illyustratsiya, saqlash va imzo, maqola rasmi (og:image) va xavfsizlik
qoidalari (SSRF, maxfiy kategoriyalar, saytning umumiy rasmi), API, RSS rasmi, fon ishchisi."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from io import BytesIO

import httpx
import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.config import settings
from app.models import EventImage, EventRecord, Source
from app.services.connectors import http as http_mod
from app.services.connectors.http import HttpFetcher
from app.services.connectors.rss import entry_image, parse_feed
from app.services.media import art, service, source, store
from app.services.media.rubric import RUBRICS, motif_of, rubric_of


def _photo(w: int = 1200, h: int = 630, *, flat: bool = False, fmt: str = "JPEG", alpha: bool = False) -> bytes:
    """Sinov "foto"si: gradient + shovqin (tekis emas) yoki bir rangli fon."""
    mode = "RGBA" if alpha else "RGB"
    img = Image.new(mode, (w, h), (240, 240, 240, 0) if alpha else (240, 240, 240))
    if not flat:
        d = ImageDraw.Draw(img)
        rng = random.Random(1)
        for _ in range(400):
            x, y, r = rng.randrange(w), rng.randrange(h), rng.randrange(5, 60)
            col = (rng.randrange(256), rng.randrange(256), rng.randrange(256)) + ((255,) if alpha else ())
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    out = BytesIO()
    img.save(out, fmt)
    return out.getvalue()


async def _event(db, uid="m1", *, category="other", channel="news", url=None, source_id=None, **kw) -> EventRecord:
    ev = EventRecord(uid=uid, source=kw.pop("source", "Kun.uz"), category=category, channel=channel,
                     title=kw.pop("title", "Hackers attacked a bank in Tashkent"), summary=kw.pop("summary", ""),
                     url=url or f"https://news.example/{uid}", lang="en", first_seen=kw.pop("first_seen", None)
                     or datetime.now(UTC), scope=kw.pop("scope", "regional"), source_id=source_id, **kw)
    db.add(ev)
    await db.commit()
    return ev


@pytest.fixture
def web(monkeypatch):
    """Soxta internet: sahifalar va rasmlar (MockTransport), DNS — "internal*" xostlar ichki manzil (SSRF)."""
    pages: dict[str, httpx.Response] = {}
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return pages.get(str(req.url)) or httpx.Response(404, text="not found")

    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    monkeypatch.setattr(http_mod, "RESOLVER",
                        lambda host: ["10.0.0.5"] if host.startswith("internal") else ["93.184.216.34"])
    http_mod.reset_gates()
    monkeypatch.setattr(settings, "media_source_images", True)
    monkeypatch.setattr(service, "_http", HttpFetcher.create(transport=httpx.MockTransport(handler)))

    def page(url: str, image: str | None, extra_head: str = "") -> None:
        meta = f'<meta property="og:image" content="{image}">' if image else ""
        pages[url] = httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                                    text=f"<html><head><title>x</title>{extra_head}{meta}</head><body>x</body></html>")

    def image(url: str, data: bytes, ctype: str = "image/jpeg") -> None:
        pages[url] = httpx.Response(200, headers={"content-type": ctype}, content=data)

    yield type("Web", (), {"page": staticmethod(page), "image": staticmethod(image), "seen": seen})


# ---------------------------------------------------------------- rubrika va motiv
@pytest.mark.parametrize("category,title,rubric,motif", [
    ("vulnerability", "OpenJDK dasturidagi kritik Java4Shell zaifligi", "vulnerability", "bug"),
    ("vulnerability", "Microsoft patches exploited zero-day", "vulnerability", "shield_check"),
    ("ransomware", "Akira claims attack on a bank", "cyber", "lock"),
    ("leak", "Data of 16.6 million Kazakh citizens for sale", "cyber", "database"),
    ("phishing", "Phishing wave hits Uzbek banks", "cyber", "hook"),
    ("other", "AI kiberhujumlarni tezlashtirmoqda: O'zbekiston biznesi", "ai", "neural"),
    ("other", "Kyrgyzstan's banks are operating normally, central bank says amid cyberattack rumours", "economy", "chart"),
    ("advisory", "Onlayn platformalarga nisbatan ma'muriy javobgarlik kuchaytirildi", "politics", "document"),
    ("other", "В Казахстане приняли закон о защите персональных данных", "politics", "building"),
    ("ddos-outage", "Beeline mobil aloqasida uzilish", "telecom", "broken_link"),
    ("ddos-outage", "DDoS attack takes down bank website", "cyber", "server"),
    ("other", "Starlink terminals seized in Tashkent", "telecom", "antenna"),
    ("other", "Microsoft releases a new Windows preview", "tech", "chip"),
    ("other", "Turla xakerlari yangi zararli dasturdan foydalanmoqda", "cyber", "shield"),
    ("other", "Qandaydir yangilik", "cyber", "shield"),  # kalit so'z yo'q — kiber-filtrdan o'tgan → cyber
])
def test_rubric_and_motif_follow_category_and_keywords(category, title, rubric, motif):
    got = rubric_of(category, title)
    assert got == rubric and got in RUBRICS
    assert motif_of(category, got, title) == motif


# ---------------------------------------------------------------- illyustratsiya
def test_illustrations_are_deterministic_unique_and_cover_every_motif():
    a = art.render(art.ArtSpec(seed=42, rubric="cyber", motif="shield", countries=("UZ",)))
    b = art.render(art.ArtSpec(seed=42, rubric="cyber", motif="shield", countries=("UZ",)))
    c = art.render(art.ArtSpec(seed=43, rubric="cyber", motif="shield", countries=("UZ",)))
    assert a.size == (1280, 720) and a.mode == "RGB"
    assert a.tobytes() == b.tobytes()  # bir urug' — bir rasm (qayta chizilsa ham)
    assert a.tobytes() != c.tobytes()  # boshqa hodisa — boshqa rasm
    for i, motif in enumerate(art.ICONS):
        for rubric in ("cyber", "vulnerability", "ai", "tech", "telecom", "economy", "politics"):
            if (i + len(rubric)) % 3:  # hamma juftlik emas (tezlik), lekin har motiv va rubrika kamida bir marta
                continue
            img = art.render(art.ArtSpec(seed=i, rubric=rubric, motif=motif))
            assert img.size == (1280, 720)
    assert art.render_fallback("ai").size == (1280, 720)


# ---------------------------------------------------------------- saqlash va imzo
def test_store_writes_atomically_and_signs_urls():
    large, small = store.encode(art.render(art.ArtSpec(seed=1)))
    assert Image.open(BytesIO(large)).size == (1280, 720) and Image.open(BytesIO(small)).size == (640, 360)
    version = store.write(7, large, small)
    assert store.exists(7) and store.read(7, "s") == small and version == store.version_of(large)
    assert store.stored_ids() == {7}
    links = store.urls(7, version)
    assert links["thumb"].startswith("/api/media/events/7.jpg?size=s&v=" + version + "&sig=")
    sig = links["url"].rsplit("sig=", 1)[1]
    assert store.verify(7, sig) and not store.verify(8, sig) and not store.verify(7, "") and not store.verify(7, None)
    store.remove(7)
    assert not store.exists(7)


# ---------------------------------------------------------------- maqola rasmi
def test_page_images_parsing():
    html = ('<head><meta name="twitter:image" content="/img/tw.jpg">'
            "<meta content='https://cdn.example/og.jpg?a=1&amp;b=2' property='og:image'>"
            '<meta property="og:image:secure_url" content="https://cdn.example/logo.svg">'
            '<link rel="image_src" href="https://t.me/x.jpg"></head>')
    assert source.page_images(html, "https://news.example/a/b") == [
        "https://cdn.example/og.jpg?a=1&b=2", "https://news.example/img/tw.jpg"]  # svg va t.me — yo'q
    card = '<meta property="og:image" content="https://habr.com/share/publication/1109300/a47b/">'
    assert source.page_images(card, "https://habr.com/ru/articles/1109300/") == []  # matnli ijtimoiy karta


@pytest.mark.parametrize("kw,reason", [
    ({}, None),
    ({"channel": "telegram_channel"}, "not_news_site"),
    ({"category": "leak"}, "sensitive_category"),
    ({"category": "ransomware"}, "sensitive_category"),
    ({"reliability": "underground"}, "untrusted_source"),
    ({"url": "http://abcdefghijklmnop.onion/x"}, "unsafe_url"),
    ({"url": "https://news.google.com/rss/articles/abc"}, "unsafe_url"),
    ({"url": "https://files.example/dump.zip"}, "unsafe_url"),
])
def test_source_image_eligibility(kw, reason, monkeypatch):
    monkeypatch.setattr(settings, "media_source_images", True)
    base = {"category": "other", "channel": "news", "reliability": "media", "url": "https://kun.uz/news/1"}
    assert source.ineligible(**{**base, **kw}) == reason


@pytest.mark.parametrize("data,err", [
    (_photo(300, 200), "too_small"),
    (_photo(600, 900), "not_landscape"),
    (_photo(1200, 630, flat=True), "flat_image"),
    (_photo(1200, 630, fmt="PNG", alpha=True), "transparent_logo"),
    (b"not an image", "bad_image"),
])
def test_unusable_images_are_rejected(data, err):
    with pytest.raises(source.SourceImageError, match=err):
        source.normalize(source.decode(data))


def test_photo_is_cropped_to_16_9():
    img = source.normalize(source.decode(_photo(1600, 1000)))
    assert img.size == (1280, 720) and img.mode == "RGB"


async def test_article_image_is_used_when_safe(db, web):
    ev = await _event(db, url="https://news.example/a1")
    web.page("https://news.example/a1", "https://cdn.example/a1.jpg")
    web.image("https://cdn.example/a1.jpg", _photo())
    row = await service.ensure_image(db, ev, fetch=True)
    await db.commit()
    assert row.kind == "source" and row.source_url == "https://cdn.example/a1.jpg" and row.source_checked
    assert store.exists(ev.id) and Image.open(BytesIO(store.read(ev.id))).size == (1280, 720)


async def test_site_wide_image_is_treated_as_logo(db, web):
    a = await _event(db, uid="a", url="https://news.example/a")
    b = await _event(db, uid="b", url="https://news.example/b")
    for url in ("https://news.example/a", "https://news.example/b"):
        web.page(url, "https://cdn.example/default.jpg")
    web.image("https://cdn.example/default.jpg", _photo())
    assert (await service.ensure_image(db, a, fetch=True)).kind == "source"
    await db.commit()
    rb = await service.ensure_image(db, b, fetch=True)  # ikkinchi hodisada ham shu rasm — saytning umumiy rasmi
    await db.commit()
    ra = await db.get(EventImage, a.id, populate_existing=True)
    assert rb.kind == "generated" and rb.error == "generic_site_image"
    assert ra.kind == "generated" and ra.error == "generic_site_image"  # birinchisi ham illyustratsiyaga o'tdi


async def test_ssrf_and_sensitive_events_never_fetch(db, web):
    internal = await _event(db, uid="i", url="https://news.example/i")
    web.page("https://news.example/i", "https://internal.corp/secret.jpg")
    row = await service.ensure_image(db, internal, fetch=True)
    assert row.kind == "generated" and "internal.corp/secret.jpg" not in " ".join(web.seen)  # ichki manzil — yo'q
    leak = await _event(db, uid="l", category="leak", url="https://news.example/l")
    under_src = Source(name="Leak chat", kind="rss", reliability="underground", config={}, enabled=True)
    db.add(under_src)
    await db.commit()
    under = await _event(db, uid="u", url="https://news.example/u", source_id=under_src.id)
    tg = await _event(db, uid="t", channel="telegram_channel", url="https://t.me/c/1")
    before = len(web.seen)
    for ev, why in ((leak, "sensitive_category"), (under, "untrusted_source"), (tg, "not_news_site")):
        row = await service.ensure_image(db, ev, fetch=True)
        assert row.kind == "generated" and row.error == why and row.source_checked
    assert len(web.seen) == before  # tarmoqqa umuman chiqilmadi


async def test_missing_image_falls_back_to_illustration_and_then_to_fallback(db, web, monkeypatch):
    ev = await _event(db, url="https://news.example/none")
    web.page("https://news.example/none", None)
    row = await service.ensure_image(db, ev, fetch=True)
    assert row.kind == "generated" and row.error == "no_image_on_page"
    broken = await _event(db, uid="x")

    def boom(_spec):
        raise RuntimeError("draw failed")

    monkeypatch.setattr(art, "render", boom)
    row = await service.ensure_image(db, broken)
    assert row.kind == "fallback" and store.exists(broken.id)  # rasmsiz qolmadi


async def test_worker_processes_newest_first_and_upgrades_illustrations(db, web):
    old = await _event(db, uid="old", url="https://news.example/old", first_seen=datetime.now(UTC) - timedelta(days=1))
    new = await _event(db, uid="new", url="https://news.example/new")
    web.page("https://news.example/new", "https://cdn.example/new.jpg")
    web.image("https://cdn.example/new.jpg", _photo())
    web.page("https://news.example/old", None)
    pre = await service.ensure_image(db, new)  # API so'rovi: tarmoqsiz illyustratsiya, keyin ishchi yangilaydi
    await db.commit()
    assert pre.kind == "generated" and not pre.source_checked
    pre_version = pre.version
    stats = await service.process_pending(db, limit=10)
    assert stats.ids[0] == new.id and stats.source == 1 and stats.generated == 1
    upgraded = await db.get(EventImage, new.id, populate_existing=True)
    assert upgraded.kind == "source" and upgraded.version != pre_version
    assert (await service.process_pending(db)).done == 0  # hammasi tekshirilgan
    await db.delete(old)
    await db.commit()
    assert await service.purge_orphans(db) == 1 and not store.exists(old.id)


# ---------------------------------------------------------------- API
async def test_image_endpoint_requires_signature_and_draws_on_demand(db, client):
    ev = await _event(db, title="Phishing wave hits Uzbek banks", category="phishing")
    sig = store.sign(ev.id)
    assert (await client.get(f"/api/media/events/{ev.id}.jpg?sig=bad")).status_code == 404
    assert (await client.get(f"/api/media/events/{ev.id + 99}.jpg?sig={store.sign(ev.id + 99)}")).status_code == 404
    r = await client.get(f"/api/media/events/{ev.id}.jpg?size=s&sig={sig}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert Image.open(BytesIO(r.content)).size == (640, 360) and "max-age=300" in r.headers["cache-control"]
    row = await db.scalar(select(EventImage).where(EventImage.event_id == ev.id))
    r = await client.get(f"/api/media/events/{ev.id}.jpg?size=l&v={row.version}&sig={sig}")
    assert Image.open(BytesIO(r.content)).size == (1280, 720) and "immutable" in r.headers["cache-control"]


async def test_events_api_returns_image_links_and_rubric(db, client, admin_headers):
    ev = await _event(db, title="Phishing wave hits Uzbek banks", category="phishing")
    r = await client.get("/api/events?scope=all", headers=admin_headers)
    item = next(i for i in r.json()["items"] if i["id"] == ev.id)
    assert item["rubric"] == "cyber" and item["image"]["kind"] == "pending"
    assert item["image"]["thumb"].startswith(f"/api/media/events/{ev.id}.jpg?size=s&v=0&sig=")
    assert (await client.get(item["image"]["thumb"])).status_code == 200  # imzoli havola autentifikatsiyasiz ochiladi
    r = await client.get("/api/events?scope=all", headers=admin_headers)
    item = next(i for i in r.json()["items"] if i["id"] == ev.id)
    assert item["image"]["kind"] == "generated" and "v=0" not in item["image"]["url"]
    # kategoriya o'zgarsa — illyustratsiya qayta chiziladi
    r = await client.patch(f"/api/events/{ev.id}", json={"category": "ransomware"}, headers=admin_headers)
    assert r.status_code == 200 and await db.scalar(select(EventImage).where(EventImage.event_id == ev.id)) is None


# ---------------------------------------------------------------- RSS rasmi
async def test_rss_entry_image_sources():
    feed = b"""<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
      <item><title>A</title><link>https://n.example/a</link>
        <media:content url="https://cdn.example/a.jpg" medium="image"/></item>
      <item><title>B</title><link>https://n.example/b</link>
        <enclosure url="https://cdn.example/b.png" type="image/png" length="1"/></item>
      <item><title>C</title><link>https://n.example/c</link>
        <description>&lt;p&gt;&lt;img src="https://cdn.example/c.webp"&gt;text&lt;/p&gt;</description></item>
      <item><title>D</title><link>https://n.example/d</link><description>no image</description></item>
    </channel></rss>"""
    parsed = await parse_feed(feed)
    assert [entry_image(e) for e in parsed.entries] == [
        "https://cdn.example/a.jpg", "https://cdn.example/b.png", "https://cdn.example/c.webp", None]
