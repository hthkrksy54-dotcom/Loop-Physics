"""Still images for Instagram: quote carousels, story cards and highlight covers (channel style)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import render, visuals

CREAM = (246, 238, 222)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(visuals.FONT_DIR / name), size)


def _field(w: int, h: int, palette: dict, seed: int, t: float = 30.0) -> Image.Image:
    unit = 320
    bw, bh = (unit, int(unit * h / w)) if w >= h else (int(unit * w / h), unit)
    img = Image.fromarray(visuals.Background(bw, bh, palette, seed).frame(t, dim=1.05))
    img = img.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = 1 - 0.5 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) ** 0.9
    return Image.fromarray((np.asarray(img, dtype=np.float32) * np.clip(v, 0.3, 1)[..., None]).astype(np.uint8))


def _wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _block(draw, text, fontname, size, max_w, max_h, min_size=40):
    """Largest font size at which the text fits the box; returns (font, lines, line_height)."""
    while True:
        font = _font(fontname, size)
        lines = _wrap(draw, text, font, max_w)
        lh = int(size * 1.18)
        fits = lh * len(lines) <= max_h and all(draw.textlength(l, font=font) <= max_w for l in lines)
        if fits or size <= min_size:
            return font, lines, lh
        size -= 4


def _centered(draw, lines, font, lh, cx, top, fill):
    for i, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        draw.text((cx - w / 2, top + i * lh), line, font=font, fill=fill)


def _spaced(text: str) -> str:
    return "  ".join(text.upper())


def carousel(script: dict, cfg: dict, outdir: Path) -> list[Path]:
    """Cover + idea slides + closing slide, 1080x1350 JPEGs."""
    W, H = 1080, 1350
    seed = render.seed_for(script)
    palette = visuals.palette_for(seed)
    accent = tuple(palette["accent"])
    data = script["carousel"]
    slides = data["slides"]
    total = len(slides) + 2
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []

    def frame(i: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = _field(W, H, palette, seed, t=20.0 + i * 9)
        d = ImageDraw.Draw(im)
        d.text((70, 60), f"{i + 1} / {total}", font=_font("EBGaramond-Medium.ttf", 30), fill=accent)
        handle = "@" + cfg["instagram"].get("account", "")
        hw = d.textlength(handle, font=_font("EBGaramond-Regular.ttf", 30))
        d.text((W - 70 - hw, 60), handle, font=_font("EBGaramond-Regular.ttf", 30), fill=CREAM)
        return im, d

    # Cover
    im, d = frame(0)
    lab = _font("EBGaramond-Medium.ttf", 34)
    _centered(d, [_spaced(script.get("label", ""))], lab, 40, W / 2, 380, accent)
    d.line([(W / 2 - 70, 440), (W / 2 + 70, 440)], fill=accent, width=2)
    font, lines, lh = _block(d, data["cover"], "CormorantGaramond-SemiBold.ttf", 120, W - 180, 520)
    _centered(d, lines, font, lh, W / 2, 500, CREAM)
    _centered(d, ["swipe  →"], _font("EBGaramond-Regular.ttf", 36), 40, W / 2, H - 170, accent)
    paths.append(outdir / "slide_01.jpg")
    im.save(paths[-1], "JPEG", quality=92)

    # Ideas
    for n, slide in enumerate(slides, start=1):
        im, d = frame(n)
        font, lines, lh = _block(d, slide["text"], "CormorantGaramond-Medium.ttf", 92, W - 200, 700)
        top = (H - lh * len(lines)) / 2 - 60
        _centered(d, lines, font, lh, W / 2, top, CREAM)
        if slide.get("sub"):
            sub_font, sub_lines, sub_lh = _block(d, "— " + slide["sub"], "EBGaramond-Italic.ttf", 42, W - 220, 130, 28)
            _centered(d, sub_lines, sub_font, sub_lh, W / 2, top + lh * len(lines) + 50, accent)
        paths.append(outdir / f"slide_{n + 1:02d}.jpg")
        im.save(paths[-1], "JPEG", quality=92)

    # Closing slide
    im, d = frame(total - 1)
    font, lines, lh = _block(d, "The full video essay is on YouTube", "CormorantGaramond-SemiBold.ttf", 96, W - 200, 400)
    _centered(d, lines, font, lh, W / 2, 470, CREAM)
    small = _font("EBGaramond-Regular.ttf", 40)
    _centered(d, [cfg["channel_name"] + " · link in bio"], small, 50, W / 2, 470 + lh * len(lines) + 60, accent)
    _centered(d, ["Save this for a quiet moment."], small, 50, W / 2, H - 260, CREAM)
    paths.append(outdir / f"slide_{total:02d}.jpg")
    im.save(paths[-1], "JPEG", quality=92)
    return paths


def story_card(path: Path, eyebrow: str, title: str, lines: list[str], seed: int = 3) -> Path:
    """1080x1920 story image."""
    W, H = 1080, 1920
    palette = visuals.PALETTES[0]
    accent = tuple(palette["accent"])
    im = _field(W, H, palette, seed)
    d = ImageDraw.Draw(im)
    top = 700  # Instagram overlays the top ~250 px and bottom ~340 px of a story
    _centered(d, [_spaced(eyebrow)], _font("EBGaramond-Medium.ttf", 38), 44, W / 2, top, accent)
    d.line([(W / 2 - 80, top + 70), (W / 2 + 80, top + 70)], fill=accent, width=2)
    font, tl, lh = _block(d, title, "CormorantGaramond-SemiBold.ttf", 130, W - 160, 440)
    _centered(d, tl, font, lh, W / 2, top + 130, CREAM)
    y = top + 130 + lh * len(tl) + 70
    body = _font("EBGaramond-Regular.ttf", 46)
    for text in lines:
        bl = _wrap(d, text, body, W - 200)
        _centered(d, bl, body, 62, W / 2, y, CREAM)
        y += 62 * len(bl) + 26
    im.save(path, "JPEG", quality=92)
    return path


def highlight_cover(path: Path, word: str, seed: int) -> Path:
    """1080x1080 cover; Instagram crops highlights to a circle, so text stays central."""
    W = 1080
    palette = visuals.PALETTES[0]
    accent = tuple(palette["accent"])
    im = _field(W, W, palette, seed)
    d = ImageDraw.Draw(im)
    d.ellipse((190, 190, 890, 890), outline=accent, width=7)
    font, lines, lh = _block(d, word, "CormorantGaramond-SemiBold.ttf", 140, 520, 380)
    _centered(d, lines, font, lh, W / 2, (W - lh * len(lines)) / 2 - 20, CREAM)
    im.save(path, "JPEG", quality=92)
    return path


def quote_story(path: Path, text: str, author: str, seed: int = 5, handle: str = "") -> Path:
    """1080x1920 quote card for Stories (kept inside the area Instagram leaves free)."""
    W, H = 1080, 1920
    palette = visuals.palette_for(seed)
    accent = tuple(palette["accent"])
    im = _field(W, H, palette, seed)
    d = ImageDraw.Draw(im)
    font, lines, lh = _block(d, f"“{text}”", "CormorantGaramond-Medium.ttf", 100, W - 200, 820, 48)
    top = (H - lh * len(lines)) / 2 - 80
    _centered(d, lines, font, lh, W / 2, top, CREAM)
    y = top + lh * len(lines) + 60
    d.line([(W / 2 - 60, y), (W / 2 + 60, y)], fill=accent, width=2)
    _centered(d, _wrap(d, author, _font("EBGaramond-Italic.ttf", 44), W - 240), _font("EBGaramond-Italic.ttf", 44), 56, W / 2, y + 40, accent)
    if handle:
        _centered(d, [handle], _font("EBGaramond-Regular.ttf", 34), 40, W / 2, H - 440, CREAM)
    im.save(path, "JPEG", quality=92)
    return path


def best_quote(script: dict) -> dict | None:
    """The shortest quote of the (fact-checked) script reads best on a phone."""
    quotes = [s["quote"] for s in script.get("sections", []) if s.get("quote") and s["quote"].get("text")]
    return min(quotes, key=lambda q: len(q["text"])) if quotes else None


HIGHLIGHTS = {"psychology": "Psychology", "philosophy": "Philosophy"}


def highlight_for(script: dict) -> str:
    """Story highlight a video's Reel story belongs in."""
    return HIGHLIGHTS.get(script.get("category", ""), script.get("label") or "Philosophy")


def quote_pool(scripts: list[dict], max_words: int = 40) -> list[dict]:
    """Fact-checked quotes from the given scripts that fit on a story card."""
    pool = []
    for script in scripts:
        for sec in script.get("sections", []):
            q = sec.get("quote")
            if q and q.get("text") and len(q["text"].split()) <= max_words:
                pool.append({"text": q["text"], "author": q["author"], "script": script})
    return pool
