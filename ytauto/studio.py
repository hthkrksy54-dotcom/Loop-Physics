"""Keynote-style motion graphics for the money channel: a black stage, crisp type, figures in colour gradients,
smooth eased animation and glowing charts that draw themselves.

A scene is a list of parts painted in order onto a black frame. Most parts are elements (`El`): a pre-rendered
RGBA image that rises in with a fading blur and leaves with the scene. Live parts change every frame: counters,
a chart line drawing itself, growing bars. The whole frame drifts in very slowly (a camera push) so long
explanations never look frozen.

Scenes (econ scripts use them as "show": {"type": ...}): title, number, line, bars, columns (alias coins),
compare, note.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

try:  # OpenCV makes the camera push ~8x faster than Pillow
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

FPS = 30
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FACES = {"display": "InterDisplay-Bold.ttf", "headline": "InterDisplay-SemiBold.ttf",
         "medium": "InterDisplay-Medium.ttf", "text": "Inter-Medium.ttf", "label": "Inter-SemiBold.ttf"}
TRACK = {"display": -0.025, "headline": -0.015, "medium": -0.01, "text": 0.0, "label": 0.0}
RAQM = features.check("raqm")

WHITE = (245, 245, 247)
SOFT = (210, 210, 215)
GRAY = (134, 134, 139)
DIM = (72, 72, 76)
CARD = (24, 24, 27)
GRADIENTS = {
    "red": [(255, 179, 64), (255, 95, 87), (255, 55, 125)],      # amber → coral → pink: money lost
    "green": [(52, 211, 120), (64, 220, 200), (100, 200, 255)],  # green → teal → sky: growth
    "blue": [(64, 156, 255), (110, 108, 245), (191, 90, 242)],   # blue → indigo → violet: neutral
    "purple": [(191, 90, 242), (255, 70, 150)],
    "gold": [(255, 224, 102), (255, 170, 40)],
    "gray": [(110, 110, 116), (150, 150, 156)],
}
IN, OUT = 0.85, 0.42                # reveal / leave durations
BLUR = [0, 1.5, 3.5, 7.0, 12.0]     # blur radii of the reveal


def clamp(p: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if p < lo else hi if p > hi else p


def ease_out(p: float) -> float:
    p = clamp(p)
    return 1 - (1 - p) ** 3


def ease_expo(p: float) -> float:
    p = clamp(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def smooth(p: float) -> float:
    p = clamp(p)
    return p * p * (3 - 2 * p)


def ease_inout(p: float) -> float:
    p = clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


# ---------------------------------------------------------------- type


@lru_cache(maxsize=None)
def font(face: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / FACES[face]), int(size))


def width(text: str, face: str, size: int) -> float:
    f = font(face, size)
    return f.getlength(text) + TRACK[face] * size * max(0, len(text) - 1)


def _line_mask(text: str, face: str, size: int, tnum: bool = False) -> Image.Image:
    """One line of text as an alpha mask, with the face's tracking (and tabular figures for counters)."""
    f = font(face, size)
    feats = ["tnum"] if tnum and RAQM else None
    tr = TRACK[face] * size
    asc, desc = f.getmetrics()
    pad = int(size * 0.12)
    full = f.getlength(text, features=feats)
    img = Image.new("L", (int(full + tr * max(0, len(text) - 1)) + 2 * pad + 2, asc + desc + 2 * pad))
    d = ImageDraw.Draw(img)
    if not tr:
        d.text((pad, pad), text, font=f, fill=255, features=feats)
        return img
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        x = f.getlength(text[:i + 1], features=feats) - f.getlength(ch, features=feats) + tr * i
        d.text((pad + x, pad), ch, font=f, fill=255, features=feats)
    return img


def text_mask(lines: list[str] | str, face: str, size: int, align: str = "center", leading: float = 1.12,
              tnum: bool = False) -> Image.Image:
    lines = [lines] if isinstance(lines, str) else lines
    masks = [_line_mask(t, face, size, tnum) for t in lines]
    step = int(size * leading)
    pad = int(size * 0.12)
    w = max(m.width for m in masks)
    h = step * (len(masks) - 1) + masks[-1].height
    out = Image.new("L", (w, h))
    for i, m in enumerate(masks):
        x = 0 if align == "left" else (w - m.width) // 2 if align == "center" else w - m.width
        out.paste(m, (x, i * step), m)
    out.info["pad"] = pad
    return out


def wrap(text: str, face: str, size: int, max_w: float) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            test = f"{cur} {word}".strip()
            if cur and width(test, face, size) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = test
        lines.append(cur)
    return lines


def fit(text: str, face: str, size: int, max_w: float, max_lines: int = 2, min_size: int = 20) -> tuple[list[str], int]:
    """Wrap text into at most max_lines lines, shrinking the size until every line fits."""
    while True:
        lines = wrap(text, face, size, max_w)
        if (len(lines) <= max_lines and all(width(t, face, size) <= max_w for t in lines)) or size <= min_size:
            return lines, size
        size = int(size * 0.94)


@lru_cache(maxsize=64)
def gradient(w: int, h: int, colors: tuple, angle: float = 18.0) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    t = xx * math.cos(a) + yy * math.sin(a)
    t = (t - t.min()) / max(1e-6, float(t.max() - t.min()))
    stops = np.linspace(0, 1, len(colors))
    rgb = np.stack([np.interp(t, stops, [c[k] for c in colors]) for k in range(3)], -1)
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def colorize(mask: Image.Image, fill) -> Image.Image:
    """Mask → RGBA in a solid colour or a gradient (list of colours or a GRADIENTS name)."""
    if isinstance(fill, str):
        fill = GRADIENTS[fill]
    if isinstance(fill, list):
        rgb = gradient(mask.width, mask.height, tuple(fill)).copy()
    else:
        rgb = Image.new("RGB", mask.size, fill)
    img = rgb.convert("RGBA")
    img.putalpha(mask)
    return img


def text(lines, face: str, size: int, fill=WHITE, align: str = "center", tnum: bool = False) -> Image.Image:
    return colorize(text_mask(lines, face, size, align, tnum=tnum), fill)


@lru_cache(maxsize=32)
def glow(w: int, h: int, color: tuple, strength: float) -> Image.Image:
    """A soft coloured light (radial falloff, dithered against banding)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    a = strength * np.clip((np.exp(-r2 * 2.6) - math.exp(-2.6)) / (1 - math.exp(-2.6)), 0, 1) * 255  # 0 at the edge
    a += np.random.default_rng(w * 7 + h).uniform(-1.2, 1.2, a.shape)
    img = Image.new("RGBA", (w, h), color + (0,))
    img.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L"))
    return img


def rounded(w: int, h: int, r: float, fill=CARD, border: tuple | None = (255, 255, 255, 26), ss: int = 3) -> Image.Image:
    """Antialiased rounded rectangle (card)."""
    big = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill if len(fill) == 4 else fill + (255,),
                        outline=border, width=int(1.6 * ss) if border else 0)
    return big.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=4096)
def pill_mask(w: int, h: int, r: float) -> Image.Image:
    ss = 3
    big = Image.new("L", (max(1, w) * ss, max(1, h) * ss))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, max(1, w) * ss - 1, max(1, h) * ss - 1), min(r, w / 2, h / 2) * ss,
                                          fill=255)
    return big.resize((max(1, w), max(1, h)), Image.LANCZOS)


@lru_cache(maxsize=16)
def dot(r: int, color: tuple) -> Image.Image:
    """White dot with a coloured halo – the tip of a drawing line."""
    size = r * 8
    img = glow(size, size, color, 0.75).copy()
    core = Image.new("L", (size * 3, size * 3))
    ImageDraw.Draw(core).ellipse((size * 1.5 - r * 3, size * 1.5 - r * 3, size * 1.5 + r * 3, size * 1.5 + r * 3), fill=255)
    core = core.resize((size, size), Image.LANCZOS)
    img.alpha_composite(colorize(core, WHITE))
    return img


@lru_cache(maxsize=256)
def _lut(a64: int) -> list[int]:
    a = a64 / 64
    return [int(v * a + 0.5) for v in range(256)]


def paste(frame: Image.Image, img: Image.Image, x: float, y: float, alpha: float = 1.0) -> None:
    """Paste an RGBA image centred at (x, y) with an extra opacity."""
    pos = (int(round(x - img.width / 2)), int(round(y - img.height / 2)))
    if alpha >= 0.995:
        frame.paste(img, pos, img)
    elif alpha > 0.004:
        frame.paste(img, pos, img.getchannel("A").point(_lut(int(alpha * 64 + 0.5))))


# ---------------------------------------------------------------- parts


class El:
    """A pre-rendered element: rises in (fade + slide + unblur) at t0, leaves with the scene (or at `out`)."""

    def __init__(self, img: Image.Image | None, x: float, y: float, t0: float = 0.0, style: str = "rise",
                 out: float | None = None, dy: float | None = None, dur: float = IN):
        self.img, self.x, self.y, self.t0, self.style, self.out, self.dur = img, x, y, t0, style, out, dur
        h = img.height if img is not None else 100
        self.dy = dy if dy is not None else clamp(h * 0.12, 14, 44)
        self._blur: dict = {}

    def image(self, t: float) -> Image.Image:
        return self.img

    def blurred(self, img: Image.Image, level: int, key=None) -> Image.Image:
        if level <= 0:
            return img
        key = (key or id(img), level)
        if key not in self._blur:
            if len(self._blur) > 120:
                self._blur.clear()
            r = BLUR[level]
            pad = int(r * 2.5)
            big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
            big.paste(img, (pad, pad))
            self._blur[key] = big.filter(ImageFilter.GaussianBlur(r))
        return self._blur[key]

    def state(self, t: float, end: float) -> tuple[float, float, int] | None:
        if t < self.t0:
            return None
        p = (t - self.t0) / self.dur
        if self.style == "none":
            a, off, lv = 1.0, 0.0, 0
        else:
            e = ease_out(p)
            a = ease_out(p * 1.35)
            off = self.dy * (1 - e) if self.style == "rise" else 0.0
            lv = int(round((1 - e) * 4)) if self.style in ("rise", "blur") else 0
        leave = self.out if self.out is not None else end - OUT
        if t > leave:
            q = clamp((t - leave) / OUT)
            a *= 1 - smooth(q)
            off -= 12 * q
            lv = max(lv, int(round(q * 3)))
        return (a, off, lv) if a > 0.004 else None

    def settled(self, t: float, end: float) -> str | None:
        """"hidden" or "full" while the element does not change, None while it moves."""
        leave = self.out if self.out is not None else end - OUT
        if t < self.t0 or t >= leave + OUT:
            return "hidden"
        if t >= leave:
            return None
        return "full" if self.style == "none" or t >= self.t0 + self.dur else None

    def paint(self, frame: Image.Image, t: float, end: float) -> None:
        st = self.state(t, end)
        if st is None:
            return
        a, off, lv = st
        img = self.image(t)
        if img is not None:
            paste(frame, self.blurred(img, lv), self.x, self.y + off, a)


class Counter(El):
    """A number that counts from `a` to `b` (keeping the target's prefix, suffix and decimals)."""

    def __init__(self, target: str, start: float | None, face: str, size: int, fill, x: float, y: float,
                 t0: float, count: float = 1.6, anchor: str = "center", **kw):
        super().__init__(None, x, y, t0, **kw)
        self.parts = parse_number(target)
        self.face, self.size, self.fill, self.count, self.anchor = face, size, fill, count, anchor
        self.start = start
        self.final = text(minus(target), face, size, fill, tnum=True)
        self.dy = clamp(self.final.height * 0.1, 14, 40)
        self._cache: dict[str, Image.Image] = {}

    def string(self, t: float) -> str:
        if not self.parts or self.start is None:
            return ""
        pre, value, dec, suf = self.parts
        p = ease_expo((t - self.t0 - 0.1) / self.count)
        if p >= 1:
            return ""
        v = self.start + (value - self.start) * p
        num = f"{abs(v):,.{dec}f}" if abs(value) >= 1000 or abs(self.start) >= 1000 else f"{abs(v):.{dec}f}"
        return f"{pre}{'−' if v < 0 and round(abs(v), dec) > 0 else ''}{num}{suf}"

    def image(self, t: float) -> Image.Image:
        s = self.string(t)
        if not s:
            return self.final
        if s not in self._cache:
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[s] = text(s, self.face, self.size, self.fill, tnum=True)
        return self._cache[s]

    def paint(self, frame: Image.Image, t: float, end: float) -> None:
        st = self.state(t, end)
        if st is None:
            return
        a, off, lv = st
        img = self.blurred(self.image(t), lv, self.string(t) or "final")
        x = self.x
        if self.anchor == "left":
            x = self.x + img.width / 2
        paste(frame, img, x, self.y + off, a)


def minus(s: str) -> str:
    """A real minus sign instead of a hyphen in front of a figure."""
    return re.sub(r"(?<![\w])-(?=[\d$.])", "−", s)


_NUM = re.compile(r"^(?P<pre>[^\d−-]*?)(?P<sign>[−-]?)(?P<num>\d[\d,]*(?:\.\d+)?)(?P<suf>.*)$")


def parse_number(s: str) -> tuple[str, float, int, str] | None:
    m = _NUM.match(s.strip())
    if not m:
        return None
    num = m["num"].replace(",", "")
    dec = len(num.split(".")[1]) if "." in num else 0
    v = float(num) * (-1 if m["sign"] else 1)
    return m["pre"], v, dec, m["suf"]


def count_from(target: str, before: str | None) -> float | None:
    """Where a counter for `target` starts: at the previous figure if it has the same form, else at zero/one."""
    t = parse_number(target)
    if not t:
        return None
    if before:
        b = parse_number(before)
        if b and b[0] == t[0] and b[3] == t[3]:
            return b[1]
    if t[0].strip() in ("×", "x"):
        return 1.0
    return 0.0


class LineDraw:
    """The chart line drawing itself left to right, with a glowing tip and its live value."""

    def __init__(self, plot: Image.Image, origin: tuple[int, int], pts: list[tuple[float, float, float]],
                 t0: float, dur: float, label, color: tuple, label_out: float | None = None):
        self.plot, self.ox, self.oy = plot, origin[0], origin[1]
        self.pts, self.t0, self.dur, self.label, self.color = pts, t0, dur, label, color
        self.label_out = label_out
        self.dot = dot(9, color)
        self._cache: dict[str, Image.Image] = {}

    def progress(self, t: float) -> float:
        return ease_inout((t - self.t0) / self.dur)

    def at(self, px: float) -> tuple[float, float, float]:
        pts = self.pts
        if px <= pts[0][0]:
            return pts[0]
        for (xa, ya, va), (xb, yb, vb) in zip(pts, pts[1:]):
            if px <= xb:
                k = (px - xa) / max(1e-6, xb - xa)
                return px, ya + (yb - ya) * k, va + (vb - va) * k
        return pts[-1]

    def time_at(self, px: float) -> float:
        """When the tip passes x (for marks)."""
        x0, x1 = self.pts[0][0], self.pts[-1][0]
        f = clamp((px - x0) / max(1e-6, x1 - x0))
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ease_inout(mid) < f else (lo, mid)
        return self.t0 + hi * self.dur

    def paint(self, frame: Image.Image, t: float, end: float) -> None:
        if t < self.t0:
            return
        fade = 1 - smooth((t - (end - OUT)) / OUT)
        if fade <= 0.004:
            return
        x0, x1 = self.pts[0][0], self.pts[-1][0]
        px = x0 + (x1 - x0) * self.progress(t)
        cut = int(px - self.ox) + 6
        if cut > 0:
            part = self.plot.crop((0, 0, min(self.plot.width, cut), self.plot.height))
            if cut < self.plot.width:  # feather the wipe edge
                a = np.asarray(part.getchannel("A"), np.float32)
                ramp = np.clip((cut - np.arange(part.width)) / 18.0, 0, 1)[None, :]
                part.putalpha(Image.fromarray((a * ramp).astype(np.uint8), "L"))
            box = (self.ox, self.oy)
            if fade >= 0.995:
                frame.paste(part, box, part)
            else:
                frame.paste(part, box, part.getchannel("A").point(_lut(int(fade * 64 + 0.5))))
        x, y, v = self.at(px)
        paste(frame, self.dot, x, y, fade)
        if self.label is None:
            return
        la = fade * ease_out((t - self.t0) / 0.5)
        if self.label_out is not None and t > self.label_out:
            la *= 1 - smooth((t - self.label_out) / OUT)
        s = self.label(v)
        if s not in self._cache:
            if len(self._cache) > 600:
                self._cache.clear()
            self._cache[s] = text(s, "headline", 40, WHITE, tnum=True)
        img = self._cache[s]
        lx = clamp(x, img.width / 2 + 10, frame.width - img.width / 2 - 10)
        paste(frame, img, lx, y - 52 if y > 160 else y + 52, la)


class Bars:
    """Horizontal bars growing from the left, values counting with them; marks focus single rows."""

    def __init__(self, rows: list[dict], x0: int, t0: float, focus: list[tuple[float, set]]):
        self.rows, self.x0, self.t0, self.focus = rows, x0, t0, focus
        self._cache: dict[str, Image.Image] = {}

    def paint(self, frame: Image.Image, t: float, end: float) -> None:
        if t < self.t0:
            return
        fade = 1 - smooth((t - (end - OUT)) / OUT)
        if fade <= 0.004:
            return
        active, since = None, 0.0
        for ft, names in self.focus:
            if t >= ft:
                active, since = names, ft
        for i, r in enumerate(self.rows):
            g = ease_expo((t - r["t0"]) / 1.4)
            if g <= 0:
                continue
            a = fade * ease_out((t - r["t0"]) / 0.5)
            if active is not None:
                k = smooth((t - since) / 0.45)
                a *= 1 - 0.68 * k if r["name"] not in active else 1.0
            w = max(int(r["h"]), int(r["w"] * g))
            mask = pill_mask(w, int(r["h"]), r["h"] / 2)
            band = r["band"].crop((0, 0, w, int(r["h"])))
            y = int(round(r["y"] - r["h"] / 2))
            frame.paste(band, (self.x0, y), mask if a >= 0.995 else mask.point(_lut(int(a * 64 + 0.5))))
            s = r["fmt"](r["v"] * g)
            if s not in self._cache:
                if len(self._cache) > 800:
                    self._cache.clear()
                self._cache[s] = text(s, "headline", r["size"], WHITE, tnum=True)
            img = self._cache[s]
            paste(frame, img, self.x0 + w + 22 + img.width / 2, r["y"], a)
            lab = r["label"]
            paste(frame, lab, self.x0 - 28 - lab.width / 2, r["y"], a)


class Columns:
    """Vertical columns rising from a baseline, one after another."""

    def __init__(self, cols: list[dict], base: int):
        self.cols, self.base = cols, base

    def paint(self, frame: Image.Image, t: float, end: float) -> None:
        fade = 1 - smooth((t - (end - OUT)) / OUT)
        if fade <= 0.004:
            return
        for c in self.cols:
            g = ease_expo((t - c["t0"]) / 1.3)
            if g <= 0:
                continue
            h = max(int(c["w"] * 0.5), int(c["h"] * g))
            mask = pill_mask(int(c["w"]), h, min(26, c["w"] * 0.22))
            band = c["band"].crop((0, int(c["h"]) - h, int(c["w"]), int(c["h"])))
            a = fade * ease_out((t - c["t0"]) / 0.4)
            frame.paste(band, (int(c["x"] - c["w"] / 2), self.base - h),
                        mask if a >= 0.995 else mask.point(_lut(int(a * 64 + 0.5))))


@dataclass
class Scene:
    parts: list
    dur: float
    zoom: float = 0.035
    _key: tuple | None = field(default=None, repr=False)
    _base: Image.Image | None = field(default=None, repr=False)

    def draw(self, frame: Image.Image, t: float) -> Image.Image:
        # the leading elements that are at rest are painted once and reused until one of them changes
        key = []
        for p in self.parts:
            if type(p) is not El:
                break
            s = p.settled(t, self.dur)
            if s is None:
                break
            key.append(s == "full")
        n = len(key)
        if n:
            if (n, tuple(key)) != self._key:
                base = frame.copy()
                for p in self.parts[:n]:
                    p.paint(base, t, self.dur)
                self._key, self._base = (n, tuple(key)), base
            frame = self._base.copy()
        for p in self.parts[n:]:
            p.paint(frame, t, self.dur)
        if self.zoom:
            frame = push(frame, 1 + self.zoom * smooth(t / max(1.0, self.dur)))
        return frame

    def release(self) -> None:
        self._key, self._base = None, None


def push(frame: Image.Image, s: float) -> Image.Image:
    """Scale the frame by s around its centre (the slow camera push-in)."""
    w, h = frame.size
    if cv2 is not None:
        m = np.float32([[s, 0, w / 2 * (1 - s)], [0, s, h / 2 * (1 - s)]])
        return Image.fromarray(cv2.warpAffine(np.asarray(frame), m, (w, h), flags=cv2.INTER_CUBIC))
    return frame.transform(frame.size, Image.AFFINE, (1 / s, 0, w / 2 * (1 - 1 / s), 0, 1 / s, h / 2 * (1 - 1 / s)),
                           Image.BILINEAR)


class Stage:
    def __init__(self, w: int, h: int):
        self.black = Image.new("RGB", (w, h), (0, 0, 0))
        self.last: Scene | None = None

    def draw(self, scene: Scene, t: float) -> Image.Image:
        if scene is not self.last:  # keep one cached background at a time
            if self.last is not None:
                self.last.release()
            self.last = scene
        return scene.draw(self.black.copy(), t)


# ---------------------------------------------------------------- layout


@dataclass
class Layout:
    w: int
    h: int

    @property
    def vertical(self) -> bool:
        return self.h > self.w

    @property
    def m(self) -> int:  # side margin
        return 84 if self.vertical else 150

    @property
    def top(self) -> int:  # first line of content (vertical: below the app's top bar)
        return 270 if self.vertical else 112

    @property
    def bottom(self) -> int:  # last line of content (vertical: captions and the app's buttons below)
        return 1290 if self.vertical else self.h - 96

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2 if self.vertical else self.h * 0.47


def fmt(v: float, unit: str = "", dec: int | None = None) -> str:
    """1234567 -> 1.2M, with $ or % where the unit says so."""
    if unit == "%":
        s = f"{abs(v):.{1 if dec is None else dec}f}%"
        return ("−" if v < 0 and abs(v) >= 0.05 else "") + s
    a = abs(v)
    s = (f"{a / 1e12:.1f}T" if a >= 1e12 else f"{a / 1e9:.1f}B" if a >= 1e9 else f"{a / 1e6:.1f}M" if a >= 1e6
         else f"{a / 1e3:.1f}k" if a >= 1e4 else f"{a:,.0f}" if a >= 100 or dec == 0
         else f"{a:.{dec if dec is not None else 1}f}" if a < 10 else f"{a:.0f}")
    s = s.replace(".0T", "T").replace(".0B", "B").replace(".0M", "M").replace(".0k", "k")
    return ("−" if v < 0 else "") + (("$" + s) if unit == "$" else s)


COUNTRIES = {"USA": "United States", "GBR": "United Kingdom", "DEU": "Germany", "JPN": "Japan", "CHE": "Switzerland",
             "FRA": "France", "CHN": "China", "IND": "India", "BRA": "Brazil", "TUR": "Turkey", "NGA": "Nigeria",
             "CAN": "Canada", "AUS": "Australia", "KOR": "South Korea", "MEX": "Mexico", "ARG": "Argentina",
             "WLD": "World", "EUU": "European Union", "ITA": "Italy", "ESP": "Spain", "RUS": "Russia"}


def heading(L: Layout, title: str, sub: str = "", t0: float = 0.15) -> tuple[list[El], int]:
    """Chart heading, top left; returns the elements and the y where the content may start."""
    size = 62 if L.vertical else 58
    lines, size = fit(title, "headline", size, L.w - 2 * L.m, 2, 36)
    img = text(lines, "headline", size, WHITE, "left")
    pad = int(size * 0.12)
    top = L.top - pad
    els = [El(img, L.m - pad + img.width / 2, top + img.height / 2, t0)]
    bottom = top + img.height - pad
    if sub:
        sz = 30 if L.vertical else 28
        s = text(sub, "text", sz, GRAY, "left")
        p2 = int(sz * 0.12)
        st = bottom + 12 - p2
        els.append(El(s, L.m - p2 + s.width / 2, st + s.height / 2, t0 + 0.12))
        bottom = st + s.height - p2
    return els, int(bottom)


def glow_el(x: float, y: float, w: int, h: int, color: tuple, strength: float, t0: float) -> El:
    return El(glow(int(w), int(h), color, strength), x, y, t0, style="fade", dur=1.6)


# ---------------------------------------------------------------- scenes


def title(L: Layout, heading_text: str, kicker: str = "", color: str = "blue", **_) -> list:
    size = 112 if L.vertical else 128
    lines, size = fit(heading_text, "display", size, L.w - 2 * L.m - 40, 3 if L.vertical else 2, 60)
    head = text(lines, "display", size, WHITE)
    y = L.mid
    parts: list = [glow_el(L.w / 2, y, L.w * 0.9, head.height * 3.2, GRADIENTS[color][-1], 0.16, 0.0)]
    if kicker:
        k = text(kicker, "label", 40 if L.vertical else 36, color)
        parts.append(El(k, L.w / 2, y - head.height / 2 - k.height / 2 + 6, 0.1))
    parts.append(El(head, L.w / 2, y + 10, 0.3))
    return parts


def number(L: Layout, big: str, caption: str = "", color: str = "green", **_) -> list:
    items = [p.strip() for p in big.split("→")]
    hero_size = 250 if L.vertical else 290
    small = int(hero_size * 0.56)
    face = "display"
    grad = GRADIENTS[color]
    parts: list = []

    def sized(s: str, size: int, limit: float) -> int:
        while width(s, face, size) > limit and size > 40:
            size = int(size * 0.94)
        return size

    if L.vertical:
        hero_size = sized(items[-1], hero_size, L.w - 2 * L.m)
        blocks = []
        for i, s in enumerate(items):
            last = i == len(items) - 1
            blocks.append(("num", s, hero_size if last else sized(s, small, L.w - 2 * L.m)))
            if not last:
                blocks.append(("arrow", "↓", int(small * 0.7)))
        heights = [int(sz * 1.08) for _, _, sz in blocks]
        gap = 18
        total = sum(heights) + gap * (len(blocks) - 1) + (90 if caption else 0)
        y = L.mid - total / 2
        k = 0
        for (kind, s, sz), hh in zip(blocks, heights):
            cy = y + hh / 2
            t0 = 0.25 + 0.5 * k
            if kind == "arrow":
                parts.append(El(text(s, "medium", sz, DIM), L.w / 2, cy, t0 - 0.2))
            else:
                last = s == items[-1] and k == len(items) - 1
                parts += _figure(L, s, sz, last, items[k - 1] if k else None, grad, L.w / 2, cy, t0)
                k += 1
            y += hh + gap
        cap_y = y + 30
    else:
        sizes = [sized(s, small, 640) for s in items[:-1]] + [hero_size]
        widths = []
        for s, sz in zip(items, sizes):
            widths.append(width(s, face, sz))
        arrow = int(small * 0.62)
        aw = width("→", "medium", arrow) + 70
        total = sum(widths) + aw * (len(items) - 1)
        if total > L.w - 2 * L.m:
            f = (L.w - 2 * L.m) / total
            sizes = [int(sz * f) for sz in sizes]
            widths = [w * f for w in widths]
            aw *= f
            arrow = int(arrow * f)
            total = L.w - 2 * L.m
        x = L.w / 2 - total / 2
        cy = L.mid - (50 if caption else 0)
        for i, (s, sz, w) in enumerate(zip(items, sizes, widths)):
            last = i == len(items) - 1
            t0 = 0.25 + 0.5 * i
            parts += _figure(L, s, sz, last, items[i - 1] if i else None, grad, x + w / 2, cy, t0)
            x += w
            if not last:
                parts.append(El(text("→", "medium", arrow, DIM), x + aw / 2, cy - sz * 0.04, t0 + 0.3))
                x += aw
        cap_y = cy + max(sizes) * 0.62 + 40
    if caption:
        lines, size = fit(caption, "text", 44 if L.vertical else 40, L.w - 2 * L.m - (0 if L.vertical else 300), 2, 28)
        c = text(lines, "text", size, GRAY)
        parts.append(El(c, L.w / 2, cap_y + c.height / 2, 0.55 + 0.5 * (len(items) - 1)))
    return parts


def _figure(L: Layout, s: str, size: int, hero: bool, before: str | None, grad: list, x: float, y: float,
            t0: float) -> list:
    if not hero:
        return [El(text(minus(s), "display", size, WHITE, tnum=True), x, y, t0)]
    img = text(minus(s), "display", size, grad, tnum=True)
    out: list = [glow_el(x, y, img.width * 1.9, img.height * 2.2, grad[-1], 0.2, t0)]
    start = count_from(s, before)
    if start is None:
        out.append(El(img, x, y, t0))
    else:
        out.append(Counter(s, start, "display", size, grad, x, y, t0, count=1.7))
    return out


def note(L: Layout, statement: str, source: str = "", color: str = "blue", **_) -> list:
    """A statement; words between *asterisks* are set in the accent gradient."""
    size = 76 if L.vertical else 74
    max_w = L.w - 2 * L.m - (0 if L.vertical else 260)
    plain = statement.replace("*", "")
    lines, size = fit(plain, "headline", size, max_w, 7 if L.vertical else 4, 40)
    # mark which characters are highlighted, then render line by line in two passes
    flags, on = [], False
    for ch in statement:
        if ch == "*":
            on = not on
            continue
        flags.append(on)
    masks_w, masks_h = [], []
    pos = 0
    for line in lines:
        k = plain.find(line, pos)
        f = flags[k:k + len(line)]
        pos = k + len(line)
        hi = "".join(c if f[i] else " " for i, c in enumerate(line))
        lo = "".join(c if not f[i] else " " for i, c in enumerate(line))
        masks_w.append(lo)
        masks_h.append(hi)
    full = text_mask(lines, "headline", size, "center")
    white = Image.new("L", full.size)
    accent = Image.new("L", full.size)
    step = int(size * 1.12)
    for i, (lo, hi, line) in enumerate(zip(masks_w, masks_h, lines)):
        lw = _line_mask(line, "headline", size)
        x = (full.width - lw.width) // 2
        for src, dst in ((lo, white), (hi, accent)):
            if src.strip():
                m = _ghost_mask(line, src, size)
                dst.paste(m, (x, i * step), m)
    img = colorize(white, WHITE)
    img.alpha_composite(colorize(accent, color))
    parts: list = [glow_el(L.w / 2, L.mid, L.w * 0.8, img.height * 2.6, GRADIENTS[color][-1], 0.09, 0.0),
                   El(img, L.w / 2, L.mid - (30 if source else 0), 0.2)]
    if source:
        s = text(source, "text", 32 if L.vertical else 28, GRAY)
        parts.append(El(s, L.w / 2, L.mid + img.height / 2 + 30, 0.7))
    return parts


def _ghost_mask(line: str, visible: str, size: int) -> Image.Image:
    """Mask of only the visible characters of a line, at their exact positions within the full line."""
    f = font("headline", size)
    tr = TRACK["headline"] * size
    asc, desc = f.getmetrics()
    pad = int(size * 0.12)
    img = Image.new("L", _line_mask(line, "headline", size).size)
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(line):
        if visible[i] == " ":
            continue
        x = f.getlength(line[:i + 1]) - f.getlength(ch) + tr * i
        d.text((pad + x, pad), ch, font=f, fill=255)
    return img


def compare(L: Layout, left: tuple, right: tuple, heading_text: str = "", color: str = "blue", **_) -> list:
    parts: list = []
    top = L.top
    if heading_text:
        lines, size = fit(heading_text, "headline", 64 if L.vertical else 60, L.w - 2 * L.m, 2, 36)
        h = text(lines, "headline", size, WHITE)
        y = (L.top + h.height / 2) if L.vertical else L.top + 40 + h.height / 2
        parts.append(El(h, L.w / 2, y, 0.1))
        top = int(y + h.height / 2)
    if L.vertical:
        cw, ch = L.w - 2 * L.m, 400
        gap = 110
        y0 = top + (L.bottom - top - 2 * ch - gap) / 2 + ch / 2
        centers = [(L.w / 2, y0), (L.w / 2, y0 + ch + gap)]
        arrow = ("↓", L.w / 2, y0 + ch / 2 + gap / 2)
    else:
        cw, ch = 640, 440
        gap = 150
        cy = top + (L.bottom - top) / 2 + 10
        centers = [(L.w / 2 - cw / 2 - gap / 2, cy), (L.w / 2 + cw / 2 + gap / 2, cy)]
        arrow = ("→", L.w / 2, cy)
    grad = GRADIENTS[color]
    for i, ((lab, val), (x, y)) in enumerate(zip((left, right), centers)):
        t0 = 0.3 + 0.55 * i
        card = rounded(int(cw), int(ch), 44)
        lab_img = text(lab, "label", 36 if L.vertical else 34, GRAY)
        card.alpha_composite(lab_img, (int(cw / 2 - lab_img.width / 2), 58))
        size = 170 if L.vertical else 150
        while width(val, "display", size) > cw - 90 and size > 50:
            size = int(size * 0.94)
        vy = y + 32
        if i == 0:
            v = text(minus(val), "display", size, WHITE, tnum=True)
            card.alpha_composite(v, (int(cw / 2 - v.width / 2), int(vy - y + ch / 2 - v.height / 2)))
            parts.append(El(card, x, y, t0))
        else:
            parts.append(glow_el(x, y, cw * 1.5, ch * 1.6, grad[-1], 0.14, t0))
            parts.append(El(card, x, y, t0))
            start = count_from(val, left[1])
            if start is None:
                parts.append(El(text(minus(val), "display", size, grad, tnum=True), x, vy, t0))
            else:
                parts.append(Counter(val, start, "display", size, grad, x, vy, t0 + 0.15, count=1.5))
    parts.append(El(text(arrow[0], "medium", 90, DIM), arrow[1], arrow[2], 0.7))
    return parts


def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = min((1, 2, 5, 10), key=lambda m: abs(m * mag - raw)) * mag
    start = math.ceil(lo / step) * step
    ticks, v = [], start
    while v <= hi + 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def line(L: Layout, series: list[dict], heading_text: str = "", unit: str = "", log: bool = False, sub: str = "",
         dur: float = 10.0, marks: list | None = None, color: str = "green", **_) -> list:
    els, top = heading(L, heading_text, sub)
    parts: list = list(els)
    x0 = L.m + (110 if L.vertical else 130)
    x1 = L.w - L.m - (40 if L.vertical else 120)
    y0 = top + (90 if L.vertical else 80)
    y1 = L.bottom - (60 if L.vertical else 70)
    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    lo, hi = min(xs), max(xs)
    vlo = min(0.0, min(ys)) if not log else min(ys)
    vhi = max(ys)
    tr = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    a, b = tr(vlo), tr(vhi) + (tr(vhi) - tr(vlo)) * 0.06
    ticks = _nice_ticks(vlo, vhi) if not log else [10 ** e for e in range(math.ceil(a), math.floor(b) + 1)]

    def X(x: float) -> float:
        return x0 + (x - lo) / max(1e-9, hi - lo) * (x1 - x0)

    def Y(v: float) -> float:
        return y1 - (tr(v) - a) / max(1e-9, b - a) * (y1 - y0)

    # grid and axis labels (static)
    P = 60
    grid = Image.new("RGBA", (L.w, L.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    lab_size = 30 if L.vertical else 28
    for v in ticks:
        y = Y(v)
        if y < y0 - 30:
            continue
        d.line((x0, round(y), x1, round(y)), fill=(255, 255, 255, 60 if v == 0 else 26), width=2)
        lab = text(fmt(v, unit, 0), "text", lab_size, GRAY, tnum=True)
        grid.alpha_composite(lab, (int(x0 - 26 - lab.width), int(y - lab.height / 2)))
    span = hi - lo
    step = 10 if span > 30 else 5 if span > 12 else 2 if span > 5 else 1
    for xv in range(int(math.ceil(lo / step) * step), int(hi) + 1, step):
        lab = text(str(xv), "text", lab_size, GRAY, tnum=True)
        grid.alpha_composite(lab, (int(X(xv) - lab.width / 2), int(y1 + 22)))
    bbox = grid.getbbox() or (0, 0, 1, 1)
    gimg = grid.crop(bbox)
    parts.append(El(gimg, (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2, 0.35, style="fade"))

    draw_t0 = 0.9
    draw_dur = clamp(dur * 0.42, 3.2, 7.5)
    grad_name = color
    tip_color = GRADIENTS[grad_name][-1]
    lines_out = []
    for si, s in enumerate(series):
        g = GRADIENTS[s.get("color") or grad_name]
        pts = [(X(x), Y(v), v) for x, v in s["points"]]
        ox, oy = int(x0 - P), int(y0 - P)
        W, H = int(x1 - x0 + 2 * P), int(y1 - y0 + 2 * P)
        ss = 3
        lm = Image.new("L", (W * ss, H * ss))
        dl = ImageDraw.Draw(lm)
        flat = [((px - ox) * ss, (py - oy) * ss) for px, py, _ in pts]
        dl.line(flat, fill=255, width=6 * ss, joint="curve")
        for fx, fy in (flat[0], flat[-1]):
            dl.ellipse((fx - 3 * ss, fy - 3 * ss, fx + 3 * ss, fy + 3 * ss), fill=255)
        line_mask = lm.resize((W, H), Image.LANCZOS)
        area = Image.new("L", (W * ss, H * ss))
        base = (Y(max(vlo, 0.0) if not log else vlo) - oy) * ss
        ImageDraw.Draw(area).polygon([(flat[0][0], base)] + flat + [(flat[-1][0], base)], fill=255)
        area = area.resize((W, H), Image.LANCZOS)
        top_y = min(py for _, py, _ in pts) - oy
        fade = np.clip(1 - (np.arange(H, dtype=np.float32) - top_y) / max(1.0, base / ss - top_y), 0, 1) ** 1.4
        area_a = (np.asarray(area, np.float32) * fade[:, None] * 0.30).astype(np.uint8)
        plot = colorize(Image.fromarray(area_a, "L"), g)
        glow_mask = line_mask.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.7))
        plot.alpha_composite(colorize(glow_mask, g))
        plot.alpha_composite(colorize(line_mask, g))
        lines_out.append((plot, (ox, oy), pts, g))

    def label(v: float) -> str:
        return fmt(v, unit, 1 if unit == "%" else None)

    marks = marks or []
    end_x = lines_out[0][2][-1][0] if lines_out else x1
    multi = len(lines_out) > 1
    first = None
    drawers = []
    for si, (plot, origin, pts, g) in enumerate(lines_out):
        ld = LineDraw(plot, origin, pts, draw_t0 + 0.25 * si, draw_dur, None if multi else label, g[-1])
        drawers.append(ld)
        if first is None:
            first = ld
    parts += drawers
    bounds = (x0, y0 - 40, L.w - L.m / 2, y1)
    if multi:  # several lines: each gets its name and final value once it has arrived
        everything = [pt for _, _, pts, _ in lines_out for pt in _samples(pts)]
        for s, (plot, origin, pts, g), ld in zip(series, lines_out, drawers):
            px, py, v = pts[-1]
            pill = _pill(s.get("label", ""), label(v), L.vertical)
            lx, ly = _place(pill, px, py, everything, bounds)
            parts.append(El(pill, lx, ly, ld.t0 + ld.dur + 0.1))
    # marks: a ring on the point and a label; a new mark replaces the previous label
    ring = _ring(14, tip_color)
    timed = []
    for mt, m in marks:
        if first is None or "x" not in m:
            continue
        px = X(m["x"])
        _, py, v = first.at(px)
        t_m = max(mt + 0.2, first.time_at(px) + 0.2)
        timed.append((t_m, m, px, py, v))
    timed.sort(key=lambda r: r[0])
    samples = _samples(first.pts) if first else []
    for k, (t_m, m, px, py, v) in enumerate(timed):
        nxt = timed[k + 1][0] if k + 1 < len(timed) else None
        parts.append(El(ring, px, py, t_m, style="fade", dur=0.4))
        lab = m.get("label") or label(v)
        pill = _pill(str(m["x"]), lab, L.vertical)
        lx, ly = _place(pill, px, py, samples, bounds)
        parts.append(El(pill, lx, ly, t_m + 0.05, out=nxt))
        if abs(px - end_x) < 200 and first.label_out is None:
            first.label_out = t_m
    return parts


def _samples(pts: list) -> list[tuple[float, float]]:
    """Points every ~4 px along a polyline (to keep labels off the line)."""
    out = []
    for (xa, ya, *_), (xb, yb, *_) in zip(pts, pts[1:]):
        steps = max(1, int(math.hypot(xb - xa, yb - ya) / 4))
        out += [(xa + (xb - xa) * k / steps, ya + (yb - ya) * k / steps) for k in range(steps)]
    return out + [tuple(pts[-1][:2])]


def _place(img: Image.Image, px: float, py: float, samples: list, bounds: tuple) -> tuple[float, float]:
    """Where a label next to (px, py) covers the least of the line (and stays inside the plot)."""
    w, h = img.width, img.height
    best, pick = None, (px, py - h / 2 - 30)
    for k, (fx, fy) in enumerate(((0, -1), (-1, -1), (1, -1), (0, 1), (-1, 1), (1, 1))):
        cx = px + fx * (w / 2 + 12)
        cy = py + fy * (h / 2 + 30)
        l, t, r, b = cx - w / 2 - 8, cy - h / 2 - 8, cx + w / 2 + 8, cy + h / 2 + 8
        hits = sum(1 for sx, sy in samples if l <= sx <= r and t <= sy <= b)
        out = max(0, bounds[0] - l) + max(0, bounds[1] - t) + max(0, r - bounds[2]) + max(0, b - bounds[3])
        score = hits * 10 + out * 4 + k
        if best is None or score < best:
            best, pick = score, (cx, cy)
    return pick


@lru_cache(maxsize=8)
def _ring(r: int, color: tuple) -> Image.Image:
    size = r * 6
    img = glow(size, size, color, 0.55).copy()
    ss = 3
    m = Image.new("L", (size * ss, size * ss))
    c = size * ss / 2
    ImageDraw.Draw(m).ellipse((c - r * ss, c - r * ss, c + r * ss, c + r * ss), outline=255, width=4 * ss)
    img.alpha_composite(colorize(m.resize((size, size), Image.LANCZOS), WHITE))
    return img


def _pill(kicker: str, value: str, vertical: bool) -> Image.Image:
    k = text(kicker or " ", "label", 28 if vertical else 26, GRAY, tnum=True)
    v = text(value, "headline", 46 if vertical else 42, WHITE, tnum=True)
    w = int(k.width + v.width + 34)
    h = int(max(k.height, v.height) + 6)
    card = rounded(w, h, h / 2, fill=(28, 28, 32), border=(255, 255, 255, 30))
    card.alpha_composite(k, (14, (h - k.height) // 2 + 2))
    card.alpha_composite(v, (k.width + 14, (h - v.height) // 2))
    return card


def bars(L: Layout, items: list[tuple[str, float]], heading_text: str = "", unit: str = "", highlight=None,
         suffix: str = "", sub: str = "", marks: list | None = None, color: str = "blue", **_) -> list:
    els, top = heading(L, heading_text, sub)
    parts: list = list(els)
    n = len(items)
    area_top, area_bottom = top + 70, L.bottom - 20
    row_h = min(120 if L.vertical else 96, (area_bottom - area_top) / n)
    bar_h = row_h * (0.48 if L.vertical else 0.5)
    lab_size = 36 if L.vertical else 34
    labels = [text(name, "text", lab_size, SOFT) for name, _ in items]
    x0 = int(L.m + max(l.width for l in labels) + 28)
    vmax = max(v for _, v in items) or 1.0
    full = (L.w - L.m - 150 - x0) if L.vertical else (L.w - L.m - 200 - x0)
    highlight = {highlight} if isinstance(highlight, str) else set(highlight or [])
    rows = []
    y = area_top + (area_bottom - area_top - row_h * n) / 2 + row_h / 2
    dec = 1 if unit == "%" else (1 if vmax < 10 else 0)
    for i, ((name, v), lab) in enumerate(zip(items, labels)):
        hot = name in highlight or not highlight
        g = GRADIENTS[color] if hot else GRADIENTS["gray"]
        w = max(bar_h, full * max(0.0, v) / vmax)
        rows.append({"name": name, "v": v, "w": w, "h": bar_h, "y": y, "t0": 0.7 + 0.12 * i, "label": lab,
                     "band": gradient(int(full) + 2, int(bar_h), tuple(g), 0.0),
                     "fmt": (lambda val, d=dec: fmt(val, unit, d) + suffix), "size": 38 if L.vertical else 36})
        y += row_h
    focus = []
    for mt, m in marks or []:
        names = m.get("item") or m.get("items")
        if names:
            focus.append((mt + 0.1, {names} if isinstance(names, str) else set(names)))
    parts.append(Bars(rows, x0, 0.6, sorted(focus, key=lambda f: f[0])))
    return parts


def columns(L: Layout, stacks: list, heading_text: str = "", color: str = "green", sub: str = "", **_) -> list:
    """Columns side by side: stacks = [[label, height, value text], ...]; the last one is highlighted."""
    els, top = heading(L, heading_text, sub)
    parts: list = list(els)
    n = len(stacks)
    base = L.bottom - (80 if L.vertical else 70)
    max_h = base - top - (190 if L.vertical else 150)
    span = L.w - 2 * L.m
    slot = span / n
    cw = min(170 if not L.vertical else 150, slot * 0.56)
    hmax = max(float(s[1]) for s in stacks) or 1.0
    cols = []
    for i, (lab, hval, val) in enumerate(stacks):
        x = L.m + slot * (i + 0.5)
        h = max(cw * 0.5, max_h * float(hval) / hmax)
        last = i == n - 1
        g = GRADIENTS[color] if last else [(70, 70, 76), (120, 120, 128)]
        t0 = 0.7 + 0.4 * i
        cols.append({"x": x, "w": cw, "h": h, "t0": t0, "band": gradient(int(cw), int(h) + 1, tuple(g[::-1]), 90.0)})
        v = text(str(val), "headline", 54 if L.vertical else 50, g if last else WHITE, tnum=True)
        parts.append(El(v, x, base - h - 26 - v.height / 2, t0 + 0.75, dy=16))
        lab_img = text(str(lab), "text", 32 if L.vertical else 30, GRAY, tnum=True)
        parts.append(El(lab_img, x, base + 30 + lab_img.height / 2 - 8, t0, style="fade"))
        if last:
            parts.insert(0, glow_el(x, base - h / 2, cw * 4, h * 1.6, g[-1], 0.14, t0 + 0.4))
    parts.append(Columns(cols, base))
    axis = Image.new("RGBA", (int(span), 2), (255, 255, 255, 50))
    parts.append(El(axis, L.w / 2, base + 1, 0.4, style="fade"))
    return parts


SCENES = {"title": title, "number": number, "note": note, "compare": compare, "line": line, "bars": bars,
          "columns": columns, "coins": columns}


def scene(L: Layout, parts: list, dur: float, zoom: float | None = None) -> Scene:
    return Scene(parts, dur, 0.035 if zoom is None else zoom)
