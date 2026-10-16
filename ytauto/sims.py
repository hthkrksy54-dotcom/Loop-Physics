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
  territory: pong wars – every ball paints the enemy squares it bounces off; most of the board wins
  chaos:     double pendulums start a hair apart and split into chaos (the butterfly effect)
  harmonograph: damped pendulums move a pen and draw a rosette
  race:      marble race down a long track of pegs, spinners, funnels and bumpers, the camera follows the leader

Finales of the escape-style kinds and the race are often replayed in slow motion.

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
SLOW = (0.9, 0.35, 0.33)  # slow motion: from 0.9 s before the finale moment to 0.35 s after it, at 1/3 speed

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
    note_gap = 0.045     # shortest gap between two melody notes (s)
    slowmo = False       # the finale moment is worth a slow-motion replay
    finale_punch = 1.0   # screen shake + flash at the finale (0 = none)
    # designed concepts (ytauto/concepts/) describe themselves; the built-in kinds use the tables in simchannel
    concept: dict = {}   # {"created": ISO time, "idea": ..., "inspiration": ..., "finale": ...}
    titles: list[str] | None = None
    questions: list[str] | None = None
    body: str | None = None
    playlist: tuple[str, str] | None = None
    cover_at: float | None = None
    trend_words: tuple[str, ...] = ()

    def __init__(self, seed: int) -> None:
        self.rnd = random.Random(seed)  # physics only
        self.look = Look(f"{self.kind}-{seed}")  # visuals only
        self.t = 0.0
        self.end: float | None = None
        self.events: list[tuple[float, str, int]] = []

    def finish(self) -> None:
        self.end = self.t
        self.events.append((self.t, "finale", 0))

    def good(self) -> bool:
        """Is this run worth a video (beyond its length)?"""
        return True

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
    """A ball bounces inside spinning rings with a gap and breaks out ring by ring."""
    kind = "escape"
    slowmo = True
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
    slowmo = True
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
    """A ball grows with every bounce until it fills the circle."""
    kind = "grow"
    slowmo = True

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
    finale_punch = 0.6

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
    finale_punch = 0.5

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
    finale_punch = 0.5
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


class Territory(Sim):
    """Pong wars: every ball flies freely through its own colour and bounces off enemy cells – painting
    them in its colour. Whoever owns most of the board when the time is up wins."""
    kind = "territory"
    note_gap = 0.11
    OVERTIME = 8.0  # the last seconds: the balls speed up
    PAIRS = [(0, 1), (5, 7), (4, 2), (6, 3)]

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        n = rnd.choice([2, 2, 3, 4])
        self.teams = list(rnd.choice(self.PAIRS)) if n == 2 else \
            list(rnd.choice([t for t in LINEUPS if len(t) == n]))
        self.G = G = rnd.choice([16, 18, 20, 24])
        self.S = 900.0
        self.c = self.S / G
        self.h = self.S / 2
        self.T = rnd.uniform(22, 56)
        self.owner = [[self._start_owner(r, c, n) for c in range(G)] for r in range(G)]
        self.rb = self.c * rnd.uniform(0.26, 0.32)
        self.speed = rnd.uniform(680, 820)
        per = rnd.choice([1, 1, 2]) if n == 2 else 1
        self.balls: list[Ball] = []
        for k in range(n * per):
            team = k % n
            cells = [(r, c) for r in range(1, G - 1) for c in range(1, G - 1) if self.owner[r][c] == team]
            r, c = rnd.choice(cells)
            a = rnd.uniform(0, TAU)
            x, y = -self.h + (c + 0.5) * self.c, -self.h + (r + 0.5) * self.c
            self.balls.append(Ball(x, y, math.cos(a) * self.speed, math.sin(a) * self.speed, self.rb,
                                   TEAMS[self.teams[team]][1], TEAMS[self.teams[team]][0]))
        self.team_of = [k % n for k in range(n * per)]
        self.flips: dict[tuple[int, int], float] = {}
        self.count = [sum(row.count(t) for row in self.owner) for t in range(n)]

    def _start_owner(self, r: int, c: int, n: int) -> int:
        G = self.G
        if n == 2:
            return int(c >= G / 2)
        if n == 4:
            return int(c >= G / 2) + 2 * int(r >= G / 2)
        a = (math.atan2(r + 0.5 - G / 2, c + 0.5 - G / 2) + math.pi / 2) % TAU
        return min(2, int(a / TAU * 3))

    def color(self, team: int) -> tuple[int, int, int]:
        return TEAMS[self.teams[team]][1]

    def cell_color(self, team: int) -> tuple[int, int, int]:
        return _mix(self.color(team), 0.58)

    def cell_box(self, r: int, c: int) -> tuple[float, float, float, float]:
        return -self.h + c * self.c, -self.h + r * self.c, -self.h + (c + 1) * self.c, -self.h + (r + 1) * self.c

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        h, cs, G = self.h, self.c, self.G
        speed = self.speed * (1 + 0.8 * max(0.0, (self.t - self.T + self.OVERTIME) / self.OVERTIME))  # final sprint
        for j, b in enumerate(self.balls):
            team = self.team_of[j]
            m = math.hypot(b.vx, b.vy)
            b.vx, b.vy = b.vx * speed / m, b.vy * speed / m
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.x - b.rb < -h or b.x + b.rb > h:
                b.x = max(-h + b.rb, min(h - b.rb, b.x))
                b.vx = -b.vx
            if b.y - b.rb < -h or b.y + b.rb > h:
                b.y = max(-h + b.rb, min(h - b.rb, b.y))
                b.vy = -b.vy
            c0, c1 = int((b.x - b.rb + h) // cs), int((b.x + b.rb + h) // cs)
            r0, r1 = int((b.y - b.rb + h) // cs), int((b.y + b.rb + h) // cs)
            hit = None
            for r in range(max(0, r0), min(G - 1, r1) + 1):
                for c in range(max(0, c0), min(G - 1, c1) + 1):
                    if self.owner[r][c] == team:
                        continue
                    x0, y0, x1, y1 = self.cell_box(r, c)
                    dx, dy = b.x - min(max(b.x, x0), x1), b.y - min(max(b.y, y0), y1)
                    if dx * dx + dy * dy >= b.rb * b.rb:
                        continue
                    self.count[self.owner[r][c]] -= 1
                    self.count[team] += 1
                    self.owner[r][c] = team
                    self.flips[r, c] = self.t
                    self.events.append((self.t, "paint", r * G + c))
                    if hit is None:
                        hit = (dx, dy)
            if hit is not None:
                dx, dy = hit
                if abs(dx) > abs(dy):
                    b.vx = math.copysign(abs(b.vx), dx)
                elif dy:
                    b.vy = math.copysign(abs(b.vy), dy)
                else:
                    b.vx, b.vy = -b.vx, -b.vy
                a = math.atan2(b.vy, b.vx) + self.rnd.gauss(0, 0.05)
                q = (a % (math.pi / 2)) / (math.pi / 2)  # keep away from the axes, or a ball runs in a rut
                if q < 0.12 or q > 0.88:
                    a += (0.12 - q if q < 0.5 else 0.88 - q) * math.pi / 2
                b.vx, b.vy = math.cos(a) * speed, math.sin(a) * speed
                self.events.append((self.t, "bounce", j))
        if self.t >= self.T:
            self.finish()

    def share(self) -> list[float]:
        return [k / (self.G * self.G) for k in self.count]

    def winner(self) -> int:
        return max(range(len(self.count)), key=lambda t: self.count[t])

    def prepare(self, p: Painter) -> None:
        for r in range(self.G):
            for c in range(self.G):
                self._cell(p, r, c, self.cell_color(self.owner[r][c]), p.base_d)
        h = self.h + 7
        p.line([(-h, -h), (h, -h), (h, h), (-h, h)], (210, 210, 235), 6, glow=None, closed=True, d=p.base_d)

    def _cell(self, p: Painter, r: int, c: int, col, d) -> None:
        x0, y0, x1, y1 = self.cell_box(r, c)
        g = 1.2
        d.rounded_rectangle(((CX + x0 + g) * SS, (CY + y0 + g) * SS, (CX + x1 - g) * SS, (CY + y1 - g) * SS),
                            radius=int(self.c * 0.18 * SS), fill=col)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "paint":
            r, c = divmod(i, self.G)
            self._cell(p, r, c, self.cell_color(self.owner[r][c]), p.base_d)
        elif kind == "finale":
            w = self.winner()
            for j, b in enumerate(self.balls):
                if self.team_of[j] == w:
                    p.parts.burst_point(p.rng, b.x, b.y, self.color(w), 200, 900)

    def draw(self, p: Painter) -> None:
        for (r, c), th in list(self.flips.items()):
            k = 1 - (self.t - th) / 0.3
            if k <= 0:
                del self.flips[r, c]
                continue
            base = self.cell_color(self.owner[r][c])
            self._cell(p, r, c, tuple(int(x + (255 - x) * 0.55 * k) for x in base), p.d)
            x0, y0, x1, y1 = self.cell_box(r, c)
            p.glow_disc((x0 + x1) / 2, (y0 + y1) / 2, self.c * 0.8, _mix(self.color(self.owner[r][c]), k))
        p.particles()
        for j, b in enumerate(self.balls):
            p.trail(j, b.x, b.y, b.rb, b.col, 8)
            p.ball(b.x, b.y, b.rb, b.col, (255, 255, 255), 3)
            p.glow_disc(b.x, b.y, b.rb * 1.8, b.col)

    def draw_text(self, p: Painter, d: ImageDraw.ImageDraw) -> None:
        for i, line in enumerate(self.title()):
            p.centered(d, 210 + i * 92, line, p.f_title, (255, 255, 255), 3)
        x0, x1, y0, y1 = 90, W - 90, 408, 466  # share bar
        x = x0
        for t, s in enumerate(self.share()):
            w = (x1 - x0) * s
            d.rectangle((x, y0, x + w, y1), fill=self.color(t))
            if w > 90:
                label = f"{round(100 * s)}%"
                tw = d.textlength(label, font=p.f_count)
                d.text((x + w / 2 - tw / 2, y0 + 1), label, font=p.f_count, fill=(255, 255, 255),
                       stroke_width=3, stroke_fill=(0, 0, 0))
            x += w
        d.rectangle((x0, y0, x1, y1), outline=(255, 255, 255), width=3)
        if self.end is None:
            left = max(0, math.ceil(self.T - self.t))
            if self.T - self.t < self.OVERTIME:
                pulse = 0.5 + 0.5 * math.cos(TAU * 2 * self.t)
                p.centered(d, 1422, f"FINAL SPRINT – {left} s", p.f_count, _mix((255, 70, 70), 0.6 + 0.4 * pulse), 2)
            else:
                p.centered(d, 1422, f"{left} s left", p.f_count, (255, 214, 120), 2)
        else:
            p.big_text(d, self.finale(), self.t - self.end)

    def title(self) -> list[str]:
        return ["Which color", "conquers the board?"]

    def finale(self) -> list[tuple[str, tuple]]:
        w = self.winner()
        return [(TEAMS[self.teams[w]][0], self.color(w)), ("WINS!", (255, 255, 255)),
                (f"{round(100 * self.share()[w])}%", self.color(w))]


class Chaos(Sim):
    """Double pendulums that start a hair apart: for a while they move as one, then the butterfly effect
    tears them apart. Each lower bob rings its own note when it swings through the middle."""
    kind = "chaos"
    counter_color = (255, 190, 130)

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.K = rnd.choice([3, 4, 5, 6, 7])
        self.delta = rnd.choice([0.01, 0.001, 0.001, 0.0001, 0.0001, 0.00001])  # degrees
        self.L1, self.L2 = 215.0, rnd.uniform(180, 225)
        self.m2 = rnd.uniform(0.6, 1.0)
        self.g = rnd.uniform(900, 1300)
        a1 = math.radians(rnd.uniform(110, 175)) * rnd.choice([-1, 1])
        a2 = a1 + math.radians(rnd.uniform(-60, 60))
        d = math.radians(self.delta)
        self.s = [[a1 + d * i, a2, 0.0, 0.0] for i in range(self.K)]
        self.oy = -20.0
        self.split: float | None = None
        self.hold = rnd.uniform(14, 26)
        self.side = [0] * self.K
        self.hit = [-9.0] * self.K
        self.spread = self.delta

    def _acc(self, t1: float, t2: float, w1: float, w2: float) -> tuple[float, float]:
        m1, m2, L1, L2, g = 1.0, self.m2, self.L1, self.L2, self.g
        d = t1 - t2
        den = 2 * m1 + m2 - m2 * math.cos(2 * d)
        a1 = (-g * (2 * m1 + m2) * math.sin(t1) - m2 * g * math.sin(t1 - 2 * t2)
              - 2 * math.sin(d) * m2 * (w2 * w2 * L2 + w1 * w1 * L1 * math.cos(d))) / (L1 * den)
        a2 = 2 * math.sin(d) * (w1 * w1 * L1 * (m1 + m2) + g * (m1 + m2) * math.cos(t1)
                                + w2 * w2 * L2 * m2 * math.cos(d)) / (L2 * den)
        return a1, a2

    def _rk4(self, s: list[float], h: float) -> None:
        t1, t2, w1, w2 = s
        a1, a2 = self._acc(t1, t2, w1, w2)
        b1, b2 = self._acc(t1 + w1 * h / 2, t2 + w2 * h / 2, w1 + a1 * h / 2, w2 + a2 * h / 2)
        c1, c2 = self._acc(t1 + (w1 + b1 * h / 2) * h / 2, t2 + (w2 + b2 * h / 2) * h / 2, w1 + b1 * h / 2, w2 + b2 * h / 2)
        e1, e2 = self._acc(t1 + (w1 + c1 * h / 2) * h, t2 + (w2 + c2 * h / 2) * h, w1 + c1 * h, w2 + c2 * h)
        s[0] = t1 + h * (w1 + h / 6 * (a1 + b1 + c1))
        s[1] = t2 + h * (w2 + h / 6 * (a2 + b2 + c2))
        s[2] = w1 + h / 6 * (a1 + 2 * b1 + 2 * c1 + e1)
        s[3] = w2 + h / 6 * (a2 + 2 * b2 + 2 * c2 + e2)

    def joints(self, i: int) -> tuple[float, float, float, float]:
        t1, t2 = self.s[i][0], self.s[i][1]
        x1, y1 = self.L1 * math.sin(t1), self.oy + self.L1 * math.cos(t1)
        return x1, y1, x1 + self.L2 * math.sin(t2), y1 + self.L2 * math.cos(t2)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        for i, s in enumerate(self.s):
            self._rk4(s, dt)
            x2 = self.joints(i)[2]
            side = 1 if x2 > 25 else -1 if x2 < -25 else 0
            if side and side != self.side[i]:
                if self.side[i]:
                    self.hit[i] = self.t
                    self.events.append((self.t, "tone", i))
                self.side[i] = side
        ref = self.s[0]
        self.spread = max(self.delta, max(abs(math.degrees(math.remainder(s[1] - ref[1], TAU))) for s in self.s))
        if self.split is None:
            x0, y0 = self.joints(0)[2:]
            if any(math.hypot(x - x0, y - y0) > 30 for x, y in (self.joints(i)[2:] for i in range(1, self.K))):
                self.split = self.t
                self.events.append((self.t, "break", 0))
        elif self.t >= self.split + self.hold:
            self.finish()

    def color(self, i: int) -> tuple[int, int, int]:
        return self.look.color(i / max(1, self.K - 1))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "finale":
            for j in range(self.K):
                x, y = self.joints(j)[2:]
                p.parts.burst_point(p.rng, x, y, self.color(j), 40, 600)

    def draw(self, p: Painter) -> None:
        if not hasattr(self, "_last"):
            self._last = [self.joints(i)[2:] for i in range(self.K)]
        for i in range(self.K):  # the bobs paint a faint permanent picture of the chaos
            x, y = self.joints(i)[2:]
            p.line([self._last[i], (x, y)], _mix(self.color(i), 0.42), 1.3, glow=None, d=p.base_d)
            self._last[i] = (x, y)
        p.particles()
        for i in reversed(range(self.K)):  # pendulum 0 on top: before the split you only see one
            x1, y1, x2, y2 = self.joints(i)
            col = self.color(i)
            p.trail(i, x2, y2, 7, col, 26)
            p.line([(0, self.oy), (x1, y1), (x2, y2)], _mix(col, 0.85, (255, 255, 255)), 5, glow=_mix(col, 0.5))
            p.ball(x1, y1, 10, col, (255, 255, 255), 2)
            k = max(0.0, 1 - (self.t - self.hit[i]) / 0.25)
            p.ball(x2, y2, 17 + 5 * k, col, (255, 255, 255), 3)
            p.glow_disc(x2, y2, 30 + 20 * k, col)
        p.ball(0, self.oy, 9, (230, 230, 240))

    def title(self) -> list[str]:
        return [f"{self.K} pendulums,", f"{_decimal(self.delta)}° apart"]

    def counter(self) -> str:
        return f"difference: {_decimal(self.spread)}°"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("BUTTERFLY", self.color(0)), ("EFFECT!", (255, 255, 255))]

    def credit(self, melody_name: str) -> str:
        return "Every pendulum plays its own note"


def _decimal(x: float) -> str:
    """0.00001 -> '0.00001', 0.0123 -> '0.012', 37.4 -> '37' (no scientific notation on screen)."""
    if x >= 10:
        return f"{x:.0f}"
    digits = max(1, 1 - math.floor(math.log10(x)))
    return f"{x:.{digits}f}".rstrip("0").rstrip(".") if x < 1 else f"{x:.1f}"


class Harmonograph(Sim):
    """A harmonograph: two damped pendulums move the pen in x, two in y – slightly detuned, so the figure
    slowly turns while it shrinks into a rosette."""
    kind = "harmonograph"
    finale_punch = 0.4
    RATIOS = [(1, 2), (2, 3), (3, 4), (2, 1), (3, 2), (1, 3), (3, 5), (4, 5)]

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        p, q = rnd.choice(self.RATIOS)
        base = rnd.uniform(0.55, 0.85) / max(p, q) * 2
        self.T = rnd.uniform(22, 56)
        det = rnd.uniform(0.006, 0.02) * rnd.choice([-1, 1])
        self.f = [base * p, base * q * (1 + det), base * p * (1 - det / 2), base * q]
        px, qx = rnd.uniform(0, TAU), rnd.uniform(0, TAU)  # y a quarter turn behind x: round figures, not lines
        self.ph = [px, qx, px + rnd.choice([-1, 1]) * (math.pi / 2 + rnd.uniform(-0.45, 0.45)),
                   qx + rnd.choice([-1, 1]) * (math.pi / 2 + rnd.uniform(-0.45, 0.45))]
        split = rnd.uniform(0.35, 0.65)
        R = 430
        self.A = [R * split, R * (1 - split), R * (1 - split), R * split]
        self.damp = math.log(rnd.uniform(5, 9)) / self.T
        self.pts = [self.pos(0.0)]
        self.dy = 0.0
        self.drawn = 0
        self.last_hit = -9.0

    def pos(self, t: float) -> tuple[float, float]:
        e = math.exp(-self.damp * t)
        f, ph, A = self.f, self.ph, self.A
        x = (A[0] * math.sin(TAU * f[0] * t + ph[0]) + A[1] * math.sin(TAU * f[1] * t + ph[1])) * e
        y = (A[2] * math.sin(TAU * f[2] * t + ph[2]) + A[3] * math.sin(TAU * f[3] * t + ph[3])) * e
        return x, y

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        x, y = self.pos(self.t)
        dy = y - self.pts[-1][1]
        if dy > 0 >= self.dy:  # the pen turns at the top of a swing: next note
            self.events.append((self.t, "bounce", len(self.pts)))
            self.last_hit = self.t
        self.dy = dy
        self.pts.append((x, y))
        if self.t >= self.T:
            self.finish()

    def color(self, u: float) -> tuple[int, int, int]:
        return self.look.color(u)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "finale":
            x, y = self.pts[-1]
            p.parts.burst_point(p.rng, x, y, self.color(1.0), 220, 900)

    def draw(self, p: Painter) -> None:
        new = self.pts[max(0, self.drawn - 1):]
        if len(new) > 1:
            col = self.color(min(1.0, self.t / self.T))
            p.line(new, col, 1.7, glow=_mix(col, 0.25), d=p.base_d, g=p.base_g)
        self.drawn = len(self.pts)
        p.particles()
        if self.end is None:
            x, y = self.pts[-1]
            col = self.color(min(1.0, self.t / self.T))
            k = max(0.0, 1 - (self.t - self.last_hit) / 0.2)
            p.ball(x, y, 9 + 3 * k, (255, 255, 255), col, 3)
            p.glow_disc(x, y, 30 + 14 * k, col)

    def title(self) -> list[str]:
        return ["What will this", "pendulum draw?"]

    def counter(self) -> str:
        return f"{min(100, int(100 * self.t / self.T))}% drawn"

    def finale_text(self) -> str:
        return "MASTERPIECE!"


class Race(Sim):
    """Marble race down a long track of pegs, zigzag ramps, spinners, funnels and bumpers. The camera
    follows the leader; the first ball over the finish line wins."""
    kind = "race"
    note_gap = 0.09
    slowmo = True
    HW = 450.0  # half width of the track
    BUCKET = 100.0

    def __init__(self, seed: int, length: float | None = None):
        super().__init__(seed)
        rnd = self.rnd
        n = rnd.choice([4, 5, 6, 6, 8])
        teams = rnd.sample(range(len(TEAMS)), n)
        self.rb = rnd.uniform(14, 17)
        span = self.HW * 0.75
        self.balls = [Ball(-span + 2 * span * i / (n - 1) + rnd.uniform(-6, 6), -40 + rnd.uniform(-8, 8),
                           rnd.gauss(0, 40), 0.0, self.rb, TEAMS[c][1], TEAMS[c][0]) for i, c in enumerate(teams)]
        self.pegs: list[tuple[float, float, float, float]] = []   # x, y, r, restitution (> 1: bumper)
        self.segs: list[tuple[float, float, float, float]] = []   # x1, y1, x2, y2
        self.spin: list[tuple[float, float, float, float, float]] = []  # cx, cy, half length, omega, phase
        self.sections: list[tuple[float, float]] = []
        builders = [self._pegs, self._zigzag, self._spinners, self._funnel, self._bumpers]
        y, last, target = 160.0, None, length or rnd.uniform(6000, 13000)
        while y < target:
            build = rnd.choice([b for b in builders if b is not last])
            y0, y = y, build(y, rnd) + 110
            self.sections.append((y0, y))
            last = build
        self.finish_y = y + 60
        self.segs.append((-self.HW, self.finish_y + 260, self.HW, self.finish_y + 260))  # catch basin
        self.g = 1350.0
        self.cam, self.zoom = 300.0, 1.0
        self.lead, self.changes, self.photo = -1, 0, 1e9
        self.order: list[int] = []
        self.hit: dict[tuple[str, int], float] = {}
        self.watch = [(0.0, b.x, b.y) for b in self.balls]
        self.trails: list[list[tuple[float, float]]] = [[] for _ in self.balls]
        self.buckets: dict[int, list[tuple[str, int]]] = {}
        for i, (x, y_, r, _) in enumerate(self.pegs):
            self._register("p", i, y_ - r, y_ + r)
        for i, (x1, y1, x2, y2) in enumerate(self.segs):
            self._register("s", i, min(y1, y2), max(y1, y2))
        for i, (cx, cy, hl, _, _) in enumerate(self.spin):
            self._register("w", i, cy - hl, cy + hl)

    def _register(self, kind: str, i: int, y0: float, y1: float) -> None:
        for k in range(int((y0 - 40) // self.BUCKET), int((y1 + 40) // self.BUCKET) + 1):
            self.buckets.setdefault(k, []).append((kind, i))

    # track sections: each takes the top y and returns the bottom y
    def _pegs(self, y: float, rnd: random.Random) -> float:
        sx, dy = rnd.choice([(80, 62), (90, 66), (100, 70)])
        rows = rnd.randint(7, 11)
        for r in range(rows):
            off = sx / 2 if r % 2 else 0
            x = -self.HW + 45 + off
            while x < self.HW - 40:
                self.pegs.append((x, y + r * dy, 7.0, 0.55))
                x += sx
        return y + rows * dy

    def _zigzag(self, y: float, rnd: random.Random) -> float:
        k, drop, gap = rnd.randint(3, 5), rnd.uniform(110, 150), rnd.uniform(110, 140)
        side = rnd.choice([-1, 1])
        for i in range(k):
            yy = y + i * (drop + 70)
            self.segs.append((-side * self.HW, yy, side * (self.HW - gap), yy + drop))
            side = -side
        return y + k * (drop + 70)

    def _spinners(self, y: float, rnd: random.Random) -> float:
        rows, w = rnd.randint(2, 3), rnd.uniform(1.3, 2.4) * rnd.choice([-1, 1])
        for i in range(rows):
            yy = y + 170 + i * 300
            for j, cx in enumerate((-self.HW / 2, self.HW / 2)):
                self.spin.append((cx, yy, 165.0, w * (-1 if (i + j) % 2 else 1), rnd.uniform(0, math.pi)))
            self.pegs.append((0.0, yy + 150, 9.0, 0.6))
        return y + 170 + rows * 300

    def _funnel(self, y: float, rnd: random.Random) -> float:
        gap, depth = rnd.uniform(3.4, 4.2) * self.rb * 2, rnd.uniform(240, 300)
        self.segs.append((-self.HW, y, -gap / 2, y + depth))
        self.segs.append((self.HW, y, gap / 2, y + depth))
        self.pegs.append((rnd.uniform(-20, 20), y + depth + 120, 26.0, 1.05))  # splits the stream again
        return y + depth + 170

    def _bumpers(self, y: float, rnd: random.Random) -> float:
        rows = rnd.randint(3, 4)
        for i in range(rows):
            xs = (-self.HW / 2, self.HW / 2) if i % 2 == 0 else (-self.HW * 0.78, 0.0, self.HW * 0.78)
            for x in xs:
                self.pegs.append((x + rnd.uniform(-25, 25), y + 80 + i * 170, rnd.uniform(34, 46), 1.05))
        return y + 80 + rows * 170

    def spinner(self, i: int) -> tuple[float, float, float, float]:
        cx, cy, hl, w, ph = self.spin[i]
        a = ph + w * self.t
        return cx - hl * math.cos(a), cy - hl * math.sin(a), cx + hl * math.cos(a), cy + hl * math.sin(a)

    def good(self) -> bool:
        """Only races with a close finish and a few changes in the lead make it into a video."""
        return self.photo < 320 and self.changes >= 4

    def leader(self) -> int:
        if self.order:
            return self.order[0]
        return max(range(len(self.balls)), key=lambda j: self.balls[j].y)

    def _contact(self, j: int, b: Ball, key: tuple[str, int], nx: float, ny: float, vn: float) -> None:
        self.hit[key] = self.t
        if self.end is None and j == self.leader() and vn < -140:
            self.events.append((self.t, "bounce", j))

    def step(self, dt: float) -> None:
        self.t += dt
        HW = self.HW
        for j, b in enumerate(self.balls):
            b.move(dt, self.g)
            if abs(b.x) > HW - b.rb:
                b.x = math.copysign(HW - b.rb, b.x)
                b.vx = -b.vx * 0.6
            k = int(b.y // self.BUCKET)
            for kind, i in self.buckets.get(k, ()):
                if kind == "p":
                    x, y, r, e = self.pegs[i]
                    dx, dy, md = b.x - x, b.y - y, r + b.rb
                    if abs(dx) >= md or abs(dy) >= md:
                        continue
                    d = math.hypot(dx, dy)
                    if d >= md:
                        continue
                    nx, ny = (dx / d, dy / d) if d else (0.0, -1.0)
                    b.x, b.y = x + nx * md, y + ny * md
                    vn = b.vx * nx + b.vy * ny
                    if vn < 0:
                        b.vx, b.vy = b.vx - (1 + e) * vn * nx, b.vy - (1 + e) * vn * ny
                        if e > 1:  # bumper: always kick hard
                            out = b.vx * nx + b.vy * ny
                            if out < 520:
                                b.vx, b.vy = b.vx + (520 - out) * nx, b.vy + (520 - out) * ny
                        self._contact(j, b, ("p", i), nx, ny, vn)
                else:
                    if kind == "s":
                        x1, y1, x2, y2 = self.segs[i]
                        w, cx, cy, e = 0.0, 0.0, 0.0, 0.35
                    else:
                        x1, y1, x2, y2 = self.spinner(i)
                        cx, cy, _, w, _ = self.spin[i]
                        e = 0.6
                    ex, ey = x2 - x1, y2 - y1
                    u = max(0.0, min(1.0, ((b.x - x1) * ex + (b.y - y1) * ey) / (ex * ex + ey * ey)))
                    qx, qy = x1 + u * ex, y1 + u * ey
                    dx, dy, md = b.x - qx, b.y - qy, b.rb + 4
                    if abs(dx) >= md or abs(dy) >= md:
                        continue
                    d = math.hypot(dx, dy)
                    if d >= md:
                        continue
                    nx, ny = (dx / d, dy / d) if d else (0.0, -1.0)
                    b.x, b.y = qx + nx * md, qy + ny * md
                    wx, wy = -w * (qy - cy), w * (qx - cx)  # the bar's own velocity at the contact point
                    vn = (b.vx - wx) * nx + (b.vy - wy) * ny
                    if vn < 0:
                        b.vx, b.vy = b.vx - (1 + e) * vn * nx, b.vy - (1 + e) * vn * ny
                        self._contact(j, b, (kind, i), nx, ny, vn)
            if j not in self.order and b.y >= self.finish_y:
                self.order.append(j)
                if self.end is None:
                    self.photo = self.finish_y - max(o.y for o in self.balls if o is not b)
                    self.finish()
            t0, x0, y0 = self.watch[j]  # a ball resting somewhere gets a little shake
            if self.t - t0 > 2.0:
                if math.hypot(b.x - x0, b.y - y0) < 12 and b.y < self.finish_y:
                    b.vx, b.vy = b.vx + self.rnd.gauss(0, 220), b.vy - 380
                self.watch[j] = (self.t, b.x, b.y)
        Escape._collide(self)
        lead = self.leader()
        if lead != self.lead and self.t > 3 and self.end is None:
            self.changes += 1
        self.lead = lead
        ys = sorted((b.y for b in self.balls), reverse=True)
        gap = min(1300.0, ys[0] - ys[1]) if self.end is None else 0.0
        zoom = max(0.55, min(1.0, 900 / (gap + 420)))  # zoom out so the chaser stays in the picture
        self.zoom += (zoom - self.zoom) * min(1.0, 2.0 * dt)
        target = max(300.0, min(ys[0] - gap / 2 + 120 / self.zoom, self.finish_y + 160))
        self.cam += (target - self.cam) * min(1.0, 3.5 * dt)

    def color(self, k: int) -> tuple[int, int, int]:
        return self.look.color(k / max(1, len(self.sections) - 1), s=0.55, v=0.95)

    def section_of(self, y: float) -> int:
        for k, (y0, y1) in enumerate(self.sections):
            if y < y1:
                return k
        return len(self.sections) - 1

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "finale":
            b = self.balls[self.order[0]]
            p.parts.burst_point(p.rng, b.x * self.zoom, (b.y - self.cam) * self.zoom, b.col, 240, 950)

    def draw(self, p: Painter) -> None:
        cam, z, HW = self.cam, self.zoom, self.HW

        def at(x: float, y: float) -> tuple[float, float]:  # world -> screen (camera and zoom)
            return x * z, (y - cam) * z
        top, bottom = cam - 560 / z, cam + 560 / z
        wall = (150, 150, 185)
        y0, y1 = max(-200, top), min(self.finish_y + 260, bottom)
        for side in (-1, 1):
            p.line([at(side * (HW + 5), y0), at(side * (HW + 5), y1)], wall, max(2, 6 * z), glow=None)
        for m in range(int(top // 400) + 1, int(bottom // 400) + 1):  # distance marks scroll past
            if 0 < m * 400 < self.finish_y:
                for side in (-1, 1):
                    p.line([at(side * HW, m * 400), at(side * (HW - 22), m * 400)], (95, 95, 125), max(2, 3 * z), glow=None)
        if top < self.finish_y + 40 and bottom > self.finish_y - 40:  # chequered finish line
            sq = 30
            for r in range(2):
                for c in range(int(2 * HW // sq)):
                    col = (240, 240, 240) if (r + c) % 2 else (25, 25, 30)
                    xa, ya = at(-HW + c * sq, self.finish_y - sq + r * sq)
                    p.d.rectangle(((CX + xa) * SS, (CY + ya) * SS, (CX + xa + sq * z) * SS, (CY + ya + sq * z) * SS),
                                  fill=col)
        seen: set = set()
        for k in range(int(top // self.BUCKET), int(bottom // self.BUCKET) + 1):
            for key in self.buckets.get(k, ()):
                if key in seen:
                    continue
                seen.add(key)
                kind, i = key
                flash = max(0.0, 1 - (self.t - self.hit.get(key, -9)) / 0.2)
                if kind == "p":
                    x, y, r, e = self.pegs[i]
                    col = self.color(self.section_of(y))
                    if e > 1:
                        p.ball(*at(x, y), r * z, _mix(col, 0.25 + 0.5 * flash), col, max(1.5, 5 * z))
                        p.glow_disc(*at(x, y), r * 1.3 * z, _mix(col, 0.3 + 0.7 * flash))
                    else:
                        p.ball(*at(x, y), (r + 2 * flash) * z, _mix(col, 0.75 + 0.25 * flash, (255, 255, 255)))
                        if flash:
                            p.glow_disc(*at(x, y), r * 3 * z, _mix(col, flash))
                else:
                    x1, y1, x2, y2 = self.segs[i] if kind == "s" else self.spinner(i)
                    col = self.color(self.section_of((y1 + y2) / 2))
                    p.line([at(x1, y1), at(x2, y2)], col, max(2, (9 if kind == "s" else 11) * z), flash * 0.7)
                    if kind == "w":
                        p.ball(*at(*self.spin[i][:2]), 11 * z, (235, 235, 245), col, max(1, 3 * z))
        p.particles()
        for j, b in enumerate(self.balls):
            tr = self.trails[j]
            tr.append((b.x, b.y))
            del tr[:-12]
            for q, (tx, ty) in enumerate(tr[:-1]):
                k = (q + 1) / len(tr)
                p.ball(*at(tx, ty), b.rb * z * (0.4 + 0.5 * k), _mix(b.col, 0.5 * k))
        lead = self.leader()
        for j in sorted(range(len(self.balls)), key=lambda j: j == lead):
            b = self.balls[j]
            p.ball(*at(b.x, b.y), b.rb * z, b.col, (255, 255, 255), max(1.5, 3 * z))
            p.glow_disc(*at(b.x, b.y), b.rb * 1.7 * z + (8 if j == lead else 0), b.col)
        p.clip(-470, 500)

    def draw_text(self, p: Painter, d: ImageDraw.ImageDraw) -> None:
        super().draw_text(p, d)
        x, y0, y1 = W - 42, 560, 1400  # progress bar: where every ball is on the track
        d.line((x, y0, x, y1), fill=(110, 110, 140), width=6)
        for yy in (y0, y1):
            d.line((x - 14, yy, x + 14, yy), fill=(200, 200, 220), width=4)
        lead = self.leader()
        for j in sorted(range(len(self.balls)), key=lambda j: j == lead):
            b = self.balls[j]
            yy = y0 + (y1 - y0) * min(1.0, max(0.0, b.y / self.finish_y))
            r = 15 if j == lead else 10
            d.ellipse((x - r, yy - r, x + r, yy + r), fill=b.col, outline=(255, 255, 255), width=3 if j == lead else 2)

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return self.balls[self.leader()].col

    def title(self) -> list[str]:
        return ["Which color", "wins the race?"]

    def counter(self) -> str:
        return f"{self.balls[self.leader()].name} {'leads' if self.end is None else 'first!'}"

    def finale(self) -> list[tuple[str, tuple]]:
        b = self.balls[self.order[0]]
        return [(b.name, b.col), ("WINS!", (255, 255, 255))]


KINDS = {k.kind: k for k in (Escape, Grow, Battle, Polygon, Plinko, StringArt, Multiply, Pendulum, Territory, Chaos,
                             Harmonograph, Race)}


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
        if sim.end is not None and lo <= sim.end <= hi and sim.good():
            return seed
    raise RuntimeError(f"no {kind} seed with a {lo}-{hi}s run near {start}")


class Warp:
    """Simulation time -> video time, optionally with a slow-motion stretch around the finale moment."""

    def __init__(self, end: float | None = None) -> None:
        self.a = self.b = None
        if end is not None:
            self.a, self.b, self.rate = max(0.0, end - SLOW[0]), end + SLOW[1], SLOW[2]

    def video(self, t: float) -> float:
        if self.a is None or t <= self.a:
            return t
        if t <= self.b:
            return self.a + (t - self.a) / self.rate
        return self.a + (self.b - self.a) / self.rate + (t - self.b)

    def sim(self, v: float) -> float:
        if self.a is None or v <= self.a:
            return v
        vb = self.video(self.b)
        return self.a + (v - self.a) * self.rate if v <= vb else self.b + (v - vb)


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


def _swoosh(rnd: random.Random, dur: float = 1.0) -> np.ndarray:
    """Falling whoosh that marks the start of a slow motion."""
    t = np.arange(int(SR * dur)) / SR
    f = 520 * np.exp(-t * 2.2) + 60
    sweep = np.sin(TAU * np.cumsum(f) / SR) * 0.35
    noise = np.random.default_rng(rnd.randrange(1 << 30)).standard_normal(len(t))
    k = 24
    air = np.convolve(noise, np.ones(k) / k, mode="same") * 1.2
    env = np.minimum(1.0, t / 0.18) * np.exp(-np.maximum(0, t - 0.18) * 3.2)
    return ((sweep + air) * env * 0.5).astype(np.float32)


def soundtrack(sim, melody: str, duration: float, seed: int, timbre: str = "bell", warp: Warp | None = None) -> np.ndarray:
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

    warp = warp or Warp()
    if warp.a is not None:
        mix_at = int(warp.a * SR)
        sw = _swoosh(rnd)
        mix[mix_at:mix_at + len(sw)] += sw[: len(mix) - mix_at]

    def put(t: float, sig: np.ndarray) -> None:
        i = int(warp.video(t) * SR)
        j = min(len(mix), i + len(sig))
        mix[i:j] += sig[: j - i]

    for t, kind, i in sim.events:
        if kind in ("bounce", "land"):
            if t - last < sim.note_gap:  # very fast bounces: don't turn the melody into noise
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
        self._masks: dict[tuple, Image.Image] = {}
        self.kicks: list[tuple[float, float]] = []
        self._shake_rng = np.random.default_rng(777)
        self._white = Image.new("RGB", (W, H), (255, 255, 255))
        self.f_title = _font("Poppins-ExtraBold.ttf", 76)
        self.f_count = _font("Poppins-SemiBold.ttf", 46)
        self.f_small = _font("Poppins-SemiBold.ttf", 30)
        self.f_big = {s: _font("Poppins-ExtraBold.ttf", s) for s in range(40, 181, 10)}
        sim.prepare(self)

    def frame(self, dt: float = 1 / FPS) -> Image.Image:
        """The picture after the simulation moved on by dt seconds (less than a frame in slow motion)."""
        sim = self.sim
        for _, kind, i in sim.events[self.seen:]:
            if kind == "finale" and sim.finale_punch:
                self.punch(sim.finale_punch)
            sim.on_event(self, kind, i)
        self.seen = len(sim.events)
        self.parts.update(dt)
        self.img = img = self.base.copy()
        self.d = ImageDraw.Draw(img)
        self.glow = glow = self.base_glow.copy()
        self.g = ImageDraw.Draw(glow)
        sim.draw(self)
        img = img.resize((W, H), Image.BOX)
        glow = glow.filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
        img = self._shake(ImageChops.screen(img, ImageChops.screen(glow, glow)))
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

    def punch(self, strength: float = 1.0) -> None:
        """Escalation effect: a short screen shake and white flash (1 = the standard finale; stacks)."""
        self.kicks.append((self.sim.t, strength))

    def _shake(self, img: Image.Image) -> Image.Image:
        t = self.sim.t
        self.kicks = [(t0, s) for t0, s in self.kicks if t - t0 < 0.7]
        amp = sum(s * max(0.0, 1 - (t - t0) / 0.6) for t0, s in self.kicks)
        if amp < 0.03:
            return img
        dx, dy = (int(v) for v in self._shake_rng.normal(0, 10 * min(amp, 2.5), 2))
        img = ImageChops.offset(img, dx, dy)
        flash = min(0.5, 0.35 * sum(s * max(0.0, 1 - (t - t0) / 0.18) for t0, s in self.kicks))
        return Image.blend(img, self._white, flash) if flash > 0.01 else img

    def clip(self, y0: float, y1: float, fade: float = 110) -> None:
        """Fade out everything drawn above y0 and below y1 so a scrolling scene stays clear of the text."""
        for img, base, s in ((self.img, self.base, SS), (self.glow, self.base_glow, 0.25)):
            w, h = img.size
            for top, bottom, up in ((0, (CY + y0) * s, True), ((CY + y1) * s, h, False)):
                top, bottom = int(top), int(bottom)
                key = (w, top, bottom, up, fade * s)
                if key not in self._masks:
                    n, f = bottom - top, max(1, int(fade * s))
                    ramp = np.clip(((np.arange(n) if up else n - 1 - np.arange(n)) - (n - f)) / f, 0, 1)
                    col = (255 * (1 - ramp)).astype(np.uint8)
                    self._masks[key] = Image.fromarray(np.repeat(col[:, None], w, 1))
                img.paste(base.crop((0, top, w, bottom)), (0, top), self._masks[key])

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
    slow = probe.slowmo and (getattr(probe, "photo", 1e9) < 150 or random.Random(f"slow-{kind}-{seed}").random() < 0.75)
    warp = Warp(probe.end if slow else None)
    duration = warp.video(probe.end) + OUTRO
    timbre = timbre or random.Random(f"tone-{kind}-{seed}").choice(TIMBRES)
    wav = out.with_suffix(".wav")
    _write_wav(wav, soundtrack(probe, melody, duration, seed, timbre, warp))

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
    dt, shown = 1 / (FPS * SUBSTEPS), 0.0
    for f in range(frames):
        target = warp.sim((f + 1) / FPS)
        while sim.t < target - dt / 2:
            sim.step(dt)
        proc.stdin.write(painter.frame(target - shown).tobytes())
        shown = target
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    wav.unlink(missing_ok=True)
    return {"video": out, "duration": duration, "kind": kind, "seed": seed, "melody": melody,
            "melody_name": MELODIES[melody][0], "timbre": timbre, "title": " ".join(sim.title()), "slowmo": slow}


# ---------------------------------------------------------------- designed concepts

from . import concepts as _concepts  # noqa: E402  (each concept module builds on the classes above)

KINDS.update({k: v for k, v in _concepts.discover().items() if k not in KINDS})
