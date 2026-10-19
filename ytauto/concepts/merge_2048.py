"""Merge to 2048: numbered balls bounce around a ring and two balls with the same number merge into the next one
(16 + 16 = 32, 32 + 32 = 64 ...). A portal in the centre keeps firing new 16s, faster and faster; when the last one
is out, same numbers start to pull at each other and the final merge cascade builds up to a single 2048 ball."""
from __future__ import annotations

import math

import numpy as np

from ..sims import CX, CY, SS, TAU, Painter, Sim, _font, _mix

WHITE = (255, 255, 255)
GOLD = (255, 214, 90)
TIERS = 8                       # 16, 32, 64 ... 2048
UNITS = 2 ** (TIERS - 1)        # 128 balls of 16 make one 2048
R0 = 16.0                       # radius of a 16; area doubles with every merge
RAD = [R0 * math.sqrt(2 ** k) for k in range(TIERS)]
COLS = [(70, 210, 255), (80, 125, 255), (165, 95, 255), (255, 85, 205), (255, 70, 85), (255, 140, 45),
        (255, 215, 60), (255, 236, 150)]
ARENA = 470.0
TICK = 8                        # physics at 90 Hz – plenty at these speeds, cheap enough for the seed search


class Merge2048(Sim):
    kind = "merge_2048"
    concept = {
        "created": "2026-10-19T12:20:00+00:00",
        "idea": "Numbered balls bounce inside a ring and every two balls with the same number merge into the next "
                "one (16+16=32 ... 1024+1024=2048); a portal fires new 16s faster and faster, then the same numbers "
                "pull at each other until one 2048 ball is left.",
        "inspiration": "viral 'Will the ball merge into final form?' simulation shorts and the evergreen 2048 / "
                       "merge-game (Suika) satisfaction, rebuilt as a free-flying ball physics run",
        "finale": "the portal closes, a FINAL MERGE cascade chains 64→128→256→512→1024 and the two 1024 balls "
                  "collide in slow motion into one giant golden 2048 with a shockwave",
    }
    titles = ["{onscreen}", "Every touch merges two balls – can they reach 2048?",
              "16 + 16 = 32 … wait for the final merge"]
    questions = ["Which merge was the most satisfying? 🔥", "Guess the second the 2048 appears!",
                 "What should merge next – 4096? 👀"]
    body = ("Two balls with the same number merge into the next one – 16, 32, 64 … all the way to 2048. The portal in "
            "the middle fires new 16s faster and faster, every merge rings a higher note and every wall bounce plays "
            "the next note of {song}. Then the portal closes and the final merge begins.")
    playlist = ("Merge to 2048", "Same numbers merge – until only one is left.")
    cover_at = 0.92
    trend_words = ("merge", "2048", "final form", "satisfying", "ball", "simulation", "asmr")
    slowmo = True
    finale_punch = 1.8
    note_gap = 0.16

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.v0 = rnd.uniform(230, 270)                      # cruising speed of a 16
        self.start = rnd.choice((36, 40, 44))                # 16s on the board at t = 0
        self.Ts = rnd.uniform(44, 66)                        # when the portal closes
        self.curve = rnd.uniform(1.4, 1.9)                   # how sharply the firing rate rises
        self.pull0 = rnd.uniform(0, 25)                      # weak same-number pull while the portal is open
        self.pull1 = rnd.uniform(70, 130)                    # how fast it grows in the final merge
        x, y, k = [], [], []
        while len(x) < self.start:
            a, r = rnd.uniform(0, TAU), math.sqrt(rnd.uniform(0.06, 0.92)) * (ARENA - 30)
            px, py = math.cos(a) * r, math.sin(a) * r
            if all((px - qx) ** 2 + (py - qy) ** 2 > (3 * R0) ** 2 for qx, qy in zip(x, y)):
                x.append(px)
                y.append(py)
                k.append(0)
        self.x, self.y, self.k = np.array(x), np.array(y), np.array(k, int)
        ang = np.array([rnd.uniform(0, TAU) for _ in x])
        self.vx, self.vy = np.cos(ang) * self.v0, np.sin(ang) * self.v0
        self.born = np.zeros(len(x))
        self.ids = np.arange(len(x))                         # stable ids for trails
        self.next_id = len(x)
        self.spawned = self.start
        self.merges = 0
        self.wall_hits = 0
        self.n_step = 0
        self.last_merge = (-9.0, 0.0, 0.0, 0)                # time, x, y, tier
        self.last_fire = -9.0
        self.close = 0.0                                     # when the last 16 left the portal

    # ------------------------------------------------------------------ physics
    def final(self) -> bool:
        return self.spawned >= UNITS

    def due(self) -> int:
        """How many 16s the portal should have fired by now – slowly at first, faster and faster."""
        u = min(1.0, self.t / self.Ts)
        return self.start + int((UNITS - self.start) * u ** self.curve)

    def biggest(self) -> int:
        return 16 * 2 ** int(self.k.max())

    def _fire(self) -> None:
        r2 = self.x ** 2 + self.y ** 2
        clear = (np.sqrt(r2) - np.array(RAD)[self.k]).min() > 2.2 * R0 if len(r2) else True
        if not clear:
            return
        a = self.rnd.uniform(0, TAU)
        self.x = np.append(self.x, 0.0)
        self.y = np.append(self.y, 0.0)
        self.vx = np.append(self.vx, math.cos(a) * self.v0 * 1.3)
        self.vy = np.append(self.vy, math.sin(a) * self.v0 * 1.3)
        self.k = np.append(self.k, 0)
        self.born = np.append(self.born, self.t)
        self.ids = np.append(self.ids, self.next_id)
        self.next_id += 1
        self.spawned += 1
        self.last_fire = self.t
        self.events.append((self.t, "clack", self.spawned))

    def step(self, dt: float) -> None:
        self.t += dt
        self.n_step += 1
        if self.n_step % TICK:
            return
        h = dt * TICK
        if self.end is not None:                             # outro: the 2048 drifts to the centre
            self.x += (0 - self.x) * 2 * h
            self.y += (0 - self.y) * 2 * h
            return
        if not self.final() and self.spawned < self.due():
            self._fire()
            if self.final():
                self.close = self.t
        x, y, k = self.x, self.y, self.k
        rad = np.array(RAD)[k]
        m = rad * rad
        dx = x[None, :] - x[:, None]                         # dx[i, j] = x_j - x_i
        dy = y[None, :] - y[:, None]
        d2 = dx * dx + dy * dy
        n = len(x)
        np.fill_diagonal(d2, 1e12)
        d = np.sqrt(d2)
        same = k[:, None] == k[None, :]
        # same numbers pull at each other – weakly while the portal is open, harder and harder in the final merge
        pull = self.pull0 + (self.pull1 * (self.t - self.close) ** 1.3 if self.final() else 0.0)
        if pull > 0 and n > 1:
            w = np.where(same, 1.0 / (d + 60.0), 0.0)
            self.vx += (w * dx).sum(axis=1) * pull * h
            self.vy += (w * dy).sum(axis=1) * pull * h
        # everybody cruises at the speed of its number (bigger = slower), faster once the final merge starts
        boost = 1.0 + (min(0.6, 0.06 * (self.t - self.close)) if self.final() else 0.0)
        want = self.v0 * boost * (1 - 0.07 * k)
        sp = np.sqrt(self.vx ** 2 + self.vy ** 2) + 1e-9
        f = 1 + (want / sp - 1) * min(1.0, 1.5 * h)
        self.vx *= f
        self.vy *= f
        x += self.vx * h
        y += self.vy * h
        # touching pairs
        touch = d < rad[:, None] + rad[None, :]
        ii, jj = np.nonzero(np.triu(touch, 1))
        gone: set[int] = set()
        bumps = []
        for i, j in zip(ii.tolist(), jj.tolist()):
            if k[i] == k[j]:
                if i in gone or j in gone or k[i] >= TIERS - 1:
                    continue
                gone.add(j)                                  # j melts into i
                mi = m[i] + m[j]
                x[i] = (x[i] * m[i] + x[j] * m[j]) / mi
                y[i] = (y[i] * m[i] + y[j] * m[j]) / mi
                self.vx[i] = (self.vx[i] + self.vx[j]) / 2
                self.vy[i] = (self.vy[i] + self.vy[j]) / 2
                k[i] += 1
                self.born[i] = self.t
                self.merges += 1
                self.last_merge = (self.t, float(x[i]), float(y[i]), int(k[i]))
                self.events.append((self.t, "tone", min(39, 4 + 5 * int(k[i]))))
                if k[i] >= 4:
                    self.events.append((self.t, "break", int(k[i])))
                if k[i] == TIERS - 1:
                    self.x, self.y, self.k = x, y, k
                    self._drop(gone)
                    self.finish()
                    return
            else:
                bumps.append((i, j))
        for i, j in bumps:                                   # elastic bounce between different numbers
            if i in gone or j in gone:
                continue
            ddx, ddy = x[j] - x[i], y[j] - y[i]
            dd = math.hypot(ddx, ddy) or 1e-9
            nx, ny = ddx / dd, ddy / dd
            over = rad[i] + rad[j] - dd
            if over <= 0:
                continue
            wi, wj = m[j] / (m[i] + m[j]), m[i] / (m[i] + m[j])
            x[i] -= nx * over * wi
            y[i] -= ny * over * wi
            x[j] += nx * over * wj
            y[j] += ny * over * wj
            vn = (self.vx[j] - self.vx[i]) * nx + (self.vy[j] - self.vy[i]) * ny
            if vn < 0:
                ji, jj_ = 2 * m[j] / (m[i] + m[j]) * vn, 2 * m[i] / (m[i] + m[j]) * vn
                self.vx[i] += ji * nx
                self.vy[i] += ji * ny
                self.vx[j] -= jj_ * nx
                self.vy[j] -= jj_ * ny
        self.x, self.y, self.k = x, y, k
        if gone:
            self._drop(gone)
        # the ring
        rad = np.array(RAD)[self.k]
        R = ARENA - rad
        r = np.sqrt(self.x ** 2 + self.y ** 2) + 1e-9
        out = r > R
        if out.any():
            nx, ny = self.x[out] / r[out], self.y[out] / r[out]
            self.x[out], self.y[out] = nx * R[out], ny * R[out]
            vn = self.vx[out] * nx + self.vy[out] * ny
            back = vn > 0
            self.vx[out] -= np.where(back, 2 * vn * nx, 0)
            self.vy[out] -= np.where(back, 2 * vn * ny, 0)
            if back.any():
                self.wall_hits += 1
                self.events.append((self.t, "bounce", self.wall_hits))

    def _drop(self, gone: set[int]) -> None:
        keep = np.array([i not in gone for i in range(len(self.x))])
        for name in ("x", "y", "vx", "vy", "k", "born", "ids"):
            setattr(self, name, getattr(self, name)[keep])

    # ------------------------------------------------------------------ picture
    def prepare(self, p: Painter) -> None:
        self.fonts = {}
        for kk in range(TIERS):
            label = str(16 * 2 ** kk)
            size = int(RAD[kk] * SS * (1.05 if len(label) <= 2 else 0.9 if len(label) == 3 else 0.72))
            self.fonts[kk] = _font("Poppins-ExtraBold.ttf", max(12, size))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "tone" or kind == "break":
            t0, mx, my, kk = self.last_merge
            if kind == "tone":
                p.parts.burst_point(p.rng, mx, my, COLS[kk], 8 + 5 * kk, 120 + 50 * kk)
            elif kk >= 5:
                p.punch(0.2 + 0.25 * (kk - 4))
                p.parts.burst_ring(p.rng, ARENA, 0, TAU, COLS[kk], 40 * (kk - 3))
        elif kind == "finale":
            _, mx, my, _ = self.last_merge
            for c in (GOLD, WHITE, GOLD):
                p.parts.burst_point(p.rng, mx, my, c, 220, 1100)
            p.parts.burst_ring(p.rng, ARENA, 0, TAU, GOLD, 320)

    def draw(self, p: Painter) -> None:
        t = self.t
        final = self.final() and self.end is None
        pulse = 0.5 + 0.5 * math.sin(t * (12 if final else 4))
        ring_col = GOLD if self.end is not None else (COLS[int(self.k.max())] if final else (150, 160, 210))
        p.ring(ARENA + 8, 0, 360, ring_col, 12, 0.3 * pulse if final else 0.0)
        # the portal in the middle (closes when the last 16 is out)
        if not self.final():
            fire = max(0.0, 1 - (t - self.last_fire) / 0.25)
            pr = 26 + 8 * fire
            p.glow_disc(0, 0, pr * 2.4, _mix(COLS[0], 0.7 + 0.3 * fire))
            p.ball(0, 0, pr, _mix(COLS[0], 0.25), WHITE if fire > 0.3 else COLS[0], 4)
        p.particles()
        order = np.argsort(self.k)                           # small ones below big ones
        top = int(self.k.max())
        for j in order.tolist():
            x, y, kk = float(self.x[j]), float(self.y[j]), int(self.k[j])
            fresh = max(0.0, 1 - (t - self.born[j]) / 0.35)
            r = RAD[kk] * (1 + 0.35 * fresh * (1 - fresh) * 4 * 0.5)
            col = COLS[kk]
            if kk >= 3:
                p.trail(int(self.ids[j]), x, y, r, col, 8)
            hot = kk == top and (final or self.end is not None)
            p.glow_disc(x, y, r + 14 + 22 * fresh + (16 * pulse if hot else 0), _mix(col, 0.45 + 0.4 * fresh))
            p.ball(x, y, r, _mix(col, 0.5), WHITE if fresh > 0.4 else col, 4 if kk < 3 else 7)
            p.ball(x, y, r * 0.78, _mix(col, 0.72))
            if self.end is not None:
                continue                                     # the finale text says it
            label = str(16 * 2 ** kk)
            f = self.fonts[kk]
            X, Y = (CX + x) * SS, (CY + y) * SS
            p.d.text((X, Y), label, font=f, fill=WHITE, anchor="mm", stroke_width=max(2, int(r * 0.12)),
                     stroke_fill=(0, 0, 0))
        p.clip(-470, 500)

    def title(self) -> list[str]:
        return ["Can they merge", "into 2048?"]

    def counter(self) -> str:
        n = len(self.x)
        if self.end is not None:
            return f"2048 in {self.merges} merges"
        if self.final():
            return f"FINAL MERGE · {n} balls left"
        return f"{n} balls · biggest {self.biggest()}"

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return (255, 110, 80) if self.final() and self.end is None else GOLD

    def finale(self) -> list[tuple[str, tuple]]:
        return [("2048!", GOLD), (f"{self.merges} merges", WHITE)]
