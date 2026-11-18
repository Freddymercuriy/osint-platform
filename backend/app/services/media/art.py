"""Hodisa illyustratsiyasi (16:9, 1280×720) — tashqi servis va kalitsiz, Pillow + numpy bilan chiziladi.

Uslub — qorong'i "editorial" muqova, hamma rubrikada bir xil til:
- rubrika rangidagi diagonal gradient va motiv ortidagi yumshoq nur;
- orqa naqsh: tarmoq yulduzlari, mikrosxema izlari, radar halqalari, perspektiv to'r yoki bokeh (rubrikaga mos,
  urug'dan tanlanadi), motiv atrofida xiralashadi;
- mavzu motivi — chiziqli ikonka (qalqon, qulf, ma'lumotlar bazasi, qarmoq, neyron tarmoq, antenna ...) nur bilan,
  shisha disk ustida;
- Markaziy Osiyo hodisasida — pastda davlat bayrog'i ranglaridagi ingichka chiziq; vinyetka va yengil donadorlik.
Matn, raqam, logotip va odam tasviri yo'q (soxta "foto" emas — ochiq ko'rinib turgan illyustratsiya).

Har hodisa — o'z rasmi: naqsh, ikonka joyi, gradient burchagi va nuqtalar urug'dan (hodisa ID) olinadi; bir urug' —
doim bir xil rasm. Hamma geometriya 2x o'lchamda chiziladi va kichraytiriladi (Pillow chiziqlarni silliqlamaydi).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1280, 720
SS = 2  # supersampling
WHITE = (238, 244, 250)

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Palette:
    base: Color  # eng to'q
    mid: Color
    accent: Color
    accent2: Color


PALETTES: dict[str, Palette] = {
    "cyber": Palette((5, 12, 24), (10, 42, 60), (45, 212, 191), (56, 189, 248)),
    "vulnerability": Palette((18, 9, 10), (62, 22, 16), (251, 146, 60), (244, 63, 94)),
    "ai": Palette((11, 8, 28), (44, 22, 86), (167, 139, 250), (240, 171, 252)),
    "tech": Palette((6, 13, 28), (17, 38, 76), (96, 165, 250), (34, 211, 238)),
    "telecom": Palette((4, 17, 22), (8, 50, 62), (34, 211, 238), (163, 230, 53)),
    "economy": Palette((5, 17, 13), (12, 50, 35), (52, 211, 153), (250, 204, 21)),
    "politics": Palette((11, 14, 21), (34, 40, 56), (203, 213, 225), (251, 191, 36)),
}
FLAG_COLORS: dict[str, list[Color]] = {
    "UZ": [(0, 153, 181), (245, 245, 245), (30, 181, 58)],
    "KZ": [(0, 175, 202), (254, 197, 12)],
    "KG": [(232, 17, 45), (255, 239, 0)],
    "TJ": [(204, 0, 0), (245, 245, 245), (0, 102, 0)],
    "TM": [(0, 132, 61), (200, 16, 46), (245, 245, 245)],
}
PATTERNS: dict[str, tuple[str, ...]] = {
    "cyber": ("constellation", "circuit", "grid"),
    "vulnerability": ("circuit", "radar", "constellation"),
    "ai": ("constellation", "bokeh"),
    "tech": ("circuit", "grid"),
    "telecom": ("waves", "constellation"),
    "economy": ("grid", "bokeh"),
    "politics": ("bokeh", "grid"),
}


@dataclass(frozen=True)
class ArtSpec:
    seed: int
    rubric: str = "cyber"
    motif: str = "shield"
    countries: tuple[str, ...] = ()


# ------------------------------------------------------------------ yordamchilar
def _rgba(c: Color, a: float) -> tuple[int, int, int, int]:
    return (c[0], c[1], c[2], max(0, min(255, int(a))))


def _mix(a: Color, b: Color, t: float) -> Color:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def _background(p: Palette, rng: random.Random, focus: tuple[float, float]) -> np.ndarray:
    """Diagonal gradient + motiv ortida nur + vinyetka (float32, 0–255)."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = math.radians(rng.uniform(20, 70))
    t = ((x / W) * math.cos(ang) + (y / H) * math.sin(ang)) / (math.cos(ang) + math.sin(ang))
    t = np.clip(t, 0, 1)[..., None]
    base, mid = np.array(p.base, np.float32), np.array(p.mid, np.float32)
    img = base * (1 - t) + mid * t
    fx, fy = focus[0] * W, focus[1] * H
    d = np.sqrt(((x - fx) / (0.55 * W)) ** 2 + ((y - fy) / (0.75 * H)) ** 2)[..., None]
    glow = np.clip(1 - d, 0, 1) ** 2
    img = img + glow * (np.array(p.accent, np.float32) * 0.22)
    cx, cy = W / 2, H / 2
    v = np.sqrt(((x - cx) / (0.72 * W)) ** 2 + ((y - cy) / (0.72 * H)) ** 2)[..., None]
    img = img * np.clip(1.08 - 0.5 * v ** 2, 0.35, 1.0)
    return img


def _fade(x: float, y: float, focus: tuple[float, float], inner: float, outer: float) -> float:
    """Motiv atrofida naqsh xiralashadi (0.12 … 1)."""
    d = math.hypot(x - focus[0], y - focus[1])
    if d <= inner:
        return 0.12
    if d >= outer:
        return 1.0
    return 0.12 + 0.88 * (d - inner) / (outer - inner)


# ------------------------------------------------------------------ naqshlar (2x qatlamda)
def _constellation(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    n = rng.randint(55, 85)
    pts = [(rng.uniform(-0.03, 1.03) * W * SS, rng.uniform(-0.03, 1.03) * H * SS) for _ in range(n)]
    f = (focus[0] * W * SS, focus[1] * H * SS)
    inner, outer = 0.16 * W * SS, 0.42 * W * SS
    link = 0.17 * W * SS
    for i, a in enumerate(pts):
        near = sorted(((math.dist(a, b), j) for j, b in enumerate(pts) if j != i))[:3]
        for dist, j in near:
            if j < i or dist > link:
                continue
            b = pts[j]
            k = _fade((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, f, inner, outer) * (1 - dist / link)
            d.line([a, b], fill=_rgba(p.accent, 30 + 90 * k), width=2 * SS // 2 + 1)
    for a in pts:
        k = _fade(a[0], a[1], f, inner, outer)
        r = rng.uniform(2.0, 4.6) * SS
        col = p.accent2 if rng.random() < 0.25 else p.accent
        d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=_rgba(col, 60 + 150 * k))


def _circuit(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    f = (focus[0] * W * SS, focus[1] * H * SS)
    inner, outer = 0.2 * W * SS, 0.45 * W * SS
    step = 28 * SS
    for _ in range(rng.randint(20, 30)):
        side = rng.choice("lrtb")
        if side in "lr":
            x = 0 if side == "l" else W * SS
            y = round(rng.uniform(0.05, 0.95) * H * SS / step) * step
            dx, dy = (1 if side == "l" else -1), 0
        else:
            y = 0 if side == "t" else H * SS
            x = round(rng.uniform(0.05, 0.95) * W * SS / step) * step
            dx, dy = 0, (1 if side == "t" else -1)
        pts = [(x, y)]
        for _seg in range(rng.randint(2, 4)):
            length = rng.randint(2, 7) * step
            x, y = x + dx * length, y + dy * length
            pts.append((x, y))
            if rng.random() < 0.7:  # 45° burilish
                turn = rng.choice((-1, 1))
                if dx:
                    dy2 = turn
                    x, y = x + dx * step, y + dy2 * step
                else:
                    dx2 = turn
                    x, y = x + dx2 * step, y + dy * step
                pts.append((x, y))
        k = _fade(x, y, f, inner, outer)
        col = p.accent2 if rng.random() < 0.3 else p.accent
        d.line(pts, fill=_rgba(col, 35 + 110 * k), width=2 * SS, joint="curve")
        r = 5 * SS
        d.ellipse([x - r, y - r, x + r, y + r], outline=_rgba(col, 60 + 150 * k), width=2 * SS)


def _radar(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    cx, cy = focus[0] * W * SS, focus[1] * H * SS
    r = 0.36 * H * SS
    i = 0
    while r < 1.25 * W * SS:
        a = max(18, 120 - i * 16)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_rgba(p.accent, a), width=2 * SS)
        r += rng.uniform(0.11, 0.16) * H * SS
        i += 1
    start = rng.uniform(0, 360)
    for k in range(18):  # aylanuvchi "nur" sektori
        d.pieslice([cx - 1.1 * W * SS, cy - 1.1 * W * SS, cx + 1.1 * W * SS, cy + 1.1 * W * SS],
                   start + k * 1.6, start + (k + 1) * 1.6, fill=_rgba(p.accent, 3 + k * 1.6))
    for ang in (0, 90):
        rad = math.radians(ang + start / 8)
        dx, dy = math.cos(rad) * W * SS, math.sin(rad) * W * SS
        d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=_rgba(p.accent, 28), width=SS)


def _waves(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    cx, cy = focus[0] * W * SS, focus[1] * H * SS
    r = 0.34 * H * SS
    for i in range(9):
        a = max(16, 130 - i * 13)
        for start in (-38, 142):
            d.arc([cx - r, cy - r, cx + r, cy + r], start, start + 76, fill=_rgba(p.accent, a), width=3 * SS)
        r += rng.uniform(0.09, 0.13) * H * SS
    _constellation_light(d, p, rng, focus)


def _constellation_light(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    f = (focus[0] * W * SS, focus[1] * H * SS)
    for _ in range(rng.randint(25, 40)):
        x, y = rng.uniform(0, W * SS), rng.uniform(0, H * SS)
        k = _fade(x, y, f, 0.18 * W * SS, 0.45 * W * SS)
        r = rng.uniform(1.6, 3.6) * SS
        d.ellipse([x - r, y - r, x + r, y + r], fill=_rgba(p.accent2, 40 + 120 * k))


def _grid(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    horizon = rng.uniform(0.6, 0.68) * H * SS
    vx = rng.uniform(0.35, 0.65) * W * SS
    for i in range(-14, 15):  # "pol"ga tushuvchi chiziqlar
        x_bottom = vx + i * 0.11 * W * SS
        d.line([(vx, horizon), (x_bottom, H * SS)], fill=_rgba(p.accent, 22 + 26 * (1 - abs(i) / 14)), width=SS)
    y, gap = horizon, 6 * SS
    while y < H * SS:
        a = 18 + 70 * (y - horizon) / (H * SS - horizon)
        d.line([(0, y), (W * SS, y)], fill=_rgba(p.accent, a), width=SS)
        gap *= 1.32
        y += gap
    _constellation_light(d, p, rng, focus)


def _bokeh(d: ImageDraw.ImageDraw, p: Palette, rng: random.Random, focus: tuple[float, float]) -> None:
    for _ in range(rng.randint(14, 22)):
        x, y = rng.uniform(0, W * SS), rng.uniform(0, H * SS)
        r = rng.uniform(18, 110) * SS
        col = p.accent if rng.random() < 0.6 else p.accent2
        d.ellipse([x - r, y - r, x + r, y + r], fill=_rgba(col, rng.uniform(10, 34)))


PATTERN_DRAWERS: dict[str, Callable] = {
    "constellation": _constellation, "circuit": _circuit, "radar": _radar, "waves": _waves, "grid": _grid,
    "bokeh": _bokeh,
}


# ------------------------------------------------------------------ ikonkalar ([-1, 1] birlik qutida, y pastga)
class Pen:
    def __init__(self, d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color, accent, width: float):
        self.d, self.cx, self.cy, self.s = d, cx, cy, s
        self.color, self.accent, self.w = color, accent, max(2, int(width))

    def p(self, x: float, y: float) -> tuple[float, float]:
        return (self.cx + x * self.s, self.cy + y * self.s)

    def box(self, x0: float, y0: float, x1: float, y1: float) -> list[float]:
        a, b = self.p(x0, y0), self.p(x1, y1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]

    def line(self, pts, *, width: float = 1.0, fill=None, closed: bool = False) -> None:
        q = [self.p(x, y) for x, y in pts]
        if closed:
            q = q + q[:2]
        self.d.line(q, fill=fill or self.color, width=max(2, int(self.w * width)), joint="curve")
        r = self.w * width / 2  # uchlarni yumaloqlash
        for x, y in (q[0], q[-1]) if not closed else ():
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill or self.color)

    def rrect(self, x0, y0, x1, y1, r: float, *, fill=None, width: float = 1.0, outline: bool = True) -> None:
        self.d.rounded_rectangle(self.box(x0, y0, x1, y1), radius=r * self.s, fill=fill,
                                 outline=self.color if outline else None, width=max(2, int(self.w * width)))

    def circle(self, x, y, r, *, fill=None, width: float = 1.0, outline: bool = True) -> None:
        self.d.ellipse(self.box(x - r, y - r, x + r, y + r), fill=fill, outline=self.color if outline else None,
                       width=max(2, int(self.w * width)))

    def arc(self, x, y, r, start, end, *, width: float = 1.0, fill=None) -> None:
        self.d.arc(self.box(x - r, y - r, x + r, y + r), start, end, fill=fill or self.color,
                   width=max(2, int(self.w * width)))

    def poly(self, pts, *, fill) -> None:
        self.d.polygon([self.p(x, y) for x, y in pts], fill=fill)


def _quad(a, c, b, n: int = 14) -> list[tuple[float, float]]:
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t ** 2 * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t ** 2 * b[1]) for t in (i / n for i in range(n + 1))]


def _shield_path() -> list[tuple[float, float]]:
    right = [(0.0, -0.95), (0.78, -0.68), (0.78, 0.0)] + _quad((0.78, 0.0), (0.74, 0.62), (0.0, 0.98))[1:]
    left = [(-x, y) for x, y in reversed(right[1:-1])]
    return right + left


def _i_shield(pen: Pen) -> None:
    pen.line(_shield_path(), closed=True)
    pen.line([(-0.3, 0.02), (-0.06, 0.27), (0.34, -0.2)], width=0.9, fill=pen.accent)


def _i_shield_check(pen: Pen) -> None:
    pen.line(_shield_path(), closed=True)
    pen.line([(-0.32, 0.0), (-0.07, 0.26), (0.36, -0.24)], width=1.1)


def _i_shield_crack(pen: Pen) -> None:
    pen.line(_shield_path(), closed=True)
    pen.line([(0.06, -0.72), (-0.14, -0.3), (0.1, -0.02), (-0.1, 0.38), (0.04, 0.72)], width=0.9, fill=pen.accent)


def _i_lock(pen: Pen) -> None:
    pen.rrect(-0.62, -0.08, 0.62, 0.9, 0.16)
    pen.arc(0, -0.42, 0.4, 180, 360)
    pen.line([(-0.4, -0.42), (-0.4, -0.1)])
    pen.line([(0.4, -0.42), (0.4, -0.1)])
    pen.circle(0, 0.3, 0.1, fill=pen.accent, outline=False)
    pen.line([(0, 0.34), (0, 0.6)], fill=pen.accent)


def _i_database(pen: Pen) -> None:
    pen.d.ellipse(pen.box(-0.7, -0.95, 0.7, -0.55), outline=pen.color, width=pen.w)
    pen.line([(-0.7, -0.75), (-0.7, 0.62)])
    pen.line([(0.7, -0.75), (0.7, 0.62)])
    for y in (-0.28, 0.17, 0.62):
        pen.d.arc(pen.box(-0.7, y - 0.2, 0.7, y + 0.2), 0, 180, fill=pen.color, width=pen.w)
    for x, y, r in ((0.98, 0.42, 0.1), (1.12, 0.78, 0.075)):  # oqib chiqayotgan tomchilar
        pen.circle(x, y, r, fill=pen.accent, outline=False)
        pen.poly([(x - r * 0.92, y - r * 0.35), (x, y - r * 2.6), (x + r * 0.92, y - r * 0.35)], fill=pen.accent)


def _i_bug(pen: Pen) -> None:
    pen.d.ellipse(pen.box(-0.42, -0.3, 0.42, 0.86), outline=pen.color, width=pen.w)
    pen.d.ellipse(pen.box(-0.25, -0.64, 0.25, -0.26), outline=pen.color, width=pen.w)
    pen.line([(0, -0.26), (0, 0.84)], width=0.8)
    for sx in (-1, 1):
        pen.line([(0.42 * sx, -0.04), (0.82 * sx, -0.26)])
        pen.line([(0.44 * sx, 0.27), (0.88 * sx, 0.27)])
        pen.line([(0.4 * sx, 0.57), (0.8 * sx, 0.82)])
        pen.line([(0.1 * sx, -0.6), (0.34 * sx, -0.93)], width=0.8)
    pen.circle(-0.16, 0.2, 0.07, fill=pen.accent, outline=False)
    pen.circle(0.18, 0.5, 0.07, fill=pen.accent, outline=False)


def _i_key(pen: Pen) -> None:
    rot = math.radians(-32)

    def r(x: float, y: float) -> tuple[float, float]:
        return (x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot))

    hx, hy = r(-0.52, 0.0)
    pen.circle(hx, hy, 0.34)
    pen.circle(hx, hy, 0.1, fill=pen.accent, outline=False)
    pen.line([r(-0.18, 0.0), r(0.88, 0.0)])
    pen.line([r(0.56, 0.0), r(0.56, 0.3)])
    pen.line([r(0.78, 0.0), r(0.78, 0.22)])


def _i_hook(pen: Pen) -> None:
    pen.rrect(-1.0, -0.4, 0.28, 0.5, 0.06)
    pen.line([(-1.0, -0.4), (-0.36, 0.1), (0.28, -0.4)])
    pen.line([(0.72, -0.98), (0.72, 0.5)], width=0.9, fill=pen.accent)
    pen.arc(0.53, 0.5, 0.19, 0, 180, width=0.9, fill=pen.accent)
    pen.line([(0.34, 0.52), (0.34, 0.3), (0.46, 0.4)], width=0.9, fill=pen.accent)
    pen.circle(0.72, -0.98, 0.07, fill=None, width=0.7)


def _i_envelope(pen: Pen) -> None:
    pen.rrect(-0.88, -0.58, 0.88, 0.58, 0.08)
    pen.line([(-0.88, -0.58), (0, 0.08), (0.88, -0.58)])
    pen.line([(-0.88, 0.58), (-0.28, 0.0)], width=0.7)
    pen.line([(0.88, 0.58), (0.28, 0.0)], width=0.7)


def _i_card(pen: Pen) -> None:
    pen.rrect(-0.9, -0.55, 0.72, 0.5, 0.1)
    pen.d.rectangle(pen.box(-0.9, -0.32, 0.72, -0.16), fill=_rgba(pen.color, 150))
    pen.rrect(-0.7, 0.02, -0.38, 0.24, 0.04, width=0.7)
    tri = [(0.55, 0.12), (0.98, 0.86), (0.12, 0.86)]
    pen.poly(tri, fill=pen.accent)
    pen.line([(0.55, 0.36), (0.55, 0.62)], width=0.8, fill=(20, 20, 24, 255))
    pen.circle(0.55, 0.74, 0.04, fill=(20, 20, 24, 255), outline=False)


def _i_eye(pen: Pen) -> None:
    pen.arc(0, 0.62, 1.02, 217, 323)
    pen.arc(0, -0.62, 1.02, 37, 143)
    pen.circle(0, 0, 0.32)
    pen.circle(0, 0, 0.13, fill=pen.accent, outline=False)


def _i_server(pen: Pen) -> None:
    for y0 in (-0.86, -0.25, 0.36):
        pen.rrect(-0.76, y0, 0.66, y0 + 0.5, 0.08)
        pen.circle(-0.52, y0 + 0.25, 0.05, fill=pen.accent, outline=False)
        pen.circle(-0.34, y0 + 0.25, 0.05, fill=pen.accent, outline=False)
        pen.line([(0.12, y0 + 0.25), (0.46, y0 + 0.25)], width=0.7)
    pen.poly([(0.86, -0.42), (0.6, 0.06), (0.8, 0.06), (0.62, 0.52), (1.02, -0.04), (0.82, -0.04), (1.0, -0.42)],
             fill=pen.accent)


def _stadium(cx, cy, length, radius, ang) -> list[tuple[float, float]]:
    pts = []
    c, s = math.cos(ang), math.sin(ang)
    for end, a0 in ((length / 2, -90), (-length / 2, 90)):
        for k in range(13):
            a = math.radians(a0 + k * 15)
            x, y = end + radius * math.cos(a), radius * math.sin(a)
            pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def _i_broken_link(pen: Pen) -> None:
    ang = math.radians(-45)
    pen.line(_stadium(-0.4, 0.4, 0.62, 0.24, ang), closed=True)
    pen.line(_stadium(0.4, -0.4, 0.62, 0.24, ang), closed=True)
    for (x0, y0), (x1, y1) in (((-0.1, -0.12), (-0.28, -0.42)), ((0.12, 0.1), (0.42, 0.28)),
                               ((-0.02, 0.0), (0.06, 0.08))):
        pen.line([(x0, y0), (x1, y1)], width=0.8, fill=pen.accent)


def _i_antenna(pen: Pen) -> None:
    pen.line([(0, -0.42), (-0.4, 0.95)])
    pen.line([(0, -0.42), (0.4, 0.95)])
    pen.line([(-0.24, 0.4), (0.24, 0.4), (-0.32, 0.7), (0.32, 0.7)], width=0.7)
    pen.line([(-0.13, 0.02), (0.13, 0.02)], width=0.7)
    pen.circle(0, -0.55, 0.1, fill=pen.accent, outline=False)
    for r in (0.36, 0.64):
        pen.arc(0, -0.55, r, -42, 42, width=0.8, fill=pen.accent)
        pen.arc(0, -0.55, r, 138, 222, width=0.8, fill=pen.accent)


def _i_gavel(pen: Pen) -> None:
    head = _stadium(-0.18, -0.36, 0.62, 0.2, math.radians(-45))
    pen.line(head, closed=True)
    pen.line([(0.02, -0.16), (0.74, 0.56)], width=1.1)
    pen.rrect(-0.88, 0.62, 0.22, 0.86, 0.06, fill=_rgba(pen.accent, 255), outline=False)


def _i_document(pen: Pen) -> None:
    pen.line([(-0.6, -0.92), (0.32, -0.92), (0.64, -0.6), (0.64, 0.92), (-0.6, 0.92)], closed=True)
    pen.line([(0.32, -0.92), (0.32, -0.6), (0.64, -0.6)], width=0.8)
    for y, x1 in ((-0.32, 0.4), (-0.06, 0.4), (0.2, 0.4), (0.46, 0.05)):
        pen.line([(-0.36, y), (x1, y)], width=0.7)
    pen.circle(0.58, 0.7, 0.24, fill=pen.accent, outline=False)
    pen.line([(0.47, 0.7), (0.56, 0.79), (0.71, 0.6)], width=0.6, fill=(20, 20, 24, 255))


def _i_magnifier(pen: Pen) -> None:
    pen.circle(-0.16, -0.16, 0.56)
    pen.line([(0.24, 0.24), (0.82, 0.82)], width=1.5)
    pen.line([(-0.46, 0.02), (-0.28, -0.18), (-0.08, -0.04), (0.14, -0.34)], width=0.8, fill=pen.accent)


def _i_neural(pen: Pen) -> None:
    layers = [(-0.82, (-0.5, 0.0, 0.5)), (0.0, (-0.72, -0.24, 0.24, 0.72)), (0.82, (-0.5, 0.0, 0.5))]
    for (x0, ys0), (x1, ys1) in zip(layers, layers[1:], strict=False):
        for y0 in ys0:
            for y1 in ys1:
                pen.line([(x0, y0), (x1, y1)], width=0.45, fill=_rgba(pen.color, 150))
    for x, ys in layers:
        for y in ys:
            pen.circle(x, y, 0.11, fill=pen.accent, width=0.7)


def _i_chip(pen: Pen) -> None:
    pen.rrect(-0.56, -0.56, 0.56, 0.56, 0.1)
    pen.rrect(-0.24, -0.24, 0.24, 0.24, 0.05, fill=_rgba(pen.accent, 255), outline=False)
    for k in (-0.33, -0.11, 0.11, 0.33):
        for a, b in (((k, -0.56), (k, -0.84)), ((k, 0.56), (k, 0.84)), ((-0.56, k), (-0.84, k)),
                     ((0.56, k), (0.84, k))):
            pen.line([a, b], width=0.7)


def _i_chart(pen: Pen) -> None:
    pen.line([(-0.86, -0.82), (-0.86, 0.8), (0.88, 0.8)])
    for x, top in ((-0.58, 0.32), (-0.24, 0.08), (0.1, 0.18), (0.44, -0.18)):
        pen.rrect(x, top, x + 0.2, 0.74, 0.03, fill=_rgba(pen.color, 70), outline=False)
    pen.line([(-0.66, 0.2), (-0.26, -0.12), (0.06, 0.02), (0.62, -0.58)], width=1.0, fill=pen.accent)
    pen.poly([(0.74, -0.7), (0.44, -0.62), (0.66, -0.42)], fill=pen.accent)


def _i_building(pen: Pen) -> None:
    pen.line([(-0.92, -0.42), (0, -0.92), (0.92, -0.42)], closed=True)
    pen.line([(-0.86, -0.32), (0.86, -0.32)], width=0.8)
    for x in (-0.6, -0.2, 0.2, 0.6):
        pen.line([(x, -0.2), (x, 0.58)], width=1.2)
    pen.line([(-0.9, 0.7), (0.9, 0.7)])
    pen.line([(-1.0, 0.88), (1.0, 0.88)])
    pen.circle(0, -0.6, 0.07, fill=pen.accent, outline=False)


def _i_globe(pen: Pen) -> None:
    pen.circle(0, 0, 0.86)
    pen.d.ellipse(pen.box(-0.38, -0.86, 0.38, 0.86), outline=pen.color, width=int(pen.w * 0.8))
    pen.line([(0, -0.86), (0, 0.86)], width=0.8)
    for y in (-0.42, 0.0, 0.42):
        half = math.sqrt(max(0.0, 0.86 ** 2 - y ** 2))
        pen.line([(-half, y), (half, y)], width=0.8)
    pen.circle(0.5, -0.5, 0.08, fill=pen.accent, outline=False)


def _i_phone(pen: Pen) -> None:
    pen.rrect(-0.46, -0.92, 0.46, 0.92, 0.14)
    pen.line([(-0.12, -0.76), (0.12, -0.76)], width=0.8)
    pen.circle(0, 0.74, 0.06, fill=pen.accent, outline=False)
    pen.line([(-0.22, -0.2), (0.22, -0.2)], width=0.6, fill=pen.accent)
    pen.line([(-0.22, 0.05), (0.12, 0.05)], width=0.6, fill=pen.accent)


def _i_browser(pen: Pen) -> None:
    pen.rrect(-0.92, -0.72, 0.92, 0.76, 0.08)
    pen.line([(-0.92, -0.42), (0.92, -0.42)], width=0.8)
    for x in (-0.76, -0.62, -0.48):
        pen.circle(x, -0.57, 0.045, fill=pen.color, outline=False)
    pen.line([(-0.36, -0.28), (-0.06, 0.06), (-0.28, 0.26), (0.12, 0.64)], width=0.9, fill=pen.accent)


ICONS: dict[str, Callable[[Pen], None]] = {
    "shield": _i_shield, "shield_check": _i_shield_check, "shield_crack": _i_shield_crack, "lock": _i_lock,
    "database": _i_database, "bug": _i_bug, "key": _i_key, "hook": _i_hook, "envelope": _i_envelope,
    "card": _i_card, "eye": _i_eye, "server": _i_server, "broken_link": _i_broken_link, "antenna": _i_antenna,
    "gavel": _i_gavel, "document": _i_document, "magnifier": _i_magnifier, "neural": _i_neural, "chip": _i_chip,
    "chart": _i_chart, "building": _i_building, "globe": _i_globe, "phone": _i_phone, "browser": _i_browser,
}


# ------------------------------------------------------------------ yig'ish
def _to_layer(draw_fn: Callable[[ImageDraw.ImageDraw], None]) -> Image.Image:
    big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(big, "RGBA"))
    return big.resize((W, H), Image.Resampling.LANCZOS)


def render(spec: ArtSpec) -> Image.Image:
    """Illyustratsiya (RGB, 1280×720)."""
    rng = random.Random(spec.seed)
    pal = PALETTES.get(spec.rubric, PALETTES["cyber"])
    fx = rng.choice((0.5, 0.5, 0.64, 0.36))
    fy = rng.uniform(0.47, 0.53)
    focus = (fx, fy)

    bg = _background(pal, rng, focus)
    canvas = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    pattern = rng.choice(PATTERNS.get(spec.rubric, ("constellation",)))
    layer = _to_layer(lambda d: PATTERN_DRAWERS[pattern](d, pal, rng, focus))
    if pattern == "bokeh":
        layer = layer.filter(ImageFilter.GaussianBlur(10))
    canvas = Image.alpha_composite(canvas, layer)

    # shisha disk va ikonka
    size = 0.25 * H * SS
    cx, cy = fx * W * SS, fy * H * SS
    plate = rng.choice(("circle", "circle", "square", "none"))

    def draw_plate(d: ImageDraw.ImageDraw) -> None:
        r = size * 1.55
        box = [cx - r, cy - r, cx + r, cy + r]
        if plate == "circle":
            d.ellipse(box, fill=(255, 255, 255, 12), outline=_rgba(pal.accent, 70), width=2 * SS)
            r2 = r * 1.16
            d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=_rgba(pal.accent, 26), width=SS)
        elif plate == "square":
            d.rounded_rectangle(box, radius=r * 0.28, fill=(255, 255, 255, 12), outline=_rgba(pal.accent, 70),
                                width=2 * SS)

    if plate != "none":
        canvas = Image.alpha_composite(canvas, _to_layer(draw_plate))

    icon_fn = ICONS.get(spec.motif, _i_shield)
    icon = _to_layer(lambda d: icon_fn(Pen(d, cx, cy, size, _rgba(WHITE, 255), _rgba(pal.accent, 255),
                                           width=size * 0.075)))
    alpha = icon.getchannel("A")
    glow_a = alpha.filter(ImageFilter.GaussianBlur(16)).point(lambda v: min(255, int(v * 1.6)))
    glow = Image.new("RGBA", (W, H), _rgba(pal.accent, 255))
    glow.putalpha(glow_a)
    canvas = Image.alpha_composite(canvas, glow)
    canvas = Image.alpha_composite(canvas, icon)

    # Markaziy Osiyo: bayroq ranglaridagi ingichka chiziq (pastki o'ng burchakda — chapda karta yorlig'i turadi)
    flags = [c for c in spec.countries if c in FLAG_COLORS]
    if flags:
        colors = FLAG_COLORS[flags[0]]
        seg, y0 = 54, H - 44
        x0 = W - 48 - seg * len(colors)
        d = ImageDraw.Draw(canvas, "RGBA")
        for i, col in enumerate(colors):
            d.rectangle([x0 + i * seg, y0, x0 + (i + 1) * seg - 4, y0 + 5], fill=_rgba(col, 230))

    # yengil donadorlik
    arr = np.asarray(canvas.convert("RGB")).astype(np.int16)
    noise = np.random.default_rng(spec.seed).normal(0, 3.2, (H, W, 1)).astype(np.int16)
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def render_fallback(rubric: str) -> Image.Image:
    """Zaxira: illyustratsiya chizilmasa — rubrika gradienti (urug'siz, oddiy yo'l; xato ehtimoli juda kichik)."""
    pal = PALETTES.get(rubric, PALETTES["cyber"])
    img = Image.new("RGB", (W, H), pal.base)
    d = ImageDraw.Draw(img)
    for i in range(H):
        d.line([(0, i), (W, i)], fill=_mix(pal.base, pal.mid, i / H))
    d.ellipse([W / 2 - 150, H / 2 - 150, W / 2 + 150, H / 2 + 150], outline=pal.accent, width=6)
    return img
