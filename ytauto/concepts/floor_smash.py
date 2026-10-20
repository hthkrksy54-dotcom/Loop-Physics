"""Floor smash: a handful of bouncy balls hammer a glass floor until it cracks and shatters – and every broken floor
turns into new balls. The swarm falls to the next, stronger floor, the camera follows them down, and the last floor
is a golden core that only the whole swarm can break."""
from __future__ import annotations

import math

import numpy as np

from ..sims import TAU, Painter, Sim, _mix

WHITE = (255, 255, 255)
GOLD = (255, 205, 70)
RB = 15.0
XW = 440.0          # shaft walls at ±XW
GAP = 560.0         # distance between floors
THICK = 34.0
TICK = 6            # physics every 6th step (120 Hz)
G = 2600.0
STAGES = 12         # crack stages per floor – each one plays the next melody note
MAXN = 150


class FloorSmash(Sim):
    kind = "floor_smash"
    tempo = "fast"
    concept = {
        "created": "2026-10-20T03:30:00+00:00",
        "idea": "Bouncy balls hammer a glass floor until it cracks and shatters; every broken floor turns into new "
                "balls, the swarm drops to the next, stronger floor and the camera follows it down – floor after "
                "floor, until the golden core at the bottom.",
        "inspiration": "viral 'how many balls does it take to break the glass' and 'ball falls through 100 floors' "
                       "smash shorts, combined with the 'every hit adds a ball' multiply trend",
        "finale": "the last floor is a thick golden core; the whole swarm (well over 100 balls) hammers it in a final "
                  "frenzy, it cracks stage by stage and explodes in slow motion as everything rains into the void",
    }
    titles = ["{onscreen}", "Every broken floor turns into more balls – wait for the golden core",
              "How many balls does it take to smash the core?"]
    questions = ["Which floor did you think would stop them?", "Guess how many balls reach the core!"]
    body = ("A few bouncy balls hammer a glass floor. Every hit knocks, every new crack plays the next note of {song}, "
            "and when the floor shatters its shards turn into more balls. Floor after floor gets stronger – until the "
            "whole swarm reaches the golden core.")
    playlist = ("Smash through", "Every broken floor makes the swarm bigger.")
    cover_at = 0.93
    trend_words = ("smash", "glass", "floors", "balls", "break", "satisfying", "simulation")
    slowmo = True
    finale_punch = 1.8
    note_gap = 0.07

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.nf = rnd.choice((9, 10, 11))
        self.n0 = rnd.choice((4, 5, 6))
        self.add = rnd.uniform(0.55, 0.7)               # each broken floor adds this share of the swarm (+ shards)
        self.vb = rnd.uniform(1050, 1200)              # bounce speed off the floor
        dur = [rnd.uniform(5.0, 7.0) * (1 + 0.04 * k) for k in range(self.nf)]
        dur[-1] = rnd.uniform(5.5, 7.0)                # the golden core takes a while (the crowd hits less often)
        # floor HP from the hits per second the swarm will have on that floor (about N / bounce period)
        period = 2 * self.vb / G
        n, self.hp0 = self.n0, []
        for k in range(self.nf):
            self.hp0.append(int(n / period * dur[k] * rnd.uniform(0.85, 1.0)))
            n = min(MAXN, int(n * (1 + self.add)) + 2)
        self.hp = list(self.hp0)
        self.cur = 0
        self.stage = 0
        self.broke_at = [-9.0] * self.nf
        self.crack_x: list[list[float]] = [[] for _ in range(self.nf)]
        x = np.array([rnd.uniform(-XW + 40, XW - 40) for _ in range(self.n0)])
        y = np.array([self.fy(0) - THICK / 2 - RB - rnd.uniform(60, 420) for _ in range(self.n0)])
        self.x, self.y = x, y
        self.vx = np.array([rnd.uniform(-520, 520) for _ in range(self.n0)])
        self.vy = np.array([rnd.uniform(500, 900) for _ in range(self.n0)])   # already falling at frame one
        self.col = [rnd.random() for _ in range(self.n0)]
        self.cam = self.fy(0) - 300
        self.n_step = 0
        self.last_hit = -9.0
        self.hits = 0

    def fy(self, k: int) -> float:
        return GAP * (k + 1)

    def core(self) -> bool:
        return self.cur == self.nf - 1

    # ------------------------------------------------------------------ physics
    def step(self, dt: float) -> None:
        self.t += dt
        self.n_step += 1
        if self.n_step % TICK:
            return
        h = dt * TICK
        x, y, vx, vy = self.x, self.y, self.vx, self.vy
        vy += G * h
        x += vx * h
        y += vy * h
        # shaft walls
        lo, hi = x < -XW + RB, x > XW - RB
        x[lo], vx[lo] = -XW + RB, np.abs(vx[lo])
        x[hi], vx[hi] = XW - RB, -np.abs(vx[hi])
        tgt = (self.fy(min(self.cur, self.nf - 1)) - 300) if self.end is None else self.cam + 260 * h
        self.cam += (tgt - self.cam) * min(1.0, 3.0 * h)
        if self.end is not None:
            return
        # the current floor
        top = self.fy(self.cur) - THICK / 2
        hit = (y + RB > top) & (vy > 0) & (y < top + THICK)
        k = int(hit.sum())
        if k:
            y[hit] = top - RB
            boost = 1.18 if self.core() else 1.0      # the core frenzy: everybody bounces harder
            vy[hit] = -self.vb * boost * (0.94 + 0.12 * np.array([self.rnd.random() for _ in range(k)]))
            vx[hit] += np.array([self.rnd.uniform(-90, 90) for _ in range(k)])
            self.hits += k
            self.last_hit = self.t
            self.hp[self.cur] = max(0, self.hp[self.cur] - k)
            done = 1 - self.hp[self.cur] / self.hp0[self.cur]
            st = min(STAGES, int(done * STAGES))
            if self.hp[self.cur] == 0:
                self._shatter(float(x[hit][0]))
            elif st > self.stage:                        # a new crack: the melody note
                self.stage = st
                self.crack_x[self.cur].append(float(x[hit][0]))
                self.events.append((self.t, "bounce", self.cur))
            else:
                self.events.append((self.t, "clack", self.cur))
        if self.n_step % (2 * TICK) == 0:               # ball-ball contacts at 60 Hz are plenty
            self._collide()

    def _shatter(self, hx: float) -> None:
        k = self.cur
        self.broke_at[k] = self.t
        self.events.append((self.t, "break", k))
        if k == self.nf - 1:
            self.finish()
            return
        # the shards become new balls, dropping with the swarm
        n = len(self.x)
        add = max(0, min(MAXN, int(n * (1 + self.add)) + 2) - n)
        rnd = self.rnd
        nx = np.array([rnd.uniform(-XW + 30, XW - 30) for _ in range(add)])
        ny = np.full(add, self.fy(k)) + np.array([rnd.uniform(-30, 30) for _ in range(add)])
        self.x = np.concatenate([self.x, nx])
        self.y = np.concatenate([self.y, ny])
        self.vx = np.concatenate([self.vx, np.array([rnd.uniform(-400, 400) for _ in range(add)])])
        self.vy = np.concatenate([self.vy, np.array([rnd.uniform(-300, 200) for _ in range(add)])])
        self.col += [rnd.random() for _ in range(add)]
        self.cur += 1
        self.stage = 0

    def _collide(self) -> None:
        x, y = self.x, self.y
        dx = x[None, :] - x[:, None]
        dy = y[None, :] - y[:, None]
        d2 = dx * dx + dy * dy
        ii, jj = np.nonzero(np.triu(d2 < (2 * RB) ** 2, 1))
        if not len(ii):
            return
        ddx, ddy = dx[ii, jj], dy[ii, jj]
        dd = np.sqrt(ddx * ddx + ddy * ddy) + 1e-9
        nx, ny = ddx / dd, ddy / dd
        push = (2 * RB - dd) / 2
        np.add.at(x, ii, -nx * push)
        np.add.at(y, ii, -ny * push)
        np.add.at(x, jj, nx * push)
        np.add.at(y, jj, ny * push)
        vn = (self.vx[jj] - self.vx[ii]) * nx + (self.vy[jj] - self.vy[ii]) * ny
        vn = np.minimum(vn, 0)
        np.add.at(self.vx, ii, vn * nx)
        np.add.at(self.vy, ii, vn * ny)
        np.add.at(self.vx, jj, -vn * nx)
        np.add.at(self.vy, jj, -vn * ny)

    def good(self) -> bool:
        return self.end is not None

    # ------------------------------------------------------------------ picture
    def floor_col(self, k: int) -> tuple[int, int, int]:
        return GOLD if k == self.nf - 1 else self.look.color(k / max(1, self.nf - 2))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        sy = self.fy(i) - self.cam
        if kind == "break":
            col = self.floor_col(i)
            for _ in range(5 if i == self.nf - 1 else 3):
                p.parts.burst_path(p.rng, [(-XW, sy), (XW, sy)], col, 70)
            p.parts.burst_path(p.rng, [(-XW, sy), (XW, sy)], WHITE, 40)
            p.punch(0.45 + 0.08 * i)
        elif kind == "bounce":
            cx = self.crack_x[i][-1]
            p.parts.burst_point(p.rng, cx, sy, _mix(self.floor_col(i), 0.9), 8, 220)
            if i == self.nf - 1:                           # every crack in the core shakes the screen a bit more
                p.punch(0.12 + 0.03 * len(self.crack_x[i]))
        elif kind == "finale":
            p.parts.burst_point(p.rng, 0, sy, GOLD, 260, 1100)
            p.parts.burst_point(p.rng, 0, sy, WHITE, 120, 700)

    def draw(self, p: Painter) -> None:
        t, cam = self.t, self.cam
        # shaft walls
        for sx in (-XW - 8, XW + 8):
            p.line([(sx, -470), (sx, 500)], (90, 90, 130), 6, glow=None)
        # floors: intact ones with cracks, broken ones as stubs at the walls
        for k in range(self.nf):
            sy = self.fy(k) - cam
            if sy < -560 or sy > 640:
                continue
            col = self.floor_col(k)
            thick = THICK * (1.8 if k == self.nf - 1 else 1.0)
            if k < self.cur or (k == self.cur and self.end is not None):
                p.line([(-XW, sy), (-XW + 40, sy + 10)], _mix(col, 0.6), thick * 0.7, glow=None)
                p.line([(XW, sy), (XW - 46, sy + 8)], _mix(col, 0.6), thick * 0.7, glow=None)
                continue
            done = 1 - self.hp[k] / self.hp0[k]
            flash = max(0.0, 1 - (t - self.last_hit) / 0.12) * 0.35 if k == self.cur else 0.0
            if k == self.cur and self.core():
                flash += 0.25 * (0.5 + 0.5 * math.sin(t * 12))
            p.line([(-XW, sy), (XW, sy)], _mix(col, 1 - 0.35 * done), thick, flash, glow=col)
            for j, cx in enumerate(self.crack_x[k]):     # jagged cracks spreading from every new crack
                for side in (-1, 1):
                    pts, px = [(cx, sy)], cx
                    for s_ in range(5):
                        px += side * (22 + 10 * abs(math.sin(j * 3.7 + s_ * 1.9)) + 4 * j)
                        pts.append((max(-XW, min(XW, px)), sy + thick * 0.42 * math.sin(j * 5.3 + s_ * 2.1 + side)))
                    p.line(pts, WHITE, 3, glow=None)
                p.line([(cx, sy - thick * 0.5), (cx + 6 * math.sin(j), sy + thick * 0.5)], WHITE, 3, glow=None)
        p.particles()
        n = len(self.x)
        for j in range(n):
            sx, sy = float(self.x[j]), float(self.y[j]) - cam
            if sy < -490 or sy > 520:
                continue
            col = self.look.color(self.col[j])
            p.glow_disc(sx, sy, RB * 2.0, _mix(col, 0.5))
            p.ball(sx, sy, RB, col, WHITE, 2)
        p.clip(-470, 500)

    def draw_text(self, p: Painter, d) -> None:
        super().draw_text(p, d)
        if self.end is None:                              # the floor's remaining HP right on the glass
            sy = self.fy(self.cur) - self.cam
            txt = f"{self.hp[self.cur]}"
            p.centered(d, 960 + sy + 30, txt, p.f_count, GOLD if self.core() else WHITE, 3)

    def title(self) -> list[str]:
        return [f"Can {self.n0} balls smash", f"through {self.nf} floors?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"{len(self.x)} balls · all {self.nf} floors smashed"
        if self.core():
            return f"THE GOLDEN CORE · {len(self.x)} balls"
        return f"floor {self.cur + 1}/{self.nf} · {len(self.x)} balls"

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return GOLD if self.core() else (255, 214, 120)

    def finale(self) -> list[tuple[str, tuple]]:
        return [("CORE SMASHED!", GOLD), (f"{len(self.x)} balls · {self.hits} hits", WHITE)]
