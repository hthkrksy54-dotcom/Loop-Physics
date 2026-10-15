"""Satisfying physics simulations for vertical Shorts/Reels.

Everything is generated here – physics, picture and sound (every collision plays the next note of a
public-domain melody) – so each video is original and free of third-party rights.

  escape:    a ball bounces inside rotating rings with a gap and breaks out ring by ring
  grow:      a ball grows with every bounce until it fills the circle
  battle:    3–4 coloured balls share the rings – whoever slips out of the last one wins
  polygon:   a ball escapes from counter-rotating nested polygons
  plinko:    a Galton board – hundreds of balls fall through pegs and stack up into a bell curve
  stringart: every bounce leaves a line between successive contact points and draws a pattern
  multiply:  every bounce of the white ball adds a new ball until the circle is full of colour
  pendulum:  a pendulum wave drifts into snakes and waves and falls back in sync (one note per pendulum)

Each seed also picks its own look (palette, background) and parameters (rings, gaps, sizes, speeds).
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
    "nachtmusik": ("Eine kleine Nachtmusik – Mozart", [
        79, 74, 79, 74, 79, 74, 79, 83, 86, 84, 81, 84, 81, 84, 81, 78, 81, 74]),
    "turkish_march": ("Rondo alla Turca – Mozart", [
        71, 69, 68, 69, 72, 74, 72, 71, 72, 76, 77, 76, 75, 76, 83, 81, 80, 81, 83, 81, 80, 81, 84]),
    "minuet": ("Minuet in G – Bach notebook", [
        74, 67, 69, 71, 72, 74, 67, 67, 76, 72, 74, 76, 78, 79, 67, 67,
        72, 74, 72, 71, 69, 71, 72, 71, 69, 67, 66, 67, 69, 71, 67, 71, 69]),
    "blue_danube": ("The Blue Danube – Strauss", [n + 12 for n in [
        62, 62, 66, 69, 69, 81, 81, 78, 78, 62, 62, 66, 69, 69, 81, 81, 79, 79,
        61, 61, 64, 71, 71, 83, 83, 79, 79, 61, 61, 64, 71, 71, 83, 83, 78, 78]]),
    "lullaby": ("Brahms' Lullaby – Brahms", [
        76, 76, 79, 76, 76, 79, 76, 79, 84, 83, 81, 81, 79, 74, 76, 77, 74, 74, 76, 77,
        74, 77, 83, 81, 79, 83, 84, 72, 72, 84, 81, 77, 79, 76, 72, 77, 79, 81, 79,
        72, 72, 84, 81, 77, 79, 76, 72, 77, 76, 74, 72]),
    "greensleeves": ("Greensleeves – traditional", [
        69, 72, 74, 76, 77, 76, 74, 71, 67, 69, 71, 72, 69, 69, 68, 69, 71, 68, 64,
        69, 72, 74, 76, 77, 76, 74, 71, 67, 69, 71, 72, 71, 69, 68, 66, 68, 69, 69]),
    "morning_mood": ("Morning Mood – Grieg", [
        79, 76, 74, 72, 74, 76, 79, 76, 74, 72, 74, 76, 74, 76, 79, 76, 79, 81, 76, 81, 79, 76, 74, 72]),
    "moonlight": ("Moonlight Sonata – Beethoven", [n + 12 for n in
        [56, 61, 64] * 4 + [57, 61, 64] * 2 + [57, 62, 66] * 2 + [56, 60, 66, 56, 61, 64, 56, 61, 63, 54, 60, 63]]),
    "frere_jacques": ("Frère Jacques – traditional", [
        72, 74, 76, 72, 72, 74, 76, 72, 76, 77, 79, 76, 77, 79, 79, 81, 79, 77, 76, 72,
        79, 81, 79, 77, 76, 72, 72, 67, 72, 72, 67, 72]),
}
TIMBRES = ["bell", "marimba", "pluck", "chip", "glass"]

PALETTES = {  # name: (start hue – None = random, hue span, saturation)
    "rainbow": (None, 0.75, 0.78),
    "sunset": (0.86, 0.26, 0.80),
    "ocean": (0.43, 0.32, 0.75),
    "fire": (0.97, 0.16, 0.85),
    "aurora": (0.30, 0.48, 0.70),
    "candy": (None, 0.90, 0.58),
    "neon": (None, 0.50, 0.90),
}
BG_TINTS = [(0.69, 0.53), (0.62, 0.60), (0.78, 0.45), (0.50, 0.50), (0.92, 0.40), (0.0, 0.0)]  # (hue, saturation)
BG_PATTERNS = ["plain", "plain", "dots", "rings", "stars", "rays", "grid"]
TEAMS = [("RED", (255, 72, 72)), ("BLUE", (64, 150, 255)), ("GREEN", (70, 225, 110)), ("YELLOW", (255, 222, 60)),
         ("PINK", (255, 105, 205)), ("ORANGE", (255, 150, 40)), ("PURPLE", (175, 105, 255)), ("CYAN", (70, 235, 240))]
LINEUPS = [(0, 1, 2, 3), (4, 7, 5, 6), (0, 1, 3), (2, 4, 1, 5), (6, 3, 7, 0), (1, 5, 2), (0, 7, 3, 6), (4, 2, 6)]
SHAPES = {5: "pentagons", 6: "hexagons", 7: "heptagons", 8: "octagons"}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(visuals.FONT_DIR / name), size)


def _rgb(h: float, s: float = 0.78, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def _mix(c: tuple, k: float, base=(8, 8, 16)) -> tuple[int, int, int]:
    return tuple(int(b + (x - b) * k) for x, b in zip(c, base))


def _reflect(vx: float, vy: float, nx: float, ny: float, rnd: random.Random, noise: float, vmin: float):
    """Mirror a velocity at a wall with outward normal n, jitter its direction, keep a minimum rebound speed."""
    vn = vx * nx + vy * ny
    vx, vy = vx - 2 * vn * nx, vy - 2 * vn * ny
    a = rnd.gauss(0, noise)
    ca, sa = math.cos(a), math.sin(a)
    vx, vy = vx * ca - vy * sa, vx * sa + vy * ca
    vn2 = vx * nx + vy * ny
    if vn2 > -vmin:  # keep it bouncing instead of rolling
        vx += (-vmin - vn2) * nx
        vy += (-vmin - vn2) * ny
    return vx, vy


def _ngon(a: float, m: int, phi: float) -> list[tuple[float, float]]:
    """Corners of a regular m-gon with apothem a; edge j faces the direction phi + j·2π/m."""
    r = a / math.cos(math.pi / m)
    return [(r * math.cos(phi + (j + 0.5) * TAU / m), r * math.sin(phi + (j + 0.5) * TAU / m)) for j in range(m)]


def _facing(x: float, y: float, m: int, phi: float) -> tuple[int, float, float]:
    """The edge of that m-gon nearest to (x, y) and its outward normal."""
    j = round((math.atan2(y, x) - phi) / (TAU / m)) % m
    a = phi + j * TAU / m
    return j, math.cos(a), math.sin(a)


class Look:
    """Per-seed visual variety (palette, background) from its own RNG, so it never changes the physics."""

    def __init__(self, key: str) -> None:
        self.rnd = rnd = random.Random(f"look-{key}")
        self.palette = rnd.choice(sorted(PALETTES))
        h0, self.span, self.sat = PALETTES[self.palette]
        self.h0 = rnd.random() if h0 is None else h0 + rnd.uniform(-0.03, 0.03)
        self.tint = rnd.choice(BG_TINTS)
        self.pattern = rnd.choice(BG_PATTERNS)

    def color(self, u: float, s: float | None = None, v: float = 1.0) -> tuple[int, int, int]:
        """Palette colour at u in 0..1 (beyond that it runs back and forth)."""
        u = abs((u + 1) % 2 - 1)
        return _rgb(self.h0 + self.span * u, self.sat if s is None else s, v)

    def background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx, dy = xx - CX, yy - CY
        shade = 1.15 - 0.9 * np.hypot(dx / W, dy / H)
        if self.pattern == "dots":
            shade += 0.35 * np.clip(3 - np.hypot(xx % 48 - 24, yy % 48 - 24), 0, 1)
        elif self.pattern == "rings":
            shade += 0.2 * np.clip(1.5 - np.abs(np.hypot(dx, dy) % 64 - 32), 0, 1)
        elif self.pattern == "grid":
            shade += 0.16 * np.clip(1.2 - np.minimum(np.abs(xx % 90 - 45), np.abs(yy % 90 - 45)), 0, 1)
        elif self.pattern == "rays":
            shade *= 1 + 0.12 * np.cos(np.arctan2(dy, dx) * 16)
        elif self.pattern == "stars":
            for _ in range(320):
                x, y = self.rnd.randrange(W - 1), self.rnd.randrange(H - 1)
                shade[y:y + self.rnd.choice((1, 1, 2)), x:x + 2] += self.rnd.uniform(0.5, 2.2)
        h, s = self.tint
        tint = np.array(_rgb(h, s, 0.118) if s else (22, 22, 27), np.float32)
        return Image.fromarray(np.clip(tint * shade[..., None], 0, 255).astype(np.uint8))


class Ball:
    """A moving disc (simulation coordinates: origin at the centre, y pointing down, pixels)."""
    __slots__ = ("x", "y", "vx", "vy", "rb", "col", "name")

    def __init__(self, x: float, y: float, vx: float, vy: float, rb: float, col=(255, 255, 255), name: str = ""):
        self.x, self.y, self.vx, self.vy, self.rb, self.col, self.name = x, y, vx, vy, rb, col, name

    def move(self, dt: float, g: float) -> None:
        self.vy += g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt


# ---------------------------------------------------------------- simulations


class Sim:
    """A simulation kind: physics in step(), picture in draw(), on-screen text in title()/counter()/finale()."""
    kind = ""
    counter_color = (255, 214, 120)

    def __init__(self, seed: int) -> None:
        self.rnd = random.Random(seed)  # physics only
        self.look = Look(f"{self.kind}-{seed}")  # visuals only
        self.t = 0.0
        self.end: float | None = None
        self.events: list[tuple[float, str, int]] = []

    def finish(self) -> None:
        self.end = self.t
        self.events.append((self.t, "finale", 0))

    def prepare(self, p: Painter) -> None:
        """Draw static scenery into the painter's persistent layers."""

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        """React to a physics event in the picture (particles, stamping onto the persistent layers)."""

    def step(self, dt: float) -> None:
        raise NotImplementedError

    def draw(self, p: Painter) -> None:
        raise NotImplementedError

    def title(self) -> list[str]:
        raise NotImplementedError

    def counter(self) -> str:
        return ""

    def finale(self) -> list[tuple[str, tuple]]:
        return [(self.finale_text(), (255, 255, 255))]

    def finale_text(self) -> str:
        return ""

    def credit(self, melody_name: str) -> str:
        """Line under the picture: normally the melody the bounces play."""
        return melody_name

    def draw_text(self, p: Painter, d: ImageDraw.ImageDraw) -> None:
        for i, line in enumerate(self.title()):
            p.centered(d, 210 + i * 92, line, p.f_title, (255, 255, 255), 3)
        p.centered(d, 420, self.counter(), p.f_count, self.counter_color, 2)
        if self.end is not None and self.t >= self.end:
            p.big_text(d, self.finale(), self.t - self.end)


class Escape(Sim):
    kind = "escape"
    RINGS = (10, 16)
    GAP = (48.0, 62.0)  # gap in degrees for the fewest/most rings, tuned for ~45 s runs

    def __init__(self, seed: int, rings: int | None = None, r0: float = 110, r1: float = 470):
        super().__init__(seed)
        rnd = self.rnd
        self.n = n = rings or rnd.randint(*self.RINGS)
        self.radii = [r0 + (r1 - r0) * i / (n - 1) for i in range(n)]
        lo, hi = self.RINGS
        deg = self.GAP[0] + (self.GAP[1] - self.GAP[0]) * (n - lo) / max(1, hi - lo)
        self.gap = math.radians(deg * rnd.uniform(0.92, 1.08))
        base, alt = rnd.uniform(0.8, 1.6), rnd.random() < 0.7  # alternating directions, or one big swirl
        self.omega = [base * (1 + 0.04 * i) * (-1 if alt and i % 2 else 1) for i in range(n)]
        self.theta0 = [rnd.uniform(0, TAU) for _ in range(n)]
        self.g = 1400.0
        self.balls = self.make_balls(rnd)
        self.k = 0
        self.last_hit = [-9.0] * n
        self.breaker = [0] * n
        self.width = min(self.look.rnd.choice([7, 9, 9, 11]), (r1 - r0) / (n - 1) * 0.45)

    def make_balls(self, rnd: random.Random) -> list[Ball]:
        a, s = rnd.uniform(0, TAU), rnd.uniform(520, 680)
        return [Ball(rnd.uniform(-20, 20), -20.0, math.cos(a) * s, math.sin(a) * s, rnd.uniform(12, 17))]

    def theta(self, i: int) -> float:
        return self.theta0[i] + self.omega[i] * self.t

    def color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / self.n)

    def _escape(self, j: int) -> None:
        self.events.append((self.t, "break", self.k))
        self.breaker[self.k] = j
        self.k += 1
        if self.k == self.n:
            self.finish()

    def step(self, dt: float) -> None:
        self.t += dt
        for b in self.balls:
            b.move(dt, self.g)
        if self.k >= self.n:
            return
        if len(self.balls) > 1:
            self._collide()
        for j, b in enumerate(self.balls):
            if self.k < self.n:
                self._wall(j, b)

    def _wall(self, j: int, b: Ball) -> None:
        r = self.radii[self.k]
        d = math.hypot(b.x, b.y)
        if d + b.rb < r:
            return
        rel = (math.atan2(b.y, b.x) - self.theta(self.k)) % TAU
        half = math.asin(min(1.0, b.rb / r))
        nx, ny = b.x / d, b.y / d
        if half < rel < self.gap - half:  # inside the gap: free to pass
            if d - b.rb > r:
                self._escape(j)
            return
        if d >= r and (rel < self.gap + half or rel > TAU - half):  # slipped through at a gap edge
            b.x, b.y = nx * (r + b.rb + 0.5), ny * (r + b.rb + 0.5)
            self._escape(j)
            return
        if b.vx * nx + b.vy * ny > 0:
            b.vx, b.vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, 0.07, 300)
            self.events.append((self.t, "bounce", self.k))
            self.last_hit[self.k] = self.t
        b.x, b.y = nx * (r - b.rb - 0.01), ny * (r - b.rb - 0.01)

    def _collide(self) -> None:
        """Equal-mass elastic collisions between the balls."""
        bs = self.balls
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                dx, dy, md = b.x - a.x, b.y - a.y, a.rb + b.rb
                if abs(dx) >= md or abs(dy) >= md:
                    continue
                d = math.hypot(dx, dy)
                if d >= md or d == 0:
                    continue
                nx, ny, push = dx / d, dy / d, (md - d) / 2
                a.x, a.y, b.x, b.y = a.x - nx * push, a.y - ny * push, b.x + nx * push, b.y + ny * push
                vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                if vn < 0:
                    a.vx, a.vy, b.vx, b.vy = a.vx + vn * nx, a.vy + vn * ny, b.vx - vn * nx, b.vy - vn * ny
                    if vn < -150:
                        self.events.append((self.t, "clack", 0))

    def title(self) -> list[str]:
        return ["Can the ball escape", f"all {self.n} rings?"]

    def counter(self) -> str:
        left = self.n - self.k
        return f"{left} ring{'s' if left != 1 else ''} left"

    def finale_text(self) -> str:
        return "ESCAPED!"

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            p.parts.burst_ring(p.rng, self.radii[i], self.theta(i) + self.gap, TAU - self.gap, self.burst_color(i))
        elif kind == "finale":
            b = self.balls[self.breaker[-1]]
            p.parts.burst_point(p.rng, b.x, b.y, self.burst_color(-1), 220, 900)

    def burst_color(self, i: int) -> tuple[int, int, int]:
        return self.color(max(0, i))

    def draw(self, p: Painter) -> None:
        for i in range(self.k, self.n):
            flash = max(0.0, 1 - (self.t - self.last_hit[i]) / 0.18) * 0.75
            start = math.degrees(self.theta(i) + self.gap)
            p.ring(self.radii[i], start, 360 - math.degrees(self.gap), self.color(i), self.width, flash)
        p.particles()
        col = self.color(min(self.k, self.n - 1))
        for j, b in enumerate(self.balls):
            self.paint_ball(p, j, b, col)

    def paint_ball(self, p: Painter, j: int, b: Ball, col) -> None:
        p.trail(j, b.x, b.y, b.rb, col)
        p.ball(b.x, b.y, b.rb, (255, 255, 255), col, 3)
        p.glow_disc(b.x, b.y, b.rb * 1.3, col)


class Battle(Escape):
    """Several coloured balls in one ring system; a ring breaks for everyone, the last one decides."""
    kind = "battle"
    RINGS = (15, 20)
    GAP = (27.0, 33.0)

    def __init__(self, seed: int, rings: int | None = None, r0: float = 125, r1: float = 470):
        super().__init__(seed, rings, r0, r1)

    def make_balls(self, rnd: random.Random) -> list[Ball]:
        team, rb, a0 = rnd.choice(LINEUPS), rnd.uniform(15, 18), rnd.uniform(0, TAU)
        balls = []
        for j, c in enumerate(team):
            a, va, s = a0 + TAU * j / len(team), rnd.uniform(0, TAU), rnd.uniform(480, 640)
            name, col = TEAMS[c]
            balls.append(Ball(math.cos(a) * 50, math.sin(a) * 50, math.cos(va) * s, math.sin(va) * s, rb, col, name))
        return balls

    def color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / self.n, s=0.32, v=0.9)  # soft rings, so the team colours stand out

    def burst_color(self, i: int) -> tuple[int, int, int]:
        return self.balls[self.breaker[i]].col

    def paint_ball(self, p: Painter, j: int, b: Ball, col) -> None:
        p.trail(j, b.x, b.y, b.rb, b.col)
        p.ball(b.x, b.y, b.rb, b.col, (255, 255, 255), 3)
        p.glow_disc(b.x, b.y, b.rb * 1.5, b.col)

    def title(self) -> list[str]:
        return ["Which color", "escapes first?"]

    def finale(self) -> list[tuple[str, tuple]]:
        b = self.balls[self.breaker[-1]]
        return [(b.name, b.col), ("WINS!", (255, 255, 255))]


class Polygon(Sim):
    """Escape from nested polygons; neighbours turn in opposite directions and are spaced so they never touch."""
    kind = "polygon"
    GAP = {5: 0.36, 6: 0.46, 7: 0.70, 8: 0.90}  # gap as a share of the edge length, tuned for ~45 s runs

    def __init__(self, seed: int, sides: int | None = None):
        super().__init__(seed)
        rnd = self.rnd
        self.m = m = sides or rnd.choice([5, 6, 6, 7, 8])
        c = math.cos(math.pi / m)
        self.ap = [100.0]  # apothems
        while (self.ap[-1] / c + 10) / c < 480:
            self.ap.append(self.ap[-1] / c + 10)
        self.n = n = len(self.ap)
        base = rnd.uniform(0.6, 1.1)
        self.omega = [base * (1 + 0.05 * i) * (-1 if i % 2 else 1) for i in range(n)]
        self.phi0 = [rnd.uniform(0, TAU) for _ in range(n)]
        edge = [2 * a * math.tan(math.pi / m) for a in self.ap]
        share = self.GAP[m] * rnd.uniform(0.9, 1.1)
        self.gw = [max(40.0, share * e) for e in edge]                     # gap width (on edge 0)
        self.gc = [rnd.uniform(-0.5, 0.5) * (e - w) for e, w in zip(edge, self.gw)]  # gap centre along the edge
        a, s = rnd.uniform(0, TAU), rnd.uniform(450, 600)
        self.ball = Ball(rnd.uniform(-15, 15), -15.0, math.cos(a) * s, math.sin(a) * s, rnd.uniform(11, 14))
        self.g = 1400.0
        self.k = 0
        self.last_hit = [-9.0] * n
        self.width = self.look.rnd.choice([6, 7, 8])

    def phi(self, i: int) -> float:
        return self.phi0[i] + self.omega[i] * self.t

    def color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / self.n)

    def _escape(self) -> None:
        self.events.append((self.t, "break", self.k))
        self.k += 1
        if self.k == self.n:
            self.finish()

    def step(self, dt: float) -> None:
        self.t += dt
        b = self.ball
        b.move(dt, self.g)
        if self.k >= self.n:
            return
        a, w, phi = self.ap[self.k], self.omega[self.k], self.phi(self.k)
        j, nx, ny = _facing(b.x, b.y, self.m, phi)
        s = b.x * nx + b.y * ny
        if s + b.rb < a:
            return
        off = abs(b.y * nx - b.x * ny - self.gc[self.k]) if j == 0 else 1e9  # distance from the gap centre
        hw = self.gw[self.k] / 2
        if off < hw - b.rb:  # inside the gap: free to pass
            if s - b.rb > a:
                self._escape()
            return
        if off < hw + b.rb and s >= a:  # slipped through at a gap edge
            b.x, b.y = b.x + (a + b.rb + 0.5 - s) * nx, b.y + (a + b.rb + 0.5 - s) * ny
            self._escape()
            return
        cx, cy = b.x + nx * b.rb, b.y + ny * b.rb
        wx, wy = -w * cy, w * cx  # the wall moves: bounce off it in its own frame
        if (b.vx - wx) * nx + (b.vy - wy) * ny > 0:
            vx, vy = _reflect(b.vx - wx, b.vy - wy, nx, ny, self.rnd, 0.06, 300)
            sp = math.hypot(vx + wx, vy + wy)
            k = min(1.0, 1500 / sp)
            b.vx, b.vy = (vx + wx) * k, (vy + wy) * k
            self.events.append((self.t, "bounce", self.k))
            self.last_hit[self.k] = self.t
        b.x, b.y = b.x - (s - a + b.rb + 0.01) * nx, b.y - (s - a + b.rb + 0.01) * ny

    def outline(self, i: int) -> list[tuple[float, float]]:
        """Polygon i as an open path: from one end of the gap around the corners to the other end."""
        phi, a = self.phi(i), self.ap[i]
        nx, ny = math.cos(phi), math.sin(phi)
        g0, g1 = self.gc[i] - self.gw[i] / 2, self.gc[i] + self.gw[i] / 2
        return [(a * nx - g1 * ny, a * ny + g1 * nx), *_ngon(a, self.m, phi), (a * nx - g0 * ny, a * ny + g0 * nx)]

    def title(self) -> list[str]:
        return ["Can the ball escape", f"all {self.n} {SHAPES[self.m]}?"]

    def counter(self) -> str:
        left = self.n - self.k
        return f"{left} {SHAPES[self.m] if left != 1 else SHAPES[self.m][:-1]} left"

    def finale_text(self) -> str:
        return "ESCAPED!"

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            p.parts.burst_path(p.rng, self.outline(i), self.color(i))
        elif kind == "finale":
            p.parts.burst_point(p.rng, self.ball.x, self.ball.y, self.color(self.n - 1), 220, 900)

    def draw(self, p: Painter) -> None:
        for i in range(self.k, self.n):
            flash = max(0.0, 1 - (self.t - self.last_hit[i]) / 0.18) * 0.75
            p.line(self.outline(i), self.color(i), self.width, flash)
        p.particles()
        b, col = self.ball, self.color(min(self.k, self.n - 1))
        p.trail(0, b.x, b.y, b.rb, col)
        p.ball(b.x, b.y, b.rb, (255, 255, 255), col, 3)
        p.glow_disc(b.x, b.y, b.rb * 1.3, col)


class Grow(Sim):
    kind = "grow"

    def __init__(self, seed: int, radius: float | None = None, inc: float | None = None):
        super().__init__(seed)
        rnd = self.rnd
        self.R = radius or rnd.uniform(400, 450)
        self.inc = inc or rnd.uniform(2.7, 3.7)
        self.rb = rnd.uniform(12, 20)
        self.x, self.y = rnd.uniform(-60, 60), rnd.uniform(-120, -40)
        a, s = rnd.uniform(0, TAU), rnd.uniform(650, 800)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.g = rnd.uniform(1150, 1450)
        self.bounces = 0
        self.last_hit = -9.0
        self.width = self.look.rnd.choice([8, 10, 12])

    def color(self, i: int = 0) -> tuple[int, int, int]:
        return self.look.color(self.bounces * 0.017)

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
        if self.vx * nx + self.vy * ny > 0:
            self.vx, self.vy = _reflect(self.vx, self.vy, nx, ny, self.rnd, 0.05, 260)
            self.bounces += 1
            self.rb += self.inc
            self.last_hit = self.t
            self.events.append((self.t, "bounce", self.bounces))
            if self.R - self.rb < 24:
                self.rb = self.R - 6
                self.finish()
        d2 = max(0.0, self.R - self.rb - 0.01)
        self.x, self.y = nx * d2, ny * d2

    def title(self) -> list[str]:
        return ["Every bounce makes", "the ball bigger"]

    def counter(self) -> str:
        return f"{min(100, round(100 * self.rb / (self.R - 6)))}% full"

    def finale_text(self) -> str:
        return "FULL!"

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return self.color()

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "finale":
            p.parts.burst_point(p.rng, self.x, self.y, self.color(), 220, 900)

    def draw(self, p: Painter) -> None:
        flash = max(0.0, 1 - (self.t - self.last_hit) / 0.18) * 0.6
        col = self.color()
        p.ring(self.R + 2 + self.width / 2, 0, 360, col, self.width, flash)
        p.particles()
        p.trail(0, self.x, self.y, self.rb, col)
        p.ball(self.x, self.y, self.rb, col, (255, 255, 255), 4)
        p.glow_disc(self.x, self.y, self.rb + 10, col)


class Plinko(Sim):
    """Galton board: balls drop onto a triangle of pegs and settle in bins (each landing plays a note)."""
    kind = "plinko"

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.rows = R = rnd.choice([10, 12, 14])
        self.N = rnd.randint(220, 280)
        self.interval = (rnd.uniform(37, 52) - 3.0) / self.N
        self.sx = 960 / (R + 1)            # peg and bin spacing
        self.rp = 5.0
        self.rb = rnd.uniform(5.5, 6.5)
        self.pitch = 2 * self.rb + 1
        self.per_row = int((self.sx - 6) // self.pitch)
        self.top, self.floor = -380.0, 470.0  # first peg row, bin floor
        peak = 1.1 * self.N * math.comb(R, R // 2) / 2 ** R / self.per_row * self.pitch
        self.dy = min(64.0, max(38.0, (self.floor - peak / 0.65 - self.top) / (R - 0.35)))  # bins ~2/3 full
        self.ybin = self.top + (R - 0.35) * self.dy
        self.g = 1500.0
        self.balls: list[list] = []        # in flight: [x, y, vx, vy, index, bin slot, last peg]
        self.released = self.landed = 0
        self.count = [0] * (R + 1)
        self.pos: list[tuple[float, float]] = [(0.0, 0.0)] * self.N
        self.hits: dict[tuple[int, int], float] = {}

    def peg(self, r: int, j: int) -> tuple[float, float]:
        return (j - r / 2) * self.sx, self.top + r * self.dy

    def _slot(self, j: int) -> tuple[float, float]:
        row, col = divmod(self.count[j], self.per_row)
        self.count[j] += 1
        x = (j - self.rows / 2) * self.sx + (col - (self.per_row - 1) / 2) * self.pitch
        return x, self.floor - 3 - self.rb - row * self.pitch

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        rnd, R, sx = self.rnd, self.rows, self.sx
        while self.released < self.N and self.t >= 0.5 + self.released * self.interval:
            self.balls.append([rnd.uniform(-2, 2), self.top - 45, rnd.gauss(0, 10), 0.0, self.released, None, None])
            self.released += 1
        md, wall = self.rp + self.rb, (R + 1) / 2 * sx - self.rb
        for b in list(self.balls):
            x, y, vx, vy, i, slot, last = b
            vy += self.g * dt
            if slot:  # inside its bin: glide into the next free place of the stack
                x += (slot[0] - x) * min(1.0, 14 * dt)
                y += vy * dt
                if y >= slot[1]:
                    self.balls.remove(b)
                    self.pos[i] = slot
                    self.landed += 1
                    self.events.append((self.t, "land", i))
                    if self.landed == self.N:
                        self.finish()
                    continue
            else:
                x, y = x + vx * dt, y + vy * dt
                if abs(x) > wall:
                    x, vx = math.copysign(wall, x), -vx * 0.5
                r = round((y - self.top) / self.dy)
                j = round(x / sx + r / 2)
                if 0 <= r < R and 0 <= j <= r:
                    px, py = self.peg(r, j)
                    dx, dy = x - px, y - py
                    d = math.hypot(dx, dy)
                    if d < md:
                        nx, ny = (dx / d, dy / d) if d else (0.0, -1.0)
                        vn = vx * nx + vy * ny
                        if vn < 0 and (r, j) != last:  # a new peg: hop left or right onto the next row's peg
                            side = 1 if rnd.random() < 0.5 + 0.15 * max(-1.0, min(1.0, dx / md)) else -1
                            vy = -0.3 * abs(vn)
                            fall = (-vy + math.sqrt(vy * vy + 2 * self.g * self.dy)) / self.g
                            vx = side * sx / 2 / fall * rnd.uniform(0.9, 1.05)
                            last = (r, j)
                            self.hits[last] = self.t
                        elif vn < 0:  # same peg again: plain damped bounce
                            vx, vy = vx - 1.4 * vn * nx, vy - 1.4 * vn * ny
                        x, y = px + nx * md, py + ny * md
                if y > self.ybin:
                    slot = self._slot(min(R, max(0, round(x / sx + R / 2))))
            b[:] = x, y, vx, vy, i, slot, last

    def ball_color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / self.N)

    def prepare(self, p: Painter) -> None:
        R, sx = self.rows, self.sx
        for k in range(R + 2):  # bin walls and floor
            x = (k - (R + 1) / 2) * sx
            p.line([(x, self.ybin + 10), (x, self.floor)], (90, 90, 120), 3, glow=None, d=p.base_d)
        p.line([(-(R + 1) / 2 * sx, self.floor), ((R + 1) / 2 * sx, self.floor)], (120, 120, 155), 4, glow=None, d=p.base_d)
        for r in range(R):
            for j in range(r + 1):
                p.ball(*self.peg(r, j), self.rp, (170, 170, 200), d=p.base_d)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "land":
            x, y = self.pos[i]
            col = self.ball_color(i)
            p.ball(x, y, self.rb, col, d=p.base_d)
            p.glow_disc(x, y, self.rb * 1.6, _mix(col, 0.35), g=p.base_g)
        elif kind == "finale":
            pts = self.curve()
            x, y = min(pts, key=lambda q: q[1])
            p.parts.burst_point(p.rng, x, y, self.look.color(0.5), 220, 900)

    def curve(self) -> list[tuple[float, float]]:
        """Normal curve fitted to the stacks, in screen coordinates."""
        idx = [j for j, c in enumerate(self.count) for _ in range(c)] or [self.rows / 2]
        mu = sum(idx) / len(idx)
        sd = max(0.5, (sum((j - mu) ** 2 for j in idx) / len(idx)) ** 0.5)
        pts = []
        for k in range(161):
            u = -0.5 + (self.rows + 1) * k / 160
            n = len(idx) / (sd * math.sqrt(TAU)) * math.exp(-0.5 * ((u - mu) / sd) ** 2)
            pts.append(((u - self.rows / 2) * self.sx, self.floor - 3 - n / self.per_row * self.pitch))
        return pts

    def draw(self, p: Painter) -> None:
        for (r, j), th in self.hits.items():
            k = 1 - (self.t - th) / 0.25
            if k > 0:
                col = self.look.color(r / self.rows)
                p.ball(*self.peg(r, j), self.rp + 2 * k, _mix(col, 0.4 + 0.6 * k, (170, 170, 200)))
                p.glow_disc(*self.peg(r, j), self.rp * 3, _mix(col, k))
        if self.end is not None:  # finale: draw the bell curve over the stacks
            pts = self.curve()
            pts = pts[:max(2, int(len(pts) * min(1.0, (self.t - self.end) / 0.8)))]
            p.line(pts, (255, 255, 255), 5, glow=self.look.color(0.5))
        p.particles()
        for x, y, _, _, i, *_ in self.balls:
            col = self.ball_color(i)
            p.trail(i, x, y, self.rb, col, 6)
            p.ball(x, y, self.rb, col, (255, 255, 255), 1.5)
            p.glow_disc(x, y, self.rb * 1.8, col)

    def title(self) -> list[str]:
        return [f"Will {self.N} balls make", "a bell curve?"]

    def counter(self) -> str:
        return f"{self.landed} / {self.N}"

    def finale_text(self) -> str:
        return "BELL CURVE!"


class StringArt(Sim):
    """A ball speeding up inside a shape; every bounce leaves a line to the previous contact point."""
    kind = "stringart"

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.m = rnd.choice([0, 0, 0, 0, 5, 6])  # 0 = circle, else a regular polygon with a flat bottom
        self.R = 440.0 if not self.m else 435 * math.cos(math.pi / self.m)
        self.phi = math.pi / 2
        self.N = rnd.randint(110, 160)
        self.acc = rnd.uniform(1.009, 1.014)
        self.noise = rnd.uniform(0.012, 0.04)
        self.g = rnd.choice([0.0, 0.0, 0.0, 300.0])
        # launch along a line that misses the centre: the chords then wrap around an empty inner circle
        a, b = rnd.uniform(0, TAU), self.R * rnd.uniform(0.3, 0.75)
        s = rnd.uniform(700, 820) * {0: 1.5, 6: 1.15}.get(self.m, 1.0)  # longer chords: faster ball
        self.ball = Ball(b * math.cos(a), b * math.sin(a), -math.sin(a) * s, math.cos(a) * s, rnd.uniform(10, 13))
        self.pts = [(self.ball.x, self.ball.y)]
        self.last_hit = -9.0

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        b = self.ball
        b.move(dt, self.g)
        if self.m:
            _, nx, ny = _facing(b.x, b.y, self.m, self.phi)
            s = b.x * nx + b.y * ny
        else:
            s = math.hypot(b.x, b.y) or 1e-9
            nx, ny = b.x / s, b.y / s
        if s + b.rb < self.R:
            return
        b.x, b.y = b.x - (s + b.rb - self.R) * nx, b.y - (s + b.rb - self.R) * ny
        if b.vx * nx + b.vy * ny > 0:
            vx, vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, self.noise, 200 if self.g else 0)
            k = min(self.acc, 2800 / math.hypot(vx, vy))
            b.vx, b.vy = vx * k, vy * k
            self.pts.append((b.x + nx * b.rb, b.y + ny * b.rb))
            self.last_hit = self.t
            self.events.append((self.t, "bounce", len(self.pts) - 1))
            if len(self.pts) > self.N:
                self.finish()

    def line_color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / self.N)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "bounce":
            col = self.line_color(i)
            p.line(self.pts[i - 1:i + 1], col, 1.6, glow=_mix(col, 0.4), d=p.base_d, g=p.base_g)
        elif kind == "finale":
            p.parts.burst_point(p.rng, self.ball.x, self.ball.y, self.line_color(self.N), 220, 900)

    def draw(self, p: Painter) -> None:
        n = len(self.pts) - 1
        col = self.line_color(n)
        flash = max(0.0, 1 - (self.t - self.last_hit) / 0.18) * 0.6
        if self.m:
            p.line(_ngon(self.R + 4, self.m, self.phi), col, 7, flash, closed=True)
        else:
            p.ring(self.R + 4, 0, 360, col, 7, flash)
        p.particles()
        if self.end is None:
            b = self.ball
            p.trail(0, b.x, b.y, b.rb, col, 8)
            p.line([self.pts[-1], (b.x, b.y)], (255, 255, 255), 2, glow=None)
            p.ball(b.x, b.y, b.rb, (255, 255, 255), col, 3)
            p.glow_disc(b.x, b.y, b.rb * 1.6, col)

    def title(self) -> list[str]:
        return [f"What will {self.N}", "bounces draw?"]

    def counter(self) -> str:
        return f"{min(self.N, len(self.pts) - 1)} / {self.N} lines"

    def finale_text(self) -> str:
        return "BEAUTIFUL!"


class Multiply(Sim):
    """Every bounce of the white ball adds a new ball – until the circle is a cloud of colour."""
    kind = "multiply"

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.R = rnd.uniform(420, 450)
        self.N = rnd.choice([40, 50, 64, 75])
        self.g = rnd.uniform(1300, 1700)
        self.rb_new = rnd.uniform(12, 16)
        a, s = rnd.uniform(0, TAU), rnd.uniform(750, 900)
        self.balls = [Ball(rnd.uniform(-40, 40), -100.0, math.cos(a) * s, math.sin(a) * s, 16.0)]
        self.last_hit = -9.0

    def step(self, dt: float) -> None:
        self.t += dt
        for j, b in enumerate(self.balls):
            b.move(dt, self.g)
            d = math.hypot(b.x, b.y) or 1e-9
            if d + b.rb < self.R:
                continue
            nx, ny = b.x / d, b.y / d
            if b.vx * nx + b.vy * ny > 0:
                b.vx, b.vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, 0.07, 300)
                if j == 0 and self.end is None:
                    n = len(self.balls)
                    a, sp = self.rnd.uniform(0, TAU), self.rnd.uniform(250, 550)
                    self.balls.append(Ball(b.x - nx * 30, b.y - ny * 30, b.vx * 0.5 + math.cos(a) * sp,
                                           b.vy * 0.5 + math.sin(a) * sp, self.rb_new, self.look.color(n / self.N)))
                    self.last_hit = self.t
                    self.events.append((self.t, "bounce", n))
                    if n >= self.N:
                        self.finish()
            d2 = self.R - b.rb - 0.01
            b.x, b.y = nx * d2, ny * d2

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "bounce" and i < len(self.balls):
            b = self.balls[i]
            p.parts.burst_point(p.rng, b.x, b.y, b.col, 14, 260)
        elif kind == "finale":
            p.parts.burst_point(p.rng, 0, 0, self.look.color(1.0), 240, 950)

    def draw(self, p: Painter) -> None:
        n = len(self.balls) - 1
        col = self.look.color(n / self.N)
        flash = max(0.0, 1 - (self.t - self.last_hit) / 0.18) * 0.6
        p.ring(self.R + 6, 0, 360, col, 9, flash)
        p.particles()
        for b in self.balls[1:]:
            p.ball(b.x, b.y, b.rb, b.col)
            p.glow_disc(b.x, b.y, b.rb * 1.5, b.col)
        lead = self.balls[0]
        p.trail(0, lead.x, lead.y, lead.rb, col)
        p.ball(lead.x, lead.y, lead.rb, (255, 255, 255), col, 3)
        p.glow_disc(lead.x, lead.y, lead.rb * 1.8, (255, 255, 255))

    def title(self) -> list[str]:
        return ["Every bounce adds", "a new ball"]

    def counter(self) -> str:
        return f"{min(self.N, len(self.balls) - 1)} / {self.N} balls"

    def finale_text(self) -> str:
        return f"{self.N} BALLS!"


class Pendulum(Sim):
    """Pendulum wave seen from below: K bobs with slightly different swing rates drift into waves and
    snakes and fall back in line at the end. Each bob rings its own note when it reaches the right side."""
    kind = "pendulum"
    counter_color = (150, 230, 255)

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.K = rnd.choice([12, 13, 15])
        self.T = rnd.uniform(34, 54)  # everything lines up again at T
        n0 = rnd.choice([10, 12, 14])
        self.f = [(n0 + i) / self.T for i in range(self.K)]  # swings per second, slowest at the top
        self.A = rnd.uniform(330, 380)
        self.top, self.bottom = -390.0, 440.0
        self.rb = rnd.uniform(15, 19)
        self.sign = [1.0] * self.K
        self.hit = [-9.0] * self.K
        self.snake = self.look.rnd.random() < 0.7

    def pos(self, i: int) -> tuple[float, float]:
        y = self.top + (self.bottom - self.top) * i / (self.K - 1)
        return self.A * math.cos(TAU * self.f[i] * min(self.t, self.T)), y  # the in-sync line freezes at the end

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        for i, f in enumerate(self.f):
            s = math.sin(TAU * f * self.t)
            if s >= 0 > self.sign[i]:  # reached the right end
                self.hit[i] = self.t
                self.events.append((self.t, "tone", i))
            self.sign[i] = s
        if self.t >= self.T:
            self.finish()

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "finale":
            for j in range(self.K):
                x, y = self.pos(j)
                p.parts.burst_point(p.rng, x, y, self.look.color(j / self.K), 16, 500)

    def draw(self, p: Painter) -> None:
        pts = [self.pos(i) for i in range(self.K)]
        for i, (x, y) in enumerate(pts):
            col = self.look.color(i / self.K)
            p.line([(-self.A - self.rb, y), (self.A + self.rb, y)], _mix(col, 0.22), 2, glow=None)
            k = max(0.0, 1 - (self.t - self.hit[i]) / 0.25)
            if k:
                p.ball(self.A + self.rb + 10, y, 6 + 6 * k, _mix(col, 0.4 + 0.6 * k))
                p.glow_disc(self.A + self.rb + 10, y, 30 * k, col)
        if self.snake:
            p.line(pts, (255, 255, 255), 2.2, glow=_mix(self.look.color(0.5), 0.6))
        p.particles()
        for i, (x, y) in enumerate(pts):
            col = self.look.color(i / self.K)
            p.trail(i, x, y, self.rb, col, 8)
            p.ball(x, y, self.rb, col, (255, 255, 255), 2)
            p.glow_disc(x, y, self.rb * 1.7, col)

    def title(self) -> list[str]:
        return [f"{self.K} pendulums,", "one perfect moment"]

    def counter(self) -> str:
        return f"in sync again in {max(0, math.ceil(self.T - self.t))} s" if self.end is None else "in sync!"

    def finale_text(self) -> str:
        return "IN SYNC!"

    def credit(self, melody_name: str) -> str:
        return "Every pendulum plays its own note"


KINDS = {k.kind: k for k in (Escape, Grow, Battle, Polygon, Plinko, StringArt, Multiply, Pendulum)}


def simulate(kind: str, seed: int, **params) -> Sim:
    """Physics only (fast) – used to pick seeds whose run has a good length."""
    sim = KINDS[kind](seed, **params)
    dt = 1 / (FPS * SUBSTEPS)
    while sim.end is None and sim.t < 180:
        sim.step(dt)
    return sim


def pick_seed(kind: str, start: int, lo: float = 35, hi: float = 55, tries: int = 400, **params) -> int:
    for seed in range(start, start + tries):
        sim = simulate(kind, seed, **params)
        if sim.end is not None and lo <= sim.end <= hi:
            return seed
    raise RuntimeError(f"no {kind} seed with a {lo}-{hi}s run near {start}")


# ---------------------------------------------------------------- sound


def _note(midi: int, dur: float = 1.1, vel: float = 0.8, timbre: str = "bell") -> np.ndarray:
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    att = np.minimum(1.0, t / 0.003)

    def osc(k: float, decay: float) -> np.ndarray:
        return np.sin(TAU * k * f * t) * np.exp(-t * decay)

    if timbre == "marimba":  # woody: strong fundamental, inharmonic 4th partial, quick decay
        sig = osc(1, 6.5) + 0.35 * osc(3.93, 16) + 0.12 * osc(9.2, 40) + 0.3 * osc(0.5, 30)
    elif timbre == "pluck":  # harp-like: many harmonics, higher ones die first
        sig = sum(osc(k, 1.6 + 1.3 * k) * 0.85 ** k / k ** 0.5 for k in range(1, 11))
    elif timbre == "chip":  # soft 8-bit square (odd harmonics), short
        sig = sum(osc(k, 4.5) / k for k in (1, 3, 5, 7, 9)) * 0.75
    elif timbre == "glass":  # glass harmonica: slow attack, long ring, inharmonic shimmer
        att = np.minimum(1.0, t / 0.012)
        sig = osc(1, 1.8) + 0.4 * osc(2.76, 4) + 0.18 * osc(5.4, 8)
    else:  # bell
        sig = osc(1, 3.2) + 0.45 * osc(2, 6) + 0.18 * osc(3.01, 11) + 0.08 * osc(4.2, 18)
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


def _clack(rnd: random.Random, dur: float = 0.12) -> np.ndarray:
    """Short wooden knock for balls hitting each other."""
    t = np.arange(int(SR * dur)) / SR
    f = rnd.uniform(1100, 1400)
    sig = np.sin(TAU * f * t) * np.exp(-t * 55) + 0.5 * np.sin(TAU * 2.76 * f * t) * np.exp(-t * 80)
    return (sig * np.minimum(1.0, t / 0.001) * 0.22).astype(np.float32)


def soundtrack(sim, melody: str, duration: float, seed: int, timbre: str = "bell") -> np.ndarray:
    notes = MELODIES[melody][1]
    rnd = random.Random(seed)
    root = min(notes) - min(notes) % 12 + (notes[-1] % 12)  # key of the melody, lowest octave it uses
    penta = [root + 12 * (k // 5) + (0, 2, 4, 7, 9)[k % 5] for k in range(40)]
    cache: dict[tuple, np.ndarray] = {}

    def note(m: int, dur: float = 1.1, vel: float = 0.75) -> np.ndarray:
        if (m, dur, vel) not in cache:
            cache[m, dur, vel] = _note(m, dur, vel, timbre)
        return cache[m, dur, vel]
    mix = np.zeros(int(SR * (duration + 2)), dtype=np.float32)
    idx, last, last_clack = 0, -1.0, -1.0

    def put(t: float, sig: np.ndarray) -> None:
        i = int(t * SR)
        j = min(len(mix), i + len(sig))
        mix[i:j] += sig[: j - i]

    for t, kind, i in sim.events:
        if kind in ("bounce", "land"):
            if t - last < 0.045:  # very fast bounces: don't turn the melody into noise
                continue
            last = t
            put(t, note(notes[idx % len(notes)]))
            idx += 1
        elif kind == "tone":  # pendulum i: its own note of the scale, low (long) to high (short)
            put(t, note(penta[i] - 12, 0.9, 0.42))
        elif kind == "clack":
            if t - last_clack < 0.08 or t - last < 0.03:
                continue
            last_clack = t
            put(t, _clack(rnd))
        elif kind == "break":
            put(t, _sparkle(rnd, notes[idx % len(notes)] - 12))
        elif kind == "finale":
            base = notes[0] - 12
            for k, iv in enumerate([0, 4, 7, 12, 16, 19, 24]):
                put(t + 0.06 * k, note(base + iv, 2.4, 0.55))
            put(t, _sparkle(rnd, base + 12))
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

    def burst_path(self, rng: np.random.Generator, pts, color, count: int = 140) -> None:
        """Burst from points spread along a polyline, flying outwards from the centre."""
        P = np.array(pts, np.float32)
        seg = np.hypot(*(P[1:] - P[:-1]).T)
        i = rng.choice(len(seg), count, p=seg / seg.sum())
        p = P[i] + (P[i + 1] - P[i]) * rng.uniform(0, 1, (count, 1))
        out = p / (np.hypot(p[:, 0], p[:, 1])[:, None] + 1e-6) * rng.uniform(80, 420, (count, 1))
        self._add(p, out + rng.normal(0, 60, (count, 2)) - [0, 120], rng.uniform(0.8, 1.6, count), color)

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
    """Frame pipeline shared by all kinds: supersampled picture + quarter-size glow layer + text.

    Kinds draw through the helpers below; `base`/`base_glow` are persistent layers they may stamp onto."""

    def __init__(self, sim: Sim, credit: str, handle: str = "") -> None:
        self.sim = sim
        self.credit = credit
        self.handle = handle
        self.base = sim.look.background().resize((W * SS, H * SS))
        self.base_glow = Image.new("RGB", (W // 4, H // 4))
        self.base_d, self.base_g = ImageDraw.Draw(self.base), ImageDraw.Draw(self.base_glow)
        self.parts = Particles()
        self.rng = np.random.default_rng(12345)
        self.trails: dict[object, list[tuple[float, float, float]]] = {}
        self.seen = 0
        self.f_title = _font("Poppins-ExtraBold.ttf", 76)
        self.f_count = _font("Poppins-SemiBold.ttf", 46)
        self.f_small = _font("Poppins-SemiBold.ttf", 30)
        self.f_big = {s: _font("Poppins-ExtraBold.ttf", s) for s in range(40, 181, 10)}
        sim.prepare(self)

    def frame(self) -> Image.Image:
        sim = self.sim
        for _, kind, i in sim.events[self.seen:]:
            sim.on_event(self, kind, i)
        self.seen = len(sim.events)
        self.parts.update(1 / FPS)
        img = self.base.copy()
        self.d = ImageDraw.Draw(img)
        glow = self.base_glow.copy()
        self.g = ImageDraw.Draw(glow)
        sim.draw(self)
        img = img.resize((W, H), Image.BOX)
        glow = glow.filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
        img = ImageChops.screen(img, ImageChops.screen(glow, glow))
        d = ImageDraw.Draw(img)
        self.centered(d, H - 430, self.credit, self.f_small, (170, 170, 200))
        if self.handle:
            self.centered(d, H - 385, self.handle, self.f_small, (120, 120, 150))
        sim.draw_text(self, d)
        return img

    # drawing helpers (simulation coordinates: origin at the centre, 1 unit = 1 output pixel)
    def ring(self, r: float, start_deg: float, span_deg: float, col, width: float, flash: float = 0.0) -> None:
        s, q = SS, 0.25
        c = tuple(int(x + (255 - x) * flash) for x in col)
        self.d.arc(((CX - r) * s, (CY - r) * s, (CX + r) * s, (CY + r) * s), start_deg, start_deg + span_deg,
                   fill=c, width=int(width * s))
        self.g.arc(((CX - r) * q, (CY - r) * q, (CX + r) * q, (CY + r) * q), start_deg, start_deg + span_deg,
                   fill=col, width=max(2, int(width * q * 2.2)))

    def line(self, pts, col, width: float, flash: float = 0.0, glow=True, closed: bool = False, d=None, g=None) -> None:
        """Polyline; glow: True = same colour, a colour, or None for no glow."""
        pts = list(pts) + ([pts[0], pts[1]] if closed else [])
        c = tuple(int(x + (255 - x) * flash) for x in col)
        (d or self.d).line([((CX + x) * SS, (CY + y) * SS) for x, y in pts], fill=c, width=round(width * SS), joint="curve")
        if glow is not None:
            (g or self.g).line([((CX + x) / 4, (CY + y) / 4) for x, y in pts], fill=col if glow is True else glow,
                               width=max(2, int(width * 0.55)))

    def ball(self, x: float, y: float, r: float, fill, outline=None, width: float = 0, d=None) -> None:
        X, Y, rr = (CX + x) * SS, (CY + y) * SS, r * SS
        (d or self.d).ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=fill, outline=outline, width=int(width * SS))

    def glow_disc(self, x: float, y: float, r: float, col, g=None) -> None:
        X, Y, rr = (CX + x) / 4, (CY + y) / 4, r / 4
        (g or self.g).ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=col)

    def trail(self, key, x: float, y: float, r: float, col, n: int = 14) -> None:
        tr = self.trails.setdefault(key, [])
        tr.append((x, y, r))
        del tr[:-n]
        for j, (tx, ty, tr_r) in enumerate(tr[:-1]):
            k = (j + 1) / len(tr)
            self.ball(tx, ty, tr_r * (0.45 + 0.5 * k), _mix(col, 0.55 * k))

    def particles(self) -> None:
        self.parts.draw(self.d, SS)

    # text
    def centered(self, d, y: float, text: str, font, fill, stroke: int = 0) -> None:
        w = d.textlength(text, font=font)
        d.text((W / 2 - w / 2, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))

    def big_text(self, d, lines: list[tuple[str, tuple]], age: float) -> None:
        """Finale text popping up in the centre (lines are stacked; too wide ones shrink to fit)."""
        k = min(1.0, age / 0.25)
        size = int(round((60 + 120 * (1 - (1 - k) ** 3)) / 10) * 10)
        widest = max(d.textlength(t, font=self.f_big[180]) for t, _ in lines)
        size = max(40, min(size, 180, int(180 * (W - 90) / widest) // 10 * 10))
        font = self.f_big[size]
        for i, (text, fill) in enumerate(lines):
            w = d.textlength(text, font=font)
            y = CY - size * 0.7 + (i - (len(lines) - 1) / 2) * size * 1.08
            d.text((W / 2 - w / 2, y), text, font=font, fill=fill, stroke_width=6, stroke_fill=(0, 0, 0))


# ---------------------------------------------------------------- video


def render(kind: str, seed: int, out: Path, melody: str | None = None, handle: str = "",
           timbre: str | None = None, **params) -> dict:
    """Render one simulation to an MP4 (1080x1920, 60 fps) with its generated soundtrack."""
    out.parent.mkdir(parents=True, exist_ok=True)
    melody = melody or list(MELODIES)[seed % len(MELODIES)]
    probe = simulate(kind, seed, **params)
    if probe.end is None:
        raise RuntimeError(f"{kind} seed {seed} does not finish")
    duration = probe.end + OUTRO
    timbre = timbre or random.Random(f"tone-{kind}-{seed}").choice(TIMBRES)
    wav = out.with_suffix(".wav")
    _write_wav(wav, soundtrack(probe, melody, duration, seed, timbre))

    sim = KINDS[kind](seed, **params)
    painter = Painter(sim, sim.credit(MELODIES[melody][0]), handle)
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
            "melody_name": MELODIES[melody][0], "timbre": timbre, "title": " ".join(sim.title())}
