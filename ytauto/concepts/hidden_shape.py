"""Hidden shape: invisible shapes push up a stretchy sheet of 1,600 spheres from below, one bump at a time – can
you guess each one before its name appears? The last one is so big it rips the sheet and shows itself.

3D (ytauto/sim3d.py): the sheet is pinned at its border flat on the platform and coloured by height, so every
shape reads like a relief map. The shapes are fixed spheres that rise out of the platform one after another (each
bump that appears plays the next note), hold, and sink again (the sheet slaps back down: a clack). Every round is
quicker than the one before. The finale shape keeps rising until the sheet tears and it bursts through.
"""
from __future__ import annotations

import math

import numpy as np

from .. import sim3d
from ..sims import H, Sim

N, SIZE = 40, 2.2          # 40×40 spheres on a 2.2 m sheet
FLOOR = -0.6               # platform top (m)
PHYS = 6                   # physics every 6th step(): 120 Hz
RISE = 0.3                 # s for one sphere to rise to its height
PUMPKIN, STEM = (255, 132, 24), (90, 200, 70)


def _arc(n, rad, a0, a1, h, r, cx=0.0, cz=0.0):
    return [(cx + rad * math.cos(a0 + (a1 - a0) * i / max(1, n - 1)),
             cz + rad * math.sin(a0 + (a1 - a0) * i / max(1, n - 1)), h, r) for i in range(n)]


def _line(p0, p1, n, h, r):
    return [(p0[0] + (p1[0] - p0[0]) * i / (n - 1), p0[1] + (p1[1] - p0[1]) * i / (n - 1), h, r) for i in range(n)]


def _heart():
    pts = []
    for i in range(16):
        t = 2 * math.pi * i / 16
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * 0.036, -z * 0.036 - 0.05, 0.2, 0.09))
    return pts + [(-0.18, -0.12, 0.26, 0.17), (0.18, -0.12, 0.26, 0.17), (0.0, 0.12, 0.24, 0.16)]


def _star():
    pts = [(0.0, 0.0, 0.34, 0.16)]
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        pts += [(math.cos(a) * d, math.sin(a) * d, 0.3 - 0.4 * d, 0.13 - 0.08 * d) for d in (0.2, 0.36, 0.5)]
    return pts


def _pyramid():
    pts = []
    for lvl, (n, h, r) in enumerate(((4, 0.16, 0.13), (3, 0.3, 0.13), (2, 0.44, 0.13), (1, 0.58, 0.14))):
        off = (n - 1) / 2 * 0.2
        pts += [(-off + 0.2 * i, -off + 0.2 * j, h, r) for i in range(n) for j in range(n)
                if lvl == 3 or i in (0, n - 1) or j in (0, n - 1)]
    return pts


def _smiley():
    return ([(-0.24, -0.2, 0.3, 0.1), (0.24, -0.2, 0.3, 0.1)] + _arc(9, 0.36, 0.35, math.pi - 0.35, 0.18, 0.075)
            + _arc(14, 0.66, -math.pi / 2, 3 * math.pi / 2 - 0.45, 0.14, 0.07))


def _spiral():
    return [(math.cos(1.0 * i) * (0.08 + 0.042 * i), math.sin(1.0 * i) * (0.08 + 0.042 * i), 0.14 + 0.026 * i, 0.09)
            for i in range(15)]


def _stairs():
    return [(-0.5 + 0.2 * i, z, 0.08 + 0.08 * i, 0.12) for i in range(6) for z in (-0.18, 0.18)]


def _snowman():
    return [(0.0, 0.3, 0.3, 0.3), (0.0, -0.18, 0.42, 0.2), (-0.07, -0.25, 0.5, 0.04), (0.07, -0.25, 0.5, 0.04),
            (0.0, -0.42, 0.44, 0.06)] + _line((-0.5, 0.1), (-0.3, 0.25), 3, 0.14, 0.04) \
        + _line((0.5, 0.1), (0.3, 0.25), 3, 0.14, 0.04)


def _cat():
    return [(0.0, 0.05, 0.34, 0.34), (-0.25, -0.33, 0.42, 0.1), (0.25, -0.33, 0.42, 0.1),
            (-0.26, -0.24, 0.38, 0.12), (0.26, -0.24, 0.38, 0.12)] \
        + _line((-0.62, 0.0), (-0.3, 0.06), 3, 0.1, 0.03) + _line((0.62, 0.0), (0.3, 0.06), 3, 0.1, 0.03)


SHAPES = [
    ("A RING", lambda: _arc(12, 0.45, 0, 2 * math.pi * 11 / 12, 0.2, 0.11)),
    ("A SMILEY", _smiley),
    ("A HEART", _heart),
    ("A STAR", _star),
    ("A PYRAMID", _pyramid),
    ("A SNAKE", lambda: [(-0.62 + 0.09 * i, 0.25 * math.sin(i * 0.6), 0.16 + (0.06 if i == 14 else 0), 0.09)
                         for i in range(15)]),
    ("A SPIRAL", _spiral),
    ("STAIRS", _stairs),
    ("A SNOWMAN", _snowman),
    ("THE LETTER X", lambda: _line((-0.5, -0.5), (0.5, 0.5), 9, 0.2, 0.1) + _line((-0.5, 0.5), (0.5, -0.5), 9, 0.2, 0.1)),
    ("A CAT", _cat),
    ("A SQUARE", lambda: [(x, z, 0.2, 0.1) for x in (-0.45, -0.15, 0.15, 0.45) for z in (-0.45, -0.15, 0.15, 0.45)
                          if abs(x) > 0.3 or abs(z) > 0.3]),
]


def _pumpkin():
    pts = [(0.0, 0.0, 0.46, 0.4)]
    pts += [(0.27 * math.cos(a), 0.27 * math.sin(a), 0.38, 0.24) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
    return pts


def _plan(seed: int):
    """Shape order and timing – fixed per seed, so the run length is known before simulating."""
    order = list(range(len(SHAPES)))
    k = seed % len(order)
    order = order[k:] + order[:k]
    pace = 1.0 + 0.07 * (seed % 6)
    rounds, t = [], 0.4
    for j, s in enumerate(order):
        f = j / (len(order) - 1)
        gap = (0.2 - 0.1 * f) * pace          # between two bumps
        hold = (1.6 - 0.8 * f) * pace         # the full shape, to guess it
        n = len(SHAPES[s][1]())
        rounds.append((t, s, gap, hold))
        t += n * gap + RISE + hold + 0.75     # sinking + a breath
    return rounds, t


class HiddenShape(Sim):
    kind = "hidden_shape"
    experiment = "guess"
    concept = {
        "created": "2026-10-21T04:40:00+00:00",
        "idea": "Invisible shapes push up a stretchy sheet of 1,600 spheres from below, bump by bump (every bump "
                "plays a note) – a ring, a heart, a star, a cat … guess each one before its name appears. Every "
                "round is quicker.",
        "inspiration": "viral 'what's under the sheet / guess the hidden object' reels and the 3D particle-cloth "
                       "simulations of @particlesflow",
        "finale": "the last shape (no name, just '?') keeps rising until the sheet rips and a glossy Halloween "
                  "pumpkin bursts through (slow motion)",
    }
    titles = ["{onscreen}", "Guess the shape under the sheet before the name appears",
              "Something is pushing up this sheet of 1,600 balls – what is it?"]
    questions = ["How many shapes did you guess before the name showed up?", "What did you think the last one was?"]
    body = ("Hidden shapes push up a stretchy sheet of 1,600 touching spheres from below – every bump that appears "
            "plays the next note of {song}. Guess each shape before its name appears; the last one rips the sheet. "
            "Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.5
    trend_words = ("3d", "guess", "hidden", "sheet", "simulation", "satisfying")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    cta_y = 600

    @staticmethod
    def planned_end(seed: int) -> float:
        return _plan(seed)[1] + 9 * 0.09 + RISE + 0.6

    def __init__(self, seed: int):
        super().__init__(seed)
        self.rounds, self.T = _plan(seed)
        self.net = sim3d.Sheet(N, SIZE, FLOOR + SIZE / (N - 1) / 2, iters=10, compliance=1e-3)
        self.net.pin_border()
        self.balls = sim3d.Balls(16 * 14)
        self.k = 0
        self.round = -1
        self.items: list = []          # (ball index, start time, rest y, top y) of the current shape
        self.named = ""
        self.seen = np.zeros(self.balls.p.shape[0], bool)
        self.sinking = None
        self.hold_until = 0.0
        self.final = False
        self.lift = None
        self.prev_low = 0
        self.last_clack = -9.0
        top, deep = self.look.rnd.choice([((255, 214, 64), (255, 92, 28)), ((90, 230, 255), (150, 70, 255)),
                                          ((150, 240, 70), (20, 170, 120)), ((255, 120, 200), (255, 140, 40))])
        self.base = self.look.rnd.choice([(70, 78, 120), (96, 100, 118), (60, 92, 110)])  # flat sheet: cool grey
        self.shades = [sim3d.lerp_col(self.base, deep, min(1, i / 8)) if i < 9 else
                       sim3d.lerp_col(deep, top, (i - 8) / 15) for i in range(24)]  # bumps glow up by height
        self.tint = self.look.rnd.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])

    def _start(self, spheres, t0: float, gap: float, cols=None) -> None:
        b = self.balls
        for i in self.items:
            b.on[i[0]] = False
        self.items = []
        for j, (x, z, htop, r) in enumerate(spheres):
            rest = FLOOR - r - 0.02
            i = b.add((x, rest, z), (0.0, 0.0, 0.0), r, math.inf, cols[j] if cols else PUMPKIN)
            self.items.append([i, t0 + j * gap, rest, FLOOR + htop - r])
        self.seen[:] = False

    def step(self, dt: float) -> None:
        self.t += dt
        self.k += 1
        if self.k % PHYS == 0:
            self._physics(PHYS * dt)

    def _physics(self, h: float) -> None:
        b, t = self.balls, self.t
        nxt = self.round + 1
        if nxt < len(self.rounds) and t >= self.rounds[nxt][0]:
            self.round = nxt
            t0, s, gap, hold = self.rounds[nxt]
            self.named = ""
            self._start(SHAPES[s][1](), t0, gap)
            self.hold_until = t0 + len(self.items) * gap + RISE + hold
            self.sinking = None
        elif not self.final and nxt == len(self.rounds) and t >= self.T:
            self.final = True
            self.round = nxt
            self.named = ""
            pts = _pumpkin()
            self._start(pts + [(0.0, 0.0, 0.58, 0.07)], self.T, 0.09, [PUMPKIN] * len(pts) + [STEM])
            self.lift = self.T + len(self.items) * 0.09 + RISE
        if self.items and not self.final and not self.named and t >= self.hold_until - self.rounds[self.round][3] / 2:
            self.named = SHAPES[self.rounds[self.round][1]][0]  # the answer, while the shape is still up
        if self.items and not self.final and self.sinking is None and t >= self.hold_until:
            self.sinking = t
        for it in self.items:  # move the hidden spheres: rise one by one, hold, sink together
            i, t0, rest, top = it
            if self.sinking is not None:
                u = 1 - min(1.0, (t - self.sinking) / 0.25)
            else:
                u = min(1.0, max(0.0, (t - t0) / RISE))
            y = rest + (top - rest) * (u * u * (3 - 2 * u))
            if self.lift is not None and t > self.lift:
                y += min(0.42, 0.55 * (t - self.lift))   # the last one doesn't stop
            b.p[i, 1] = y
        broke = self.net.step(h, b, FLOOR, damp=0.99)
        for it in self.items:
            i = it[0]
            if b.touch[i] and not self.seen[i] and self.end is None:
                self.seen[i] = True
                self.events.append((t, "bounce", int(i)))
        # the sheet slapping back onto the platform after a shape sinks
        low = int(np.count_nonzero(self.net.P[..., 1] < FLOOR + self.net.r + 0.01))
        if self.sinking is not None and low - self.prev_low > 60 and t - self.last_clack > 0.2:
            self.events.append((t, "clack", 0))
            self.last_clack = t
        self.prev_low = low
        if self.lift is not None and t > self.lift and self.end is None:
            self.net.tear[:] = 1.45
            if broke or t > self.lift + 0.9:
                self.events.append((t, "break", 0))
                self.finish()

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, FLOOR + 0.15, 0.05), dist=9.6, yaw=0.5, pitch=0.8, fov=28, cy=H * 0.55)
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=1.25, thick=0.16, tint=self.tint)

    def render(self, p):
        a = (self.k % PHYS) / PHYS
        P = self.net.lerp(a).reshape(-1, 3)
        u = np.clip((P[:, 1] - FLOOR - self.net.r) / 0.32, 0, 1)
        cols = [self.shades[int(v * 23 + 0.5)] if v > 0.01 else self.base for v in u]
        pts, rad = P, np.full(len(P), self.net.r)
        if self.end is not None:  # torn open: the pumpkin shows itself
            b = self.balls
            on = [it[0] for it in self.items]
            pts = np.vstack([P, b.p[on]])
            rad = np.concatenate([rad, b.r[on]])
            cols = cols + [b.col[i] for i in on]
        img = self.studio.back.copy()
        img = self.studio.shadows(img, pts, rad, strength=0.35)
        self.studio.spheres(img, pts, rad, cols)
        return img

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["What's under", "the sheet?"]

    def counter(self) -> str:
        if self.final:
            return "LAST ONE: ???"
        if self.round < 0:
            return "Guess before the name appears"
        n = f"{self.round + 1}/{len(self.rounds)}"
        return f"{n} · it's {self.named}!" if self.named else f"{n} · guess it!"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("A PUMPKIN", PUMPKIN), ("RIPPED IT!", (255, 255, 255))]
