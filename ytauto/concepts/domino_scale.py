"""Domino scaling: a chain where every domino is a bit bigger than the one before – the first is a sliver, the last
is a giant. A marble taps the first one, the wave runs and grows, the camera keeps zooming out, every impact gets
heavier, and the giant at the end comes down in one huge slam."""
from __future__ import annotations

import math

from ..sims import CX, CY, SS, Painter, Sim, _mix

GROUND = 400.0      # screen y of the floor (simulation coordinates)
WIDTH = 0.19        # domino thickness / height
PITCH = 0.62        # distance between two dominoes (back face to back face) / height of the first
PIPS = {0: (), 1: ((0, 0),), 2: ((-1, -1), (1, 1)), 3: ((-1, -1), (0, 0), (1, 1)),
        4: ((-1, -1), (1, -1), (-1, 1), (1, 1)), 5: ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)),
        6: ((-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1))}
GOLD = (255, 205, 70)


class DominoScale(Sim):
    kind = "domino_scale"
    concept = {
        "created": "2026-10-17T08:30:00+00:00",
        "idea": "Domino scaling: a chain of dominoes where each one is ~9% bigger than the one before; a marble "
                "taps the first sliver, the wave grows, the camera keeps zooming out and every impact gets heavier.",
        "inspiration": "viral 'domino scaling / each domino is 1.5× bigger' clips and the classic 'tiny domino "
                       "topples a giant' chain reaction shorts",
        "finale": "the last regular domino tips a giant twice its size – it comes down in slow motion, the slam "
                  "shakes the screen and throws up a wall of dust, then the camera pulls back over the whole chain",
    }
    titles = ["{onscreen}", "Every domino is bigger than the last – wait for the giant",
              "One tiny domino vs. a giant – sound on"]
    questions = ["How many times bigger is the last one? Guess before the end!",
                 "Would the chain have made it with one domino less?"]
    body = ("A marble taps one tiny domino. Every domino is a little bigger than the one before, so the wave grows "
            "with every hit – until it reaches the giant at the end. Every impact plays the next note of {song}, "
            "and the hits get heavier the bigger they get.")
    playlist = ("Domino chains", "Every domino bigger than the last.")
    cover_at = 0.97
    trend_words = ("domino", "dominoes", "chain reaction", "bigger", "giant")
    slowmo = True
    finale_punch = 1.9
    note_gap = 0.05

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.n = rnd.randint(66, 80)                     # regular dominoes, then the giant
        self.k = rnd.uniform(1.07, 1.08)               # growth per domino
        self.jump = rnd.uniform(1.85, 2.15)              # the giant vs. the domino before it
        self.gamma = rnd.uniform(0.52, 0.6)              # gravity grows with size (keeps the big ones moving)
        self.g0 = rnd.uniform(17, 21)                    # first domino height = 1
        self.h = [self.k ** i for i in range(self.n)]
        self.h.append(self.h[-1] * self.jump)
        self.x = [0.0]                                   # back face of each domino (pivot = x + width)
        for i in range(1, len(self.h)):
            self.x.append(self.x[-1] + PITCH * self.h[i - 1] + (WIDTH * self.h[i] - WIDTH * self.h[i - 1]) * 0.5)
        self.N = len(self.h)
        self.front = 0                                   # the domino that is falling freely right now
        self.th, self.om = 0.0, 0.0
        self.hit_t = [-9.0] * self.N
        self.started = False
        self.marble = -3.2                               # marble x (world), rolls into the first domino
        self.landed = None
        g = self.look.rnd
        self.pips = [(g.randint(0, 6), g.randint(0, 6)) for _ in range(self.N)]

    # ------------------------------------------------------------------ physics
    def g(self, i: int) -> float:
        return self.g0 * self.h[i] ** self.gamma

    def pivot(self, i: int) -> float:
        return self.x[i] + WIDTH * self.h[i]

    def contact(self, i: int) -> float:
        """Angle at which domino i touches the (still upright) next one."""
        gap = self.x[i + 1] - self.pivot(i)
        return math.asin(min(1.0, gap / self.h[i]))

    def om_min(self, i: int) -> float:
        h, w = self.h[i], WIDTH * self.h[i]
        r = math.hypot(h, w) / 2
        return math.sqrt(6 * self.g(i) * (r - h / 2) / (h * h + w * w))

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        if not self.started:
            self.marble += dt * 4.2
            if self.marble + 0.22 >= 0:
                self.started = True
                self.om = 1.6 * self.om_min(0)
                self.hit_t[0] = self.t
                self.events.append((self.t, "clack", 0))
            return
        i = self.front
        h, w = self.h[i], WIDTH * self.h[i]
        acc = 3 * self.g(i) * (h * math.sin(self.th) - w * math.cos(self.th)) / (2 * (h * h + w * w))
        self.om += acc * dt
        self.th += self.om * dt
        if i == self.N - 1:
            if self.th >= math.pi / 2:
                self.th = math.pi / 2
                self.finish()
            return
        if self.th >= self.contact(i):
            j = i + 1
            v = self.om * self.h[i] * math.cos(self.th)            # tip speed into the next domino
            yc = self.h[i] * math.cos(self.th)
            om = max(0.75 * v / yc * (self.h[i] / self.h[j]) ** 1.5, 1.25 * self.om_min(j))
            self.front, self.th, self.om = j, 0.0, om
            self.hit_t[j] = self.t
            self.events.append((self.t, "bounce", j))
            if j % 4 == 0 or j >= self.N - 6:
                self.events.append((self.t, "clack", j))
            if j == self.N - 1:
                self.events.append((self.t, "break", j))

    # ------------------------------------------------------------------ geometry
    def angles(self) -> list[float]:
        """Angle of every domino: the front one falls freely, every one behind leans on its neighbour."""
        a = [0.0] * self.N
        f = self.front
        if self.started:
            a[f] = self.th
        for i in range(f - 1, -1, -1):
            a[i] = self._lean(i, a[i + 1])
        return a

    def _lean(self, i: int, phi: float) -> float:
        h, P = self.h[i], self.pivot(i)
        j = i + 1
        wj = WIDTH * self.h[j]
        bx, by = self.pivot(j) - wj * math.cos(phi), wj * math.sin(phi)   # back-bottom corner of j
        dx, dy = math.sin(phi), math.cos(phi)                              # up along j's back face

        def side(th: float) -> float:
            tx, ty = P + h * math.sin(th), h * math.cos(th)
            return dx * (ty - by) - dy * (tx - bx)

        lo, hi = 0.0, math.pi / 2
        if side(hi) < 0:
            return hi
        for _ in range(18):
            m = (lo + hi) / 2
            if side(m) < 0:
                lo = m
            else:
                hi = m
        return lo

    def progress(self) -> float:
        if not self.started:
            return 0.0
        i = self.front
        if i == self.N - 1:
            return i + min(1.0, self.th / (math.pi / 2)) * 0.6
        return i + min(1.0, self.th / self.contact(i))

    def camera(self) -> tuple[float, float]:
        q = self.progress()
        i = min(int(q), self.N - 2)
        f = q - i
        lh = math.log(self.h[i]) * (1 - f) + math.log(self.h[i + 1]) * f
        X = self.x[i] * (1 - f) + self.x[i + 1] * f
        u = min(1.0, q / (self.N - 1))
        end = 830 * self.h[-2] / self.h[-1]              # at the end the giant just fits on screen
        hs = 115 * (end / 115) ** (u ** 1.15)             # screen height of the front domino grows over the run
        z = hs / math.exp(lh)
        s = max(0.0, min(1.0, (q - (self.N - 4)) / 2.5))
        sx = -230 - 180 * s * s * (3 - 2 * s)            # front slides left so the giant has room to fall
        cam = X - sx / z
        if self.end is not None:                         # outro: pull back over the whole chain
            k = min(1.0, (self.t - self.end - 0.6) / 1.6)
            if k > 0:
                k = k * k * (3 - 2 * k)
                L = self.pivot(self.N - 1) + self.h[-1]
                zo = 940 / L
                z2 = math.exp(math.log(z) * (1 - k) + math.log(zo) * k)
                cam = (cam * z * (1 - k) + (L / 2) * zo * k) / (z * (1 - k) + zo * k)
                z = z2
        return cam, z

    # ------------------------------------------------------------------ picture
    def color(self, i: int) -> tuple[int, int, int]:
        return GOLD if i == self.N - 1 else self.look.color(i / (self.N - 1))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "bounce" and i >= self.N - 12:
            p.punch(0.12 + 0.5 * (i - (self.N - 12)) / 12)
        elif kind == "bounce" and i % 10 == 0:
            p.punch(0.18)
        elif kind == "finale":
            cam, z = self.camera()
            x0 = (self.pivot(self.N - 1) - cam) * z
            for q in range(7):
                p.parts.burst_point(p.rng, x0 + q * 125, GROUND - 6, (235, 225, 205), 50, 900)
            p.parts.burst_point(p.rng, x0 + 400, GROUND - 60, GOLD, 120, 1300)

    def _domino(self, p: Painter, i: int, th: float, cam: float, z: float, lit: float) -> None:
        h, w = self.h[i] * z, WIDTH * self.h[i] * z
        if h < 1.2:
            return
        px = (self.pivot(i) - cam) * z
        if px + h < -560 or px - w > 560:
            return
        s, c = math.sin(th), math.cos(th)

        def at(lx: float, ly: float) -> tuple[float, float]:   # local (from the pivot, ly up) -> screen
            return px + lx * c + ly * s, GROUND + lx * s - ly * c
        col = self.color(i)
        pts = [at(0, 0), at(-w, 0), at(-w, h), at(0, h)]
        fill = _mix(col, 0.16 + 0.5 * lit, (16, 16, 26))
        p.d.polygon([((CX + x) * SS, (CY + y) * SS) for x, y in pts], fill=fill)
        p.line(pts, _mix(col, 0.7 + 0.3 * lit, (255, 255, 255)), max(1.0, min(7.0, w * 0.13)), lit * 0.6,
               glow=col if h > 14 else None, closed=True)
        if h > 60:
            p.line([at(-w * 0.18, h / 2), at(-w * 0.82, h / 2)], _mix(col, 0.6), max(1.0, w * 0.05), glow=None)
        if h > 110:
            r, gap = w * 0.085, w * 0.24
            for half, n in enumerate(self.pips[i]):
                cy = h * (0.25 + 0.5 * half)
                for ox, oy in PIPS[n]:
                    x, y = at(-w / 2 + ox * gap, cy + oy * gap * 1.6)
                    p.ball(x, y, r, (235, 235, 245))

    def draw(self, p: Painter) -> None:
        cam, z = self.camera()
        p.line([(-560, GROUND + 3), (560, GROUND + 3)], (120, 120, 150), 4, glow=None)
        a = self.angles()
        lo = max(0, self.front - 140)
        for i in range(min(self.N - 1, self.front + 14), lo - 1, -1):
            lit = max(0.0, 1 - (self.t - self.hit_t[i]) / 0.35)
            self._domino(p, i, a[i], cam, z, lit)
        g = self.N - 1
        self._domino(p, g, a[g], cam, z, max(0.0, 1 - (self.t - self.hit_t[g]) / 0.6))
        if not self.started or self.t - self.hit_t[0] < 0.6:
            mx = (self.marble - cam) * z
            r = 0.22 * z
            p.ball(mx, GROUND - r, r, (245, 245, 255), (255, 255, 255), 1)
            p.glow_disc(mx, GROUND - r, r * 2, (120, 120, 160))
        p.particles()
        p.clip(-470, 500)

    def draw_text(self, p: Painter, d) -> None:
        super().draw_text(p, d)
        if self.end is None and self.front < self.N - 1:
            cam, z = self.camera()
            g = self.N - 1
            gx = (self.x[g] + WIDTH * self.h[g] / 2 - cam) * z
            gy = GROUND - self.h[g] * z - 70
            if -480 < gx < 480 and gy > -420:
                txt = f"×{self.h[g]:.0f}"
                wdt = d.textlength(txt, font=p.f_count)
                d.text((CX + gx - wdt / 2, CY + gy), txt, font=p.f_count, fill=GOLD, stroke_width=3,
                       stroke_fill=(0, 0, 0))

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return GOLD if self.front >= self.N - 3 else (255, 214, 120)

    def title(self) -> list[str]:
        return ["Every domino is bigger", "than the one before"]

    def counter(self) -> str:
        if self.front == self.N - 1:
            return f"THE GIANT · ×{self.h[-1]:.0f}"
        return f"domino {self.front + 1}/{self.N} · ×{self.h[self.front]:.1f}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"×{self.h[-1]:.0f}", GOLD), ("TIMBER!", (255, 255, 255))]
