"""Satisfying physics simulations for vertical Shorts/Reels.

Everything is generated here – physics, picture and sound (every collision plays the next note of a
public-domain melody) – so each video is original and free of third-party rights.

  escape: a ball bounces inside rotating rings with a gap and breaks out ring by ring
  grow:   a ball grows with every bounce until it fills the circle
"""
from __future__ import annotations

import colorsys
import math
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from . import visuals

W, H, FPS, SS = 1080, 1920, 60, 2  # SS: supersampling for anti-aliased shapes
SUBSTEPS = 12
SR = 48000
CX, CY = W / 2, H * 0.5
TAU = 2 * math.pi
OUTRO = 2.6

# Melody lines (MIDI note numbers) of public-domain compositions.
MELODIES = {
    "fur_elise": ("Für Elise – Beethoven", [
        76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 68, 71, 72, 64,
        76, 75, 76, 75, 76, 71, 74, 72, 69, 60, 64, 69, 71, 64, 72, 71, 69]),
    "ode_to_joy": ("Ode to Joy – Beethoven", [n + 12 for n in [
        64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62,
        64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60,
        62, 62, 64, 60, 62, 64, 65, 64, 60, 62, 64, 65, 64, 62, 60, 62, 55,
        64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 62, 60, 60]]),
    "mountain_king": ("In the Hall of the Mountain King – Grieg", [n + 12 for n in [
        59, 61, 62, 64, 66, 62, 66, 65, 61, 65, 64, 60, 64,
        59, 61, 62, 64, 66, 62, 66, 71, 69, 66, 62, 66, 69]]),
    "twinkle": ("Twinkle Twinkle Little Star – Mozart variations", [n + 12 for n in [
        60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60,
        67, 67, 65, 65, 64, 64, 62, 67, 67, 65, 65, 64, 64, 62,
        60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]]),
    "canon": ("Canon in D – Pachelbel", [
        78, 76, 74, 73, 71, 69, 71, 73, 74, 73, 71, 69, 67, 66, 67, 64,
        62, 66, 69, 67, 66, 62, 66, 64, 62, 59, 62, 69, 67, 71, 69, 67]),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(visuals.FONT_DIR / name), size)


def _rgb(h: float, s: float = 0.78, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def _mix(c: tuple, k: float, base=(8, 8, 16)) -> tuple[int, int, int]:
    return tuple(int(b + (x - b) * k) for x, b in zip(c, base))


# ---------------------------------------------------------------- simulations


class Escape:
    kind = "escape"

    def __init__(self, seed: int, rings: int = 14, r0: float = 110, r1: float = 470):
        rnd = random.Random(seed)
        self.rnd = rnd
        self.n = rings
        self.radii = [r0 + (r1 - r0) * i / (rings - 1) for i in range(rings)]
        self.gap = math.radians(rnd.uniform(38, 48))
        base = rnd.uniform(1.0, 1.5)
        self.omega = [base * (1 + 0.04 * i) * (1 if i % 2 == 0 else -1) for i in range(rings)]
        self.theta0 = [rnd.uniform(0, TAU) for _ in range(rings)]
        self.hue0 = rnd.random()
        self.k = 0
        self.x, self.y = rnd.uniform(-20, 20), -20.0
        a, s = rnd.uniform(0, TAU), rnd.uniform(520, 680)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.rb = 15.0
        self.g = 1400.0
        self.t = 0.0
        self.end: float | None = None
        self.events: list[tuple[float, str, int]] = []
        self.last_hit = [-9.0] * rings
        self.broken_at: list[float | None] = [None] * rings

    def theta(self, i: int) -> float:
        return self.theta0[i] + self.omega[i] * self.t

    def color(self, i: int) -> tuple[int, int, int]:
        return _rgb(self.hue0 + 0.75 * i / self.n)

    def _escape(self) -> None:
        self.events.append((self.t, "break", self.k))
        self.broken_at[self.k] = self.t
        self.k += 1
        if self.k == self.n:
            self.end = self.t
            self.events.append((self.t, "finale", 0))

    def step(self, dt: float) -> None:
        self.t += dt
        self.vy += self.g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.k >= self.n:
            return
        r = self.radii[self.k]
        d = math.hypot(self.x, self.y)
        if d + self.rb < r:
            return
        rel = (math.atan2(self.y, self.x) - self.theta(self.k)) % TAU
        half = math.asin(min(1.0, self.rb / r))
        nx, ny = self.x / d, self.y / d
        if half < rel < self.gap - half:  # inside the gap: free to pass
            if d - self.rb > r:
                self._escape()
            return
        if d >= r:  # slipped through at a gap edge
            self.x, self.y = nx * (r + self.rb + 0.5), ny * (r + self.rb + 0.5)
            self._escape()
            return
        vn = self.vx * nx + self.vy * ny
        if vn > 0:
            self.vx -= 2 * vn * nx
            self.vy -= 2 * vn * ny
            a = self.rnd.gauss(0, 0.07)
            ca, sa = math.cos(a), math.sin(a)
            self.vx, self.vy = self.vx * ca - self.vy * sa, self.vx * sa + self.vy * ca
            vn2 = self.vx * nx + self.vy * ny
            if vn2 > -300:  # keep it bouncing instead of rolling
                self.vx += (-300 - vn2) * nx
                self.vy += (-300 - vn2) * ny
            self.events.append((self.t, "bounce", self.k))
            self.last_hit[self.k] = self.t
        self.x, self.y = nx * (r - self.rb - 0.01), ny * (r - self.rb - 0.01)

    # text shown on screen
    def title(self) -> list[str]:
        return ["Can the ball escape", f"all {self.n} rings?"]

    def counter(self) -> str:
        left = self.n - self.k
        return f"{left} ring{'s' if left != 1 else ''} left"

    def finale_text(self) -> str:
        return "ESCAPED!"


class Grow:
    kind = "grow"

    def __init__(self, seed: int, radius: float = 440, inc: float = 3.2):
        rnd = random.Random(seed)
        self.rnd = rnd
        self.R = radius
        self.inc = inc
        self.hue0 = rnd.random()
        self.rb = 16.0
        self.x, self.y = rnd.uniform(-60, 60), rnd.uniform(-120, -40)
        a, s = rnd.uniform(0, TAU), rnd.uniform(650, 800)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.g = 1300.0
        self.t = 0.0
        self.end: float | None = None
        self.events: list[tuple[float, str, int]] = []
        self.bounces = 0
        self.last_hit = -9.0

    def color(self, i: int = 0) -> tuple[int, int, int]:
        return _rgb(self.hue0 + self.bounces * 0.013)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        self.vy += self.g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        d = math.hypot(self.x, self.y) or 1e-9
        if d + self.rb < self.R:
            return
        nx, ny = self.x / d, self.y / d
        vn = self.vx * nx + self.vy * ny
        if vn > 0:
            self.vx -= 2 * vn * nx
            self.vy -= 2 * vn * ny
            a = self.rnd.gauss(0, 0.05)
            ca, sa = math.cos(a), math.sin(a)
            self.vx, self.vy = self.vx * ca - self.vy * sa, self.vx * sa + self.vy * ca
            vn2 = self.vx * nx + self.vy * ny
            if vn2 > -260:
                self.vx += (-260 - vn2) * nx
                self.vy += (-260 - vn2) * ny
            self.bounces += 1
            self.rb += self.inc
            self.last_hit = self.t
            self.events.append((self.t, "bounce", self.bounces))
            if self.R - self.rb < 24:
                self.rb = self.R - 6
                self.end = self.t
                self.events.append((self.t, "finale", 0))
        d2 = max(0.0, self.R - self.rb - 0.01)
        self.x, self.y = nx * d2, ny * d2

    def title(self) -> list[str]:
        return ["Every bounce makes", "the ball bigger"]

    def counter(self) -> str:
        return f"{min(100, round(100 * self.rb / (self.R - 6)))}% full"

    def finale_text(self) -> str:
        return "FULL!"


KINDS = {"escape": Escape, "grow": Grow}


def simulate(kind: str, seed: int, **params) -> object:
    """Physics only (fast) – used to pick seeds whose run has a good length."""
    sim = KINDS[kind](seed, **params)
    dt = 1 / (FPS * SUBSTEPS)
    while sim.end is None and sim.t < 180:
        sim.step(dt)
    return sim


def pick_seed(kind: str, start: int, lo: float = 35, hi: float = 55, **params) -> int:
    for seed in range(start, start + 400):
        sim = simulate(kind, seed, **params)
        if sim.end is not None and lo <= sim.end <= hi:
            return seed
    raise RuntimeError(f"no {kind} seed with a {lo}-{hi}s run near {start}")


# ---------------------------------------------------------------- sound


def _note(midi: int, dur: float = 1.1, vel: float = 0.8) -> np.ndarray:
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    att = np.minimum(1.0, t / 0.003)
    sig = (np.sin(TAU * f * t) * np.exp(-t * 3.2)
           + 0.45 * np.sin(TAU * 2 * f * t) * np.exp(-t * 6)
           + 0.18 * np.sin(TAU * 3.01 * f * t) * np.exp(-t * 11)
           + 0.08 * np.sin(TAU * 4.2 * f * t) * np.exp(-t * 18))
    return (sig * att * vel).astype(np.float32)


def _sparkle(rnd: random.Random, base_midi: int, dur: float = 1.4) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    out = np.zeros_like(t)
    for _ in range(7):  # glassy shimmer: a few high partials with staggered starts
        m = base_midi + 12 + rnd.choice([0, 4, 7, 12, 16, 19, 24])
        f = 440.0 * 2 ** ((m - 69) / 12)
        delay = rnd.uniform(0, 0.12)
        tt = np.clip(t - delay, 0, None)
        out += np.sin(TAU * f * tt) * np.exp(-tt * rnd.uniform(4, 7)) * (t >= delay) * 0.22
    noise = np.random.default_rng(rnd.randrange(1 << 30)).standard_normal(len(t))
    hp = noise - np.convolve(noise, np.ones(8) / 8, mode="same")  # crude high-pass: crisp crack
    out += hp * np.exp(-t * 28) * 0.35
    thump = np.sin(TAU * 70 * t) * np.exp(-t * 14) * 0.5
    return (out + thump).astype(np.float32)


def soundtrack(sim, melody: str, duration: float, seed: int) -> np.ndarray:
    notes = MELODIES[melody][1]
    rnd = random.Random(seed)
    mix = np.zeros(int(SR * (duration + 2)), dtype=np.float32)
    idx, last = 0, -1.0

    def put(t: float, sig: np.ndarray) -> None:
        i = int(t * SR)
        j = min(len(mix), i + len(sig))
        mix[i:j] += sig[: j - i]

    for t, kind, _ in sim.events:
        if kind == "bounce":
            if t - last < 0.045:  # very fast bounces: don't turn the melody into noise
                continue
            last = t
            put(t, _note(notes[idx % len(notes)], vel=0.75))
            idx += 1
        elif kind == "break":
            put(t, _sparkle(rnd, notes[idx % len(notes)] - 12))
        elif kind == "finale":
            root = notes[0] - 12
            for k, iv in enumerate([0, 4, 7, 12, 16, 19, 24]):
                put(t + 0.06 * k, _note(root + iv, dur=2.4, vel=0.55))
            put(t, _sparkle(rnd, root + 12))
    mix = mix[: int(SR * duration)]
    peak = float(np.abs(mix).max()) or 1.0
    return mix / peak * 0.89


def _write_wav(path: Path, mono: np.ndarray) -> None:
    pcm = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- picture


def _background() -> Image.Image:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - CX) / W, (yy - CY) / H)
    base = np.array([16, 14, 30], np.float32) * (1.15 - 0.9 * r)[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


class Particles:
    def __init__(self) -> None:
        self.p = np.zeros((0, 2), np.float32)
        self.v = np.zeros((0, 2), np.float32)
        self.life = np.zeros(0, np.float32)
        self.col = np.zeros((0, 3), np.float32)

    def burst_ring(self, rng: np.random.Generator, r: float, start: float, span: float, color, count: int = 140) -> None:
        a = start + rng.uniform(0, span, count)
        out = rng.uniform(80, 420, count)
        p = np.stack([np.cos(a) * r, np.sin(a) * r], 1)
        v = np.stack([np.cos(a) * out + rng.normal(0, 60, count), np.sin(a) * out + rng.normal(0, 60, count) - 120], 1)
        self._add(p, v, rng.uniform(0.8, 1.6, count), color)

    def burst_point(self, rng: np.random.Generator, x: float, y: float, color, count: int = 160, speed: float = 700) -> None:
        a = rng.uniform(0, TAU, count)
        s = rng.uniform(100, speed, count)
        p = np.tile([[x, y]], (count, 1)).astype(np.float32)
        v = np.stack([np.cos(a) * s, np.sin(a) * s - 200], 1)
        self._add(p, v, rng.uniform(1.0, 2.2, count), color)

    def _add(self, p, v, life, color) -> None:
        self.p = np.concatenate([self.p, p.astype(np.float32)])
        self.v = np.concatenate([self.v, v.astype(np.float32)])
        self.life = np.concatenate([self.life, life.astype(np.float32)])
        self.col = np.concatenate([self.col, np.tile(np.array(color, np.float32), (len(life), 1))])

    def update(self, dt: float) -> None:
        if not len(self.life):
            return
        self.v[:, 1] += 900 * dt
        self.v *= 0.995
        self.p += self.v * dt
        self.life -= dt
        keep = self.life > 0
        self.p, self.v, self.life, self.col = self.p[keep], self.v[keep], self.life[keep], self.col[keep]

    def draw(self, d: ImageDraw.ImageDraw, scale: float) -> None:
        for (x, y), life, c in zip(self.p, self.life, self.col):
            k = min(1.0, life / 0.8)
            rr = (2 + 4 * k) * scale
            X, Y = (CX + x) * scale, (CY + y) * scale
            d.ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=_mix(tuple(int(v) for v in c), k))


class Painter:
    def __init__(self, sim, credit: str, handle: str = "") -> None:
        self.sim = sim
        self.credit = credit
        self.handle = handle
        self.bg = _background()
        self.bg_ss = self.bg.resize((W * SS, H * SS))
        self.parts = Particles()
        self.rng = np.random.default_rng(12345)
        self.trail: list[tuple[float, float, float]] = []
        self.seen = 0
        self.f_title = _font("Poppins-ExtraBold.ttf", 76)
        self.f_count = _font("Poppins-SemiBold.ttf", 46)
        self.f_small = _font("Poppins-SemiBold.ttf", 30)
        self.f_big = {s: _font("Poppins-ExtraBold.ttf", s) for s in range(40, 181, 10)}

    def _new_events(self) -> None:
        sim = self.sim
        for t, kind, i in sim.events[self.seen:]:
            if kind == "break" and isinstance(sim, Escape):
                th = sim.theta(i)
                self.parts.burst_ring(self.rng, sim.radii[i], th + sim.gap, TAU - sim.gap, sim.color(i))
            elif kind == "finale":
                self.parts.burst_point(self.rng, sim.x, sim.y, sim.color(0), 220, 900)
        self.seen = len(sim.events)

    def frame(self) -> Image.Image:
        sim, s = self.sim, SS
        self._new_events()
        self.parts.update(1 / FPS)
        self.trail.append((sim.x, sim.y, sim.rb))
        self.trail = self.trail[-14:]

        img = self.bg_ss.copy()
        d = ImageDraw.Draw(img)
        glow = Image.new("RGB", (W // 4, H // 4))
        g = ImageDraw.Draw(glow)
        q = 0.25

        def ring(r: float, start_deg: float, span_deg: float, col, width: float, flash: float) -> None:
            c = tuple(int(x + (255 - x) * flash) for x in col)
            box = ((CX - r) * s, (CY - r) * s, (CX + r) * s, (CY + r) * s)
            d.arc(box, start_deg, start_deg + span_deg, fill=c, width=int(width * s))
            gb = ((CX - r) * q, (CY - r) * q, (CX + r) * q, (CY + r) * q)
            g.arc(gb, start_deg, start_deg + span_deg, fill=col, width=max(2, int(width * q * 2.2)))

        if isinstance(sim, Escape):
            for i in range(sim.k, sim.n):
                flash = max(0.0, 1 - (sim.t - sim.last_hit[i]) / 0.18) * 0.75
                start = math.degrees(sim.theta(i) + sim.gap)
                ring(sim.radii[i], start, 360 - math.degrees(sim.gap), sim.color(i), 9, flash)
            col = sim.color(min(sim.k, sim.n - 1))
        else:
            flash = max(0.0, 1 - (sim.t - sim.last_hit) / 0.18) * 0.6
            ring(sim.R + 7, 0, 360, sim.color(), 10, flash)
            col = sim.color()

        self.parts.draw(d, s)
        n = len(self.trail)
        for j, (x, y, rb) in enumerate(self.trail[:-1]):
            k = (j + 1) / n
            rr = rb * (0.45 + 0.5 * k) * s
            X, Y = (CX + x) * s, (CY + y) * s
            d.ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=_mix(col, 0.55 * k))
        X, Y, rr = (CX + sim.x) * s, (CY + sim.y) * s, sim.rb * s
        if isinstance(sim, Grow):
            d.ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=col, outline=(255, 255, 255), width=int(4 * s))
        else:
            d.ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=(255, 255, 255), outline=col, width=int(3 * s))
        gx, gy = (CX + sim.x) * q, (CY + sim.y) * q
        gr = (sim.rb * 1.3 if isinstance(sim, Escape) else sim.rb + 10) * q
        g.ellipse((gx - gr, gy - gr, gx + gr, gy + gr), fill=col)

        img = img.resize((W, H), Image.BOX)
        glow = glow.filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
        img = ImageChops.screen(img, ImageChops.screen(glow, glow))
        self._text(img)
        return img

    def _centered(self, d, y: float, text: str, font, fill, stroke: int = 0) -> None:
        w = d.textlength(text, font=font)
        d.text((W / 2 - w / 2, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))

    def _text(self, img: Image.Image) -> None:
        sim = self.sim
        d = ImageDraw.Draw(img)
        lines = sim.title()
        for i, line in enumerate(lines):
            self._centered(d, 210 + i * 92, line, self.f_title, (255, 255, 255), 3)
        self._centered(d, 420, sim.counter(), self.f_count, sim.color(0) if isinstance(sim, Grow) else (255, 214, 120), 2)
        self._centered(d, H - 430, self.credit, self.f_small, (170, 170, 200))
        if self.handle:
            self._centered(d, H - 385, self.handle, self.f_small, (120, 120, 150))
        if sim.end is not None and sim.t >= sim.end:
            k = min(1.0, (sim.t - sim.end) / 0.25)
            size = int(round((60 + 120 * (1 - (1 - k) ** 3)) / 10) * 10)
            font = self.f_big[max(40, min(180, size))]
            text = sim.finale_text()
            w = d.textlength(text, font=font)
            d.text((W / 2 - w / 2, CY - size * 0.7), text, font=font, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))


# ---------------------------------------------------------------- video


def render(kind: str, seed: int, out: Path, melody: str | None = None, handle: str = "", **params) -> dict:
    """Render one simulation to an MP4 (1080x1920, 60 fps) with its generated soundtrack."""
    out.parent.mkdir(parents=True, exist_ok=True)
    melody = melody or list(MELODIES)[seed % len(MELODIES)]
    probe = simulate(kind, seed, **params)
    if probe.end is None:
        raise RuntimeError(f"{kind} seed {seed} does not finish")
    duration = probe.end + OUTRO
    wav = out.with_suffix(".wav")
    _write_wav(wav, soundtrack(probe, melody, duration, seed))

    sim = KINDS[kind](seed, **params)
    painter = Painter(sim, MELODIES[melody][0], handle)
    frames = int(math.ceil(duration * FPS))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    dt = 1 / (FPS * SUBSTEPS)
    for _ in range(frames):
        for _ in range(SUBSTEPS):
            sim.step(dt)
        proc.stdin.write(painter.frame().tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    wav.unlink(missing_ok=True)
    return {"video": out, "duration": duration, "kind": kind, "seed": seed, "melody": melody,
            "melody_name": MELODIES[melody][0], "title": " ".join(sim.title())}
