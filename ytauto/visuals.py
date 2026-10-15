"""Calm procedural visuals: drifting soft colour fields, plus thumbnails."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Each palette: dark base, a few glow colours, and an accent for small text.
PALETTES = [
    {"name": "midnight", "base": (8, 12, 22), "glows": [(28, 58, 96), (70, 48, 96), (150, 112, 64), (18, 84, 92)], "accent": (214, 182, 120)},
    {"name": "ember", "base": (16, 9, 9), "glows": [(110, 40, 30), (150, 92, 40), (60, 28, 52), (90, 60, 30)], "accent": (230, 178, 110)},
    {"name": "forest", "base": (7, 14, 11), "glows": [(30, 76, 56), (90, 110, 60), (26, 60, 72), (120, 100, 52)], "accent": (206, 196, 140)},
    {"name": "dusk", "base": (14, 10, 20), "glows": [(96, 54, 104), (150, 84, 86), (44, 58, 110), (170, 120, 80)], "accent": (236, 190, 150)},
    {"name": "slate", "base": (10, 12, 15), "glows": [(60, 76, 92), (116, 96, 66), (40, 62, 70), (84, 84, 104)], "accent": (220, 196, 150)},
    {"name": "ocean", "base": (5, 13, 19), "glows": [(20, 80, 110), (28, 108, 104), (60, 70, 120), (130, 120, 90)], "accent": (190, 214, 210)},
]


def palette_for(seed: int) -> dict:
    return PALETTES[seed % len(PALETTES)]


class Background:
    """Generates frames of slowly drifting gaussian glows at low resolution.

    ffmpeg upscales them; smooth gradients survive upscaling perfectly.
    """

    def __init__(self, width: int, height: int, palette: dict, seed: int):
        self.w, self.h = width, height
        rng = np.random.default_rng(seed)
        self.base = np.array(palette["base"], dtype=np.float32) / 255
        unit = min(width, height)  # blobs scale with the short side, so portrait stays moody
        ext_x, ext_y = width / unit, height / unit
        ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
        self.x = xs / unit
        self.y = ys / unit
        self.blobs = []
        for color in palette["glows"]:
            self.blobs.append(
                {
                    "color": np.array(color, dtype=np.float32) / 255,
                    "cx": rng.uniform(0.2, 0.8) * ext_x,
                    "cy": rng.uniform(0.2, 0.8) * ext_y,
                    "ax": rng.uniform(0.15, 0.35) * ext_x,
                    "ay": rng.uniform(0.12, 0.3) * ext_y,
                    "wx": 2 * math.pi / rng.uniform(55, 110),
                    "wy": 2 * math.pi / rng.uniform(60, 120),
                    "px": rng.uniform(0, 2 * math.pi),
                    "py": rng.uniform(0, 2 * math.pi),
                    "size": rng.uniform(0.28, 0.5),
                    "wb": 2 * math.pi / rng.uniform(25, 50),
                    "pb": rng.uniform(0, 2 * math.pi),
                }
            )

    def frame(self, t: float, dim: float = 1.0) -> np.ndarray:
        acc = np.zeros((self.h, self.w, 3), dtype=np.float32)
        for b in self.blobs:
            cx = b["cx"] + b["ax"] * math.sin(b["wx"] * t + b["px"])
            cy = b["cy"] + b["ay"] * math.sin(b["wy"] * t + b["py"])
            s = b["size"] * (0.85 + 0.15 * math.sin(b["wb"] * t + b["pb"]))
            g = np.exp(-((self.x - cx) ** 2 + (self.y - cy) ** 2) / (2 * s * s))
            acc += g[..., None] * b["color"]
        img = self.base + (1 - np.exp(-acc * 1.5)) * 0.62 * dim
        return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def thumbnail(path: Path, text: str, label: str, palette: dict, seed: int) -> None:
    """1280x720 thumbnail: large serif statement on the video's colour field."""
    W, H = 1280, 720
    bg = Background(320, 180, palette, seed)
    img = Image.fromarray(bg.frame(37.0, dim=1.25)).resize((W, H), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(2))

    # Vignette for focus.
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = 1 - 0.55 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 0.9
    arr = (np.asarray(img, dtype=np.float32) * np.clip(v, 0.25, 1)[..., None]).astype(np.uint8)
    img = Image.fromarray(arr)

    draw = ImageDraw.Draw(img)
    accent = tuple(palette["accent"])
    cream = (246, 238, 222)

    size = 132
    while True:
        font = _font("CormorantGaramond-SemiBold.ttf", size)
        lines = _wrap(draw, text, font, W - 200)
        line_h = int(size * 1.02)
        if (len(lines) <= 3 and line_h * len(lines) < H - 260) or size <= 70:
            break
        size -= 6

    total = line_h * len(lines)
    y = (H - total) // 2 + 30
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        sd.text(((W - w) / 2 + 3, y + i * line_h + 4), line, font=font, fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img.convert("RGBA"), shadow)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y + i * line_h), line, font=font, fill=cream)

    lab_font = _font("EBGaramond-Medium.ttf", 34)
    lab = "  ".join(label.upper())
    lw = draw.textlength(lab, font=lab_font)
    draw.text(((W - lw) / 2, y - 78), lab, font=lab_font, fill=accent)
    draw.line([(W / 2 - 60, y - 24), (W / 2 + 60, y - 24)], fill=accent, width=2)

    img.convert("RGB").save(path, "JPEG", quality=92)
