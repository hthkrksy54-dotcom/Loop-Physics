"""Black hole: a spinning galaxy of a few hundred coloured balls orbits a tiny black hole. Every ball that crosses
the event horizon is gone for good, makes the hole bigger and its pull stronger – so the disc spirals in faster and
faster, ring after ring of colour falls in, and when the very last ball is swallowed the hole goes supernova."""
from __future__ import annotations

import math

import numpy as np

from ..sims import TAU, Painter, Sim, _mix

H_PHYS = 1 / 120     # physics step (vectorised, every 6 render substeps)
R_WALL = 470.0
WHITE = (255, 255, 255)


class BlackHole(Sim):
    kind = "black_hole"
    concept = {
        "created": "2026-10-17T13:00:00+00:00",
        "idea": "A galaxy of a few hundred coloured balls orbits a tiny black hole; every ball it swallows makes it "
                "bigger and its pull stronger, so the disc spirals in faster and faster until nothing is left.",
        "inspiration": "viral 'black hole eats everything' / 'gravity simulation' shorts and the 'can it eat all "
                       "the balls?' ball-simulation trend",
        "finale": "the last ring of balls whirls in at top speed, the hole swallows the final ball, collapses to a "
                  "point and explodes in a supernova of every colour it ate, with a white shockwave",
    }
    titles = ["{onscreen}", "Every ball it eats makes the black hole stronger – wait for the end",
              "A black hole vs. a galaxy of balls – sound on"]
    questions = ["Which colour do you think falls in last?",
                 "At what count did you think it would never finish?"]
    body = ("A few hundred balls orbit a tiny black hole. Every ball that crosses the event horizon plays the next "
            "note of {song} and makes the hole bigger and its pull stronger – so the galaxy spirals in faster and "
            "faster until the last ball is gone.")
    playlist = ("Gravity", "Orbits, black holes and everything falling in.")
    cover_at = 0.93
    trend_words = ("black hole", "gravity", "galaxy", "orbit", "eat", "space")
    slowmo = True
    finale_punch = 2.0
    note_gap = 0.07

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.n = n = rnd.randint(260, 320)
        self.rb = 8.5
        self.g0 = rnd.uniform(5.5e6, 7.0e6)          # GM of the hole at the start
        self.c0 = rnd.uniform(0.0027, 0.0039)         # orbital drag (grows with time)
        self.spin = rnd.choice((-1.0, 1.0))
        rad, ang, sp = [], [], []
        for i in range(n):
            if i < n // 9:
                r = 27 * (100 / 27) ** rnd.random()              # an inner disc that starts falling in at once
            else:
                r = 32 * (445 / 32) ** (rnd.random() ** 0.42)    # log-spread, denser far out
            rad.append(r)
            ang.append(rnd.uniform(0, TAU))
            sp.append(rnd.gauss(1.0, 0.035))
        rad, ang, sp = np.array(rad), np.array(ang), np.array(sp)
        v = np.sqrt(self.g0 / rad) * sp * self.spin
        self.P = np.stack([np.cos(ang) * rad, np.sin(ang) * rad], 1)
        self.V = np.stack([-np.sin(ang) * v, np.cos(ang) * v], 1)
        self.r0 = rad
        self.alive = np.ones(n, bool)
        self.eaten = 0
        self.acc_t = 0.0
        self.last_eat = -9.0
        self.swallow: list[tuple[float, float, int]] = []    # (time, angle, ball) for the horizon flashes
        self.prev = self.P.copy()

    # ------------------------------------------------------------------ physics
    def gm(self) -> float:
        return self.g0 * (1 + 0.6 * self.eaten / self.n)

    def horizon(self) -> float:
        return 24 + 70 * math.sqrt(self.eaten / self.n)

    def left(self) -> int:
        return self.n - self.eaten

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        self.acc_t += dt
        if self.acc_t < H_PHYS - 1e-9:
            return
        self.acc_t -= H_PHYS
        h = H_PHYS
        idx = np.flatnonzero(self.alive)
        P, V = self.P[idx], self.V[idx]
        r2 = (P * P).sum(1)
        r = np.sqrt(r2)
        gm = self.gm() * (1 + 1.5 * max(0, 30 - self.left()) / 30)    # the last 30 feel the full pull
        V -= (gm / (r2 * r))[:, None] * P * h
        drag = self.c0 * (1 + (self.t / 30) ** 2) * (1 + 2.0 * max(0, 40 - self.left()) / 40)
        V *= (1 - drag * h * np.minimum(8.0, (150 / r) ** 1.5))[:, None]   # the gas gets denser near the hole
        P += V * h
        r = np.sqrt((P * P).sum(1))
        out = r > R_WALL - self.rb
        if out.any():
            nrm = P[out] / r[out, None]
            vn = (V[out] * nrm).sum(1)
            V[out] -= (2 * np.maximum(vn, 0))[:, None] * nrm
            P[out] = nrm * (R_WALL - self.rb)
        self.P[idx], self.V[idx] = P, V
        gone = idx[r < self.horizon() + self.rb * 0.3]
        for j in gone:
            self.alive[j] = False
            self.eaten += 1
            self.last_eat = self.t
            self.swallow.append((self.t, math.atan2(self.P[j, 1], self.P[j, 0]), int(j)))
            self.events.append((self.t, "bounce", self.eaten))
            if self.eaten % 50 == 0 and self.left() > 0:
                self.events.append((self.t, "break", self.eaten))
            if self.left() <= 10:
                self.events.append((self.t, "tone", 10 - self.left()))
        if self.left() == 0:
            self.finish()

    def good(self) -> bool:
        return self.eaten == self.n

    # ------------------------------------------------------------------ picture
    def color(self, j: int) -> tuple[int, int, int]:
        return self.look.color(math.log(self.r0[j] / 27) / math.log(445 / 27))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.35 + 0.15 * i / 50)
        elif kind == "finale":
            cols = [self.look.color(u / 5) for u in range(6)]
            for c in cols:
                p.parts.burst_point(p.rng, 0, 0, c, 120, 1500)
            p.parts.burst_point(p.rng, 0, 0, WHITE, 160, 900)

    def draw(self, p: Painter) -> None:
        t = self.t
        rh = self.horizon()
        if self.end is not None:
            age = t - self.end
            shock = 30 + 1700 * age
            if shock < 1400:
                k = max(0.0, 1 - age / 0.8)
                p.ring(shock, 0, 360, _mix(WHITE, 0.25 + 0.75 * k), 6 + 30 * k, k)
                p.ring(shock * 0.7, 0, 360, _mix(self.look.color(0.3), 0.3 + 0.7 * k), 4 + 16 * k, 0)
            core = max(0.0, 1 - age / 0.35) * rh
            p.glow_disc(0, 0, 140 + 400 * max(0.0, 1 - age / 1.2), _mix(WHITE, max(0.0, 1 - age / 1.5)))
            if core > 1:
                p.ball(0, 0, core, (0, 0, 0), WHITE, 3)
            p.particles()
            return
        # accretion glow, coloured by what fell in last
        fresh = max(0.0, 1 - (t - self.last_eat) / 0.25)
        last_col = self.color(self.swallow[-1][2]) if self.swallow else self.look.color(0.0)
        frenzy = min(1.0, self.eaten / self.n) ** 2
        p.glow_disc(0, 0, rh * (1.8 + 0.4 * frenzy), _mix(last_col, 0.25 + 0.3 * fresh + 0.15 * frenzy))
        p.ring(rh + 14, 0, 360, _mix(self.look.color(0.5), 0.25), 2, 0)
        # balls with a short motion streak
        idx = np.flatnonzero(self.alive)
        prev, P = self.prev, self.P
        for j in idx:
            x, y = P[j]
            col = self.color(j)
            px, py = prev[j]
            if (x - px) ** 2 + (y - py) ** 2 > 9:
                sx, sy = x - (x - px) * 2.2, y - (y - py) * 2.2
                p.line([(sx, sy), (x, y)], _mix(col, 0.45), self.rb * 1.1, glow=None)
            p.ball(x, y, self.rb, col)
            p.glow_disc(x, y, self.rb * 1.7, _mix(col, 0.22))
        self.prev = P.copy()
        # the hole: black disc, bright photon ring, flashes where balls just crossed
        p.ball(0, 0, rh, (0, 0, 0))
        p.ring(rh + 3, 0, 360, _mix(WHITE, 0.55 + 0.45 * fresh), 4 + 3 * frenzy, 0.3 * fresh)
        self.swallow = [s for s in self.swallow if t - s[0] < 0.4]
        for t0, a, j in self.swallow:
            k = 1 - (t - t0) / 0.4
            deg = math.degrees(a)
            p.ring(rh + 5, deg - 14 * k, 28 * k, self.color(j), 8 * k + 2, 0.5 * k)
        p.ball(0, 0, rh - 1, (0, 0, 0))
        p.glow_disc(0, 0, rh * 0.9, (0, 0, 0))            # keep the hole itself black under the glow

    def title(self) -> list[str]:
        return ["Can the black hole", f"eat all {self.n} balls?"]

    def counter(self) -> str:
        left = self.left()
        if self.end is not None:
            return f"{self.n} of {self.n} eaten"
        if left <= 20:
            return f"ONLY {left} LEFT!"
        return f"{left} balls left"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("ALL EATEN!", WHITE), ("SUPERNOVA", (255, 210, 90))]
