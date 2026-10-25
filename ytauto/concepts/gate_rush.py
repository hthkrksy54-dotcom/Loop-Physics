"""Gate rush: one ball drops into a glass shaft full of peg rods and multiplier gates (×2, ×3, ×5 … and red ×0 /
÷2 traps). Every ball that falls through a gate turns into that many balls – 1 becomes 3, 3 become 15, 15 become
hundreds – until a flood of thousands of glossy beads rains into the box at the bottom. Can it fill the box to the
goal line? Then the box bursts.

A numbered series (experiment "series"): RUN #N, the goal grows by 500 balls every episode and the finale teases
the next one. The episode number is the seed + 1 – the run ranges are wide, so practically every seed fits and the
numbers count up by themselves.

3D (ytauto/sim3d.py look): every ball is a real sphere (gravity, peg rods, walls, ball–ball contacts, compiled
with numba), the camera falls with the front of the swarm. The gates are planned on the fly from the expected
number of balls, so the count really grows to the goal – every number on screen is the real count.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim, _font, _rgb

RB = 0.03            # ball radius (m)
RP = 0.024           # peg rod radius
PS = 0.2             # peg spacing in a row
RS = 0.17            # row spacing
HW = 0.64            # half width of the shaft
HZ = 0.19            # half depth of the shaft
BX, BZ = 0.72, 0.4   # half size of the box at the bottom
DROP = 1.1           # free fall from the shaft into the box
PHYS = 6             # physics every 6th step (120 Hz)
GRAV = 2.2           # lighter than earth: a slow-motion look, the swarm stays readable
CAP = 14000
TBL = 1 << 15
GATES = 11
ROWS = [0, 9, 12, 16, 18, 19, 19, 19, 21, 21, 19]   # peg rows above each gate (the first gate comes right away)
GOLD = (255, 214, 64)
RED = (255, 64, 70)
ORANGE = (255, 150, 40)


@njit(cache=True)
def _phys(P, V, live, n, h, g, nry, roff, ysb, yfl, hw, hz, bx, bz, imp, head, nxt):  # compiled: plain loops
    e_peg, e_ball, e_wall = 0.42, 0.15, 0.35
    for i in range(n):
        imp[i] = 0.0
        if live[i] == 0:
            continue
        V[i, 1] -= g * h
        for c in range(3):
            P[i, c] += V[i, c] * h
    reach = RB + RP
    for i in range(n):
        if live[i] == 0:
            continue
        x, y = P[i, 0], P[i, 1]
        if y > ysb:  # in the shaft: peg rods (along z) in the rows next to the ball
            j = np.searchsorted(nry, -y - reach)
            while j < nry.shape[0] and -nry[j] > y - reach:
                py = -nry[j]
                off = roff[j]
                c = math.floor((x - off) / PS + 0.5)
                for dc in range(-1, 3):
                    if dc == 2:                     # the rod touching the nearer wall
                        px = (hw - RP) if x > 0 else -(hw - RP)
                    else:
                        px = off + (c + dc) * PS
                        if abs(px) > hw - RP - 0.1:
                            continue
                    dx, dy = x - px, y - py
                    d = math.sqrt(dx * dx + dy * dy)
                    if d < reach and d > 1e-9:
                        nx, ny = dx / d, dy / d
                        P[i, 0] = px + nx * reach
                        P[i, 1] = py + ny * reach
                        x, y = P[i, 0], P[i, 1]
                        vn = V[i, 0] * nx + V[i, 1] * ny
                        if vn < 0:
                            V[i, 0] -= (1 + e_peg) * vn * nx
                            V[i, 1] -= (1 + e_peg) * vn * ny
                            V[i, 0] *= 0.97
                            V[i, 2] *= 0.97
                            if -vn > imp[i]:
                                imp[i] = -vn
                j += 1
            wx, wz = hw, hz
        else:
            wx, wz = bx, bz
        for c in (0, 2):
            w = wx if c == 0 else wz
            if P[i, c] > w - RB:
                P[i, c] = w - RB
                if V[i, c] > 0:
                    V[i, c] = -V[i, c] * e_wall
            elif P[i, c] < -w + RB:
                P[i, c] = -w + RB
                if V[i, c] < 0:
                    V[i, c] = -V[i, c] * e_wall
        if P[i, 1] < yfl + RB:
            P[i, 1] = yfl + RB
            if V[i, 1] < 0:
                if -V[i, 1] > imp[i]:
                    imp[i] = -V[i, 1]
                V[i, 1] = -V[i, 1] * 0.2
            V[i, 0] *= 0.9
            V[i, 2] *= 0.9
    # ball–ball contacts: spatial hash, one pass
    cs = 2 * RB
    for k in range(head.shape[0]):
        head[k] = -1
    for i in range(n):
        if live[i] == 0:
            continue
        ix, iy, iz = math.floor(P[i, 0] / cs), math.floor(P[i, 1] / cs), math.floor(P[i, 2] / cs)
        key = ((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791)) & (TBL - 1)
        nxt[i] = head[key]
        head[key] = i
    d2 = cs * cs
    for i in range(n):
        if live[i] == 0:
            continue
        ix, iy, iz = math.floor(P[i, 0] / cs), math.floor(P[i, 1] / cs), math.floor(P[i, 2] / cs)
        for ax in range(ix - 1, ix + 2):
            for ay in range(iy - 1, iy + 2):
                for az in range(iz - 1, iz + 2):
                    key = ((ax * 73856093) ^ (ay * 19349663) ^ (az * 83492791)) & (TBL - 1)
                    j = head[key]
                    while j >= 0:
                        if j > i:
                            dx, dy, dz = P[j, 0] - P[i, 0], P[j, 1] - P[i, 1], P[j, 2] - P[i, 2]
                            q = dx * dx + dy * dy + dz * dz
                            if q < d2 and q > 1e-12:
                                d = math.sqrt(q)
                                nx, ny, nz = dx / d, dy / d, dz / d
                                push = (cs - d) * 0.5
                                P[i, 0] -= nx * push
                                P[i, 1] -= ny * push
                                P[i, 2] -= nz * push
                                P[j, 0] += nx * push
                                P[j, 1] += ny * push
                                P[j, 2] += nz * push
                                vn = (V[j, 0] - V[i, 0]) * nx + (V[j, 1] - V[i, 1]) * ny + (V[j, 2] - V[i, 2]) * nz
                                if vn < 0:
                                    J = -(1 + e_ball) * vn * 0.5
                                    V[i, 0] -= J * nx
                                    V[i, 1] -= J * ny
                                    V[i, 2] -= J * nz
                                    V[j, 0] += J * nx
                                    V[j, 1] += J * ny
                                    V[j, 2] += J * nz
                        j = nxt[j]


def _eff(op: int) -> float:
    return 0.0 if op == 0 else 0.5 if op == -2 else float(op)


def _label(op: int) -> str:
    return "×0" if op == 0 else "÷2" if op == -2 else f"×{op}"


class GateRush(Sim):
    kind = "gate_rush"
    concept = {
        "created": "2026-10-25T02:30:00+00:00",
        "idea": "One ball drops into a 3D glass shaft of peg rods and multiplier gates (×2, ×3, ×5 … and red ×0 / ÷2 "
                "traps): every ball that falls through a gate becomes that many balls, until thousands of glossy "
                "spheres rain into the box at the bottom. Can it fill the box to the goal? A numbered series: RUN #N, "
                "the goal grows by 500 balls every episode.",
        "inspiration": "the 'multiply the balls through x2 / x5 gates' mobile-game ads and ball-multiplier shorts "
                       "that are all over TikTok and Shorts, rebuilt as a real 3D sphere simulation in the style of "
                       "@particlesflow, plus our series formula (tower_drop ×9.8)",
        "finale": "the flood of thousands of balls fills the box past the gold goal line, the box bursts and every "
                  "ball fountains out (slow motion) – 'NEXT: RUN #N+1 · GOAL …' above the follow button",
    }
    titles = ["{onscreen}", "Run #{n}: can 1 ball become {k} balls?", "1 ball, {k} to go – run #{n}, watch the gates"]
    questions = ["Which gate should run #{n} get next time?", "How many balls do you think it really made?",
                 "Would you have taken the ×0 risk?"]
    body = ("Run #{n}: one ball falls through a glass shaft of peg rods and multiplier gates – every ball that falls "
            "through a ×3 gate turns into three. The goal: {k} balls in the box. The pegs play {song}, every gate "
            "chimes, and every episode the goal grows by 500 balls. Everything is simulated in 3D, nothing is "
            "animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.97
    trend_words = ("ball", "balls", "multiply", "gates", "3d", "simulation", "satisfying", "x2", "marble")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    tempo = "fast"
    experiment = "series"
    cta_y = 1560
    run_ranges = [(60, 76), (62, 80)]   # wide: practically every seed fits, so the run numbers count up

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.ep = self.n = seed + 1
        self.goal = self.K = min(5000, 2000 + 500 * (self.ep - 1))
        # the shaft, top to bottom: gate 0 right under the first ball, then rows of pegs and a gate, again and again
        y = -0.35
        rows_y, rows_off, gy = [], [], []
        for k in range(GATES):
            if k:
                y -= 0.2
                for r in range(ROWS[k]):
                    rows_y.append(y)
                    rows_off.append((PS / 2 if (len(rows_y) % 2) else 0.0) + rnd.uniform(-0.01, 0.01))
                    y -= RS
                y -= 0.05
            gy.append(y)
        vol = math.pi / 6 * (2 * RB) ** 3 / 0.6   # random close packing
        self.goal_h = self.goal * vol / (4 * BX * BZ)   # the gold goal line: where the pile reaches with `goal` balls
        self.ysb = y - 0.45                       # bottom of the shaft
        self.yfl = self.ysb - max(DROP, self.goal_h + 0.75)   # floor of the box
        self.ry = np.array(rows_y)
        self.nry = -self.ry                       # ascending, for the binary search
        self.roff = np.array(rows_off)
        self.gy = np.array(gy)
        self.layout: list[list[tuple[float, float, int]] | None] = [None] * GATES   # (x0, x1, op) per panel
        self.avg = np.ones(GATES)
        self.P = np.zeros((CAP, 3))
        self.V = np.zeros((CAP, 3))
        self.Pprev = self.P.copy()
        self.live = np.zeros(CAP, np.int8)
        self.last = np.full(CAP, -1, np.int32)    # last gate a ball fell through
        self.gen = np.zeros(CAP, np.int16)        # colour: which gate made it ...
        self.xg = np.zeros(CAP)                   # ... and where it fell through (clones keep it: stripes)
        self.imp = np.zeros(CAP)
        self.head = np.zeros(TBL, np.int64)
        self.nxt = np.zeros(CAP, np.int64)
        self.nb = 1
        self.P[0] = (rnd.uniform(-0.1, 0.1), 0.0, 0.0)
        self.V[0] = (rnd.uniform(-0.3, 0.3), -0.5, rnd.uniform(-0.1, 0.1))
        self.live[0] = 1
        self.alive = 1
        self.boxed = 0
        self.steps = 0
        self.last_note = self.last_tone = self.last_clack = -9.0
        self.half = np.zeros(GATES, np.int32)     # ÷2 panels kill every second ball
        self.opened = np.zeros(GATES, bool)
        self.seen = np.zeros(GATES)                # balls through each gate ...
        self.made = np.zeros(GATES)                # ... and the balls they turned into
        self.revealed = False                      # the last gate shows ×? until the front gets close
        self.pflash: dict[tuple[int, int], float] = {}
        self.debris: list[tuple[float, float, float, float, tuple]] = []   # (t, x, y, z, col): popped balls
        self.lead_y = 0.0
        self.cam_y = -0.6
        self.burst = False
        for k in range(2):
            self._plan(k)

    # ---------------------------------------------------------------- the gates

    def _target(self, k: int) -> float:
        """Planned number of balls after gate k: from 1 to 1.3 × goal along an exponential curve."""
        if k == GATES - 1:
            return self.goal * 1.3
        return (self.goal * 1.3 / 7) ** ((k + 1) / (GATES - 1))    # the mystery gate at the end does ~×7

    def _expected(self, k: int) -> float:
        """Expected number of balls after gate k-1, from where every live ball is now."""
        idx = np.flatnonzero(self.live[:self.nb])
        if not len(idx):
            return 0.0
        avg = np.where(self.seen[:k] >= 30, self.made[:k] / np.maximum(self.seen[:k], 1), self.avg[:k])
        cum = np.concatenate([[1.0], np.cumprod(avg)])     # cum[j] = product of avg[0..j-1]
        last = self.last[idx]
        f = cum[k] / cum[last + 1]
        return float(f.sum())

    def _plan(self, k: int) -> None:
        rnd = self.rnd
        est = max(1.0, self._expected(k))
        want = self._target(k) / est
        cands = []
        for _ in range(40):
            if k == 0:
                ops = [rnd.choice([3, 4])]
            elif k == GATES - 1:
                ops = [max(2, min(25, int(math.ceil(want))))]
            else:
                m = rnd.choice([2, 2, 3, 3])
                pool = [2, 3, 4, 5, 10] if est < 40 else [0, -2, 2, 3, 4, 5, 10]
                ops = [rnd.choice(pool) for _ in range(m)]
                if est < 40:
                    ops = [o for o in ops if o > 0] or [2]
            cuts = sorted(rnd.uniform(-HW + 0.3, HW - 0.3) for _ in range(len(ops) - 1))
            xs = [-HW] + cuts + [HW]
            if any(b - a < 0.36 for a, b in zip(xs, xs[1:])):
                continue
            avg = sum((b - a) / (2 * HW) * _eff(o) for a, b, o in zip(xs, xs[1:], ops))
            if avg <= 0.3:
                continue
            cands.append((abs(math.log(avg / want)), [(a, b, o) for a, b, o in zip(xs, xs[1:], ops)], avg))
        cands.sort(key=lambda c: c[0])
        _, lay, avg = cands[min(len(cands) - 1, rnd.randrange(2))]
        self.layout[k], self.avg[k] = lay, avg

    # ---------------------------------------------------------------- physics

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        if self.steps % PHYS:
            return
        h = PHYS * dt
        n = self.nb
        self.Pprev[:n] = self.P[:n]
        bx, bz = (60.0, 60.0) if self.burst else (BX, BZ)
        _phys(self.P, self.V, self.live, n, h, GRAV, self.nry, self.roff, self.ysb, self.yfl, HW, HZ, bx, bz,
              self.imp, self.head, self.nxt)
        if self.end is None:
            self._gates()
            self._sound()
            self._count()
        if self.debris:
            self.debris = [d for d in self.debris if self.t - d[0] < 0.6]

    def _gates(self) -> None:
        if not self.revealed and self.lead_y < self.gy[-1] + 1.0:
            self.revealed = True                   # the mystery gate: its number is set now, from the real swarm
            self._plan(GATES - 1)
            self.events.append((self.t, "break", GATES - 1))
            self.pflash[(GATES - 1, 0)] = self.t
        n = self.nb
        idx = np.flatnonzero(self.live[:n])
        nxt_g = self.last[idx] + 1
        ok = nxt_g < GATES
        idx, nxt_g = idx[ok], nxt_g[ok]
        cross = self.P[idx, 1] < self.gy[nxt_g]
        rnd = self.rnd
        for i, k in zip(idx[cross], nxt_g[cross]):
            k = int(k)
            if self.layout[k] is None:
                self._plan(k)
            x = self.P[i, 0]
            j = next((jj for jj, (a, b, _) in enumerate(self.layout[k]) if x < b), len(self.layout[k]) - 1)
            op = self.layout[k][j][2]
            self.last[i] = k
            self.gen[i] = k + 1
            self.xg[i] = x
            self.seen[k] += 1
            self.pflash[(k, j)] = self.t
            if not self.opened[k]:
                self.opened[k] = True
                self.events.append((self.t, "break", k))
                for kk in (k + 1, k + 2):           # plan the gates the camera will show next
                    if kk < GATES and self.layout[kk] is None:
                        self._plan(kk)
            if self.t - self.last_tone > 0.11:
                self.last_tone = self.t
                self.events.append((self.t, "tone", min(14, 4 + max(op, 0) + (0 if op else 0))))
            kill = op == 0
            if op == -2:
                self.half[k] += 1
                kill = self.half[k] % 2 == 0
            self.made[k] += 0 if kill else max(op, 1)
            if kill:
                self.live[i] = 0
                self.alive -= 1
                self.debris.append((self.t, *self.P[i], RED if op == 0 else ORANGE))
                continue
            for _ in range(max(0, op - 1)):
                if self.nb >= CAP:
                    break
                c = self.nb
                self.nb += 1
                self.P[c] = self.P[i] + (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.03, 0.0), rnd.uniform(-0.08, 0.08))
                self.Pprev[c] = self.P[c]
                self.V[c] = self.V[i] * 0.7 + (rnd.uniform(-0.7, 0.7), rnd.uniform(-0.3, 0.1), rnd.uniform(-0.4, 0.4))
                self.live[c], self.last[c], self.gen[c], self.xg[c] = 1, k, k + 1, x
                self.alive += 1

    def _sound(self) -> None:
        """Melody on peg hits the camera shows (at most ~9 per second), clacks for the rest and the landings."""
        n = self.nb
        idx = np.flatnonzero((self.imp[:n] > 0.45) & (self.live[:n] == 1))
        if not len(idx):
            return
        y = self.P[idx, 1]
        seen = idx[np.abs(y - self.cam_y) < 0.9]
        peg = seen[self.P[seen, 1] > self.ysb]
        if len(peg) and self.t - self.last_note > 0.11:
            self.last_note = self.t
            i = int(peg[np.argmax(self.imp[peg])])
            self.events.append((self.t, "bounce", i))
            self.hero = i
        elif len(seen) and self.t - self.last_clack > 0.09 and self.t - self.last_note > 0.04:
            self.last_clack = self.t
            self.events.append((self.t, "clack", int(seen[0])))

    def _count(self) -> None:
        n = self.nb
        live = self.live[:n] == 1
        y = self.P[:n, 1]
        inbox = live & (y < self.ysb - 0.4)
        self.boxed = int(inbox.sum())
        shaft = live & (y > self.ysb - 0.4)
        if shaft.any():
            ys = y[shaft]
            self.lead_y = float(ys.min())
            front = float(np.quantile(ys, 0.08)) if len(ys) > 12 else self.lead_y
            goal = max(front + 0.35, self.yfl + 0.5 * self.goal_h + 0.45)
            if self.boxed > 20:                    # the flood reached the box: watch it fill up
                goal = self.yfl + 0.5 * self.goal_h + 0.45
        else:
            goal = self.yfl + 0.5 * self.goal_h + 0.45
        self.cam_y += (goal - self.cam_y) * (1 - math.exp(-PHYS / 720 * 3.5))
        if self.boxed >= self.goal:
            self.events.append((self.t, "break", GATES))
            self.finish()
            self._explode()
        elif self.alive == 0 or (not shaft.any() and self.boxed < self.goal and self.t > 5):
            self.finish()          # out of balls: a failed run (good() rejects it)

    def _explode(self) -> None:
        self.burst = True
        n = self.nb
        rnd = self.rnd
        idx = np.flatnonzero((self.live[:n] == 1) & (self.P[:n, 1] < self.ysb - 0.4))
        m = len(idx)
        if not m:
            return
        ang = np.array([rnd.uniform(0, 2 * math.pi) for _ in range(m)])
        sp = np.array([rnd.uniform(0.6, 2.4) for _ in range(m)])
        up = np.array([rnd.uniform(2.5, 6.0) for _ in range(m)])
        hgt = (self.P[idx, 1] - self.yfl) / max(self.goal_h, 0.1)
        self.V[idx, 0] += np.cos(ang) * sp
        self.V[idx, 2] += np.sin(ang) * sp
        self.V[idx, 1] += up * (0.6 + 0.6 * np.clip(hgt, 0, 1.5))

    def good(self) -> bool:
        return self.boxed >= self.goal

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        look = self.look.rnd
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 18)])
        h0, turn = look.uniform(0, 1), look.choice([-1, 1])
        self.hue = [_rgb(h0 + turn * j / 30, 0.72, 1.0) for j in range(30)]
        self.bg = self._background()
        self._spr: dict = {}
        self.fonts = {s: _font("Poppins-ExtraBold.ttf", s) for s in range(24, 121, 8)}

    def _background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        cx, cy = W / 8, H / 8 * 1.05
        glow = np.exp(-(((xx - cx) / (W / 4 * 0.6)) ** 2 + ((yy - cy) / (H / 4 * 0.38)) ** 2))
        arr = np.array(self.tint, np.float32)[None, None, :] * (0.5 + 1.1 * glow)[..., None]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _cam(self) -> sim3d.Camera:
        out = 0.0 if self.end is None else min(1.0, (self.t - self.end) / 1.5)
        return sim3d.Camera(target=(0, self.cam_y + 0.4 * out, 0), dist=4.1 + 1.8 * out, yaw=0.32, pitch=0.24,
                            fov=34, cy=H * 0.52)

    @staticmethod
    def _op_col(op: int) -> tuple:
        if op == 0:
            return RED
        if op == -2:
            return ORANGE
        return [(80, 230, 140), (70, 220, 200), (80, 200, 255), (140, 150, 255), (255, 214, 64)][
            min(4, [2, 3, 4, 5, 10].index(op) if op in (2, 3, 4, 5, 10) else 4)]

    def render(self, p):
        cam = self._cam()
        img = self.bg.copy()
        t = self.t
        lo, hi = self.cam_y - 2.2, self.cam_y + 2.0
        over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(over)
        goal_lbl = None
        # the box: a glass floor, the gold goal line and glowing edges
        if self.yfl + self.goal_h + 1.4 > lo:
            a, b, f = BX, BZ, self.yfl
            q = lambda pts: [cam.point(pp) for pp in pts]      # noqa: E731
            od.polygon(q([(-a, f, -b), (a, f, -b), (a, f, b), (-a, f, b)]), fill=(70, 74, 96, 150))
            if not self.burst:
                for (x0, z0), (x1, z1) in (((-a, -b), (a, -b)), ((-a, -b), (-a, b)), ((a, -b), (a, b))):
                    od.polygon(q([(x0, f, z0), (x1, f, z1), (x1, f + max(0.9, self.goal_h + 0.25), z1), (x0, f + max(0.9, self.goal_h + 0.25), z0)]),
                               fill=(120, 140, 200, 26))
                gl = f + self.goal_h
                full = self.boxed >= self.goal
                gc = GOLD if full or int(t * 3) % 2 == 0 else (190, 150, 40)
                top = f + max(0.9, self.goal_h + 0.25)
                edges = [q([(x, f, z), (x, top, z)]) for x in (-a, a) for z in (-b, b)]
                edges += [q([(-a, top, b), (a, top, b), (a, top, -b), (-a, top, -b), (-a, top, b)])]
                goal_lbl = (q([(-a, gl, b), (a, gl, b), (a, gl, -b), (-a, gl, -b), (-a, gl, b)]),
                            cam.point((a - 0.04, gl + 0.03, b)), gc, edges)
        # the gates: glass slabs split into panels
        labels = []
        for k in range(GATES):
            y = self.gy[k]
            if not (lo - 0.3 < y < hi + 0.3) or self.layout[k] is None:
                continue
            for j, (x0, x1, op) in enumerate(self.layout[k]):
                col = self._op_col(op) if k < GATES - 1 or self.revealed else (255, 214, 64)
                fl = max(0.0, 1 - (t - self.pflash.get((k, j), -9)) / 0.25)
                al = int(70 + 120 * fl)
                c2 = tuple(int(c + (255 - c) * fl * 0.6) for c in col)
                pts = [cam.point(pp) for pp in [(x0 + 0.01, y, -HZ), (x1 - 0.01, y, -HZ), (x1 - 0.01, y, HZ),
                                                 (x0 + 0.01, y, HZ)]]
                od.polygon(pts, fill=c2 + (al,))
                fr = [cam.point(pp) for pp in [(x0 + 0.01, y, HZ), (x1 - 0.01, y, HZ), (x1 - 0.01, y - 0.05, HZ),
                                                (x0 + 0.01, y - 0.05, HZ)]]
                od.polygon(fr, fill=c2 + (230,))
                text = _label(op) if k < GATES - 1 or self.revealed else "×?"
                labels.append((cam.point(((x0 + x1) / 2, y + 0.08, HZ)), text, c2, x1 - x0))
        img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
        # spheres: balls, peg rods (beads along z), corner rails
        a = (self.steps % PHYS) / PHYS
        n = self.nb
        live = np.flatnonzero(self.live[:n])
        Pb = self.Pprev[live] + (self.P[live] - self.Pprev[live]) * a
        keep = (Pb[:, 1] > lo) & (Pb[:, 1] < hi)
        live, Pb = live[keep], Pb[keep]
        pts, rad, cols = [Pb], [np.full(len(live), RB)], []
        hb = (np.clip((self.xg[live] + HW) / (2 * HW), 0, 0.999) * 12 + self.gen[live] * 1.7).astype(int) % 30
        cols += [self.hue[j] if g else (255, 255, 255) for j, g in zip(hb, self.gen[live])]
        rsel = np.flatnonzero((self.ry > lo) & (self.ry < hi))
        zs = np.array([-HZ + RP, 0.0, HZ - RP])
        for r in rsel:
            off = self.roff[r]
            xs = off + PS * np.arange(-6, 7)
            xs = np.concatenate([xs[np.abs(xs) <= HW - RP - 0.1], [-(HW - RP), HW - RP]])
            X, Z = np.meshgrid(xs, zs)
            pts.append(np.stack([X.ravel(), np.full(X.size, self.ry[r]), Z.ravel()], 1))
            rad.append(np.full(X.size, RP))
            cols += [(62, 66, 84)] * X.size
        ys = np.arange(math.floor(lo / 0.07) * 0.07, min(hi, 0.3), 0.07)
        ys = ys[ys > self.ysb]
        for cx_, cz_ in ((-HW, -HZ), (HW, -HZ), (-HW, HZ), (HW, HZ)):
            pts.append(np.stack([np.full(len(ys), cx_), ys, np.full(len(ys), cz_)], 1))
            rad.append(np.full(len(ys), 0.022))
            cols += [(70, 74, 92)] * len(ys)
        P = np.vstack(pts)
        R = np.concatenate(rad)
        x, y, z, s = cam.project(P)
        rp = np.maximum(1, np.rint(R * s)).astype(int)
        ok = (y > -60) & (y < H + 60) & (x > -60) & (x < W + 60) & (z > 1.5)
        order = np.argsort(-z)
        for j in order:
            if not ok[j]:
                continue
            r = int(rp[j])
            spr = self._sprite(cols[j], r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        # popped balls: little red sparks; gate labels on top
        d = ImageDraw.Draw(img)
        for (t0, px, py, pz, col) in self.debris:
            age = t - t0
            sx, sy = cam.point((px, py - 0.5 * age * age, pz))
            rr = 26 * (1 + 2.5 * age)
            d.ellipse((sx - rr, sy - rr, sx + rr, sy + rr), outline=col, width=max(1, int(6 * (1 - age / 0.6))))
        for (sx, sy), text, col, w in labels if self.end is None else []:
            if sy < 500:                           # never on top of the title
                continue
            _, _, _, sc = cam.project(np.array([[0, self.cam_y, HZ]]))
            size = int(np.clip(float(sc[0]) * min(0.16, w * 0.3), 24, 120))
            f = self.fonts[min(self.fonts, key=lambda v: abs(v - size))]
            tw = d.textlength(text, font=f)
            d.text((sx - tw / 2, sy - size * 0.75), text, font=f, fill=(255, 255, 255), stroke_width=4,
                   stroke_fill=tuple(int(c * 0.35) for c in col))
        if goal_lbl is not None:
            line, (gx, gy_), gc, edges = goal_lbl
            for e in edges:
                d.line(e, fill=(150, 165, 210), width=3)
            d.line(line, fill=gc, width=8)
            f = self.fonts[40]
            tw = d.textlength("GOAL", font=f)
            d.text((gx - tw, gy_ - 52), "GOAL", font=f, fill=gc, stroke_width=3, stroke_fill=(40, 30, 0))
        if self.end is not None:
            glow = Image.new("RGB", (W // 4, H // 4))
            gd = ImageDraw.Draw(glow)
            age = t - self.end
            gx, gy = cam.point((0, self.yfl + self.goal_h * 0.6, 0))
            rr = (120 + 300 * age) / 4
            v = max(0.0, 1 - age / 2.5)
            gd.ellipse((gx / 4 - rr, gy / 4 - rr, gx / 4 + rr, gy / 4 + rr), fill=(int(150 * v), int(110 * v), int(30 * v)))
            img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR))
        return img

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break" and i < GATES:
            p.punch(0.18 + 0.03 * i)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)
        if self.t - self.end > 0.6:
            p.centered(d, 600, f"NEXT: RUN #{self.ep + 1} · GOAL {min(5000, self.goal + 500):,}", p.f_count,
                       (255, 214, 120), 2)

    def title(self) -> list[str]:
        return ["Can 1 ball become", f"{self.goal:,} balls?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"RUN #{self.ep} · {self.alive:,} BALLS"
        if self.boxed:
            return f"{self.alive:,} balls · box {self.boxed:,}/{self.goal:,}"
        return f"RUN #{self.ep} · {self.alive:,} ball" + ("s" if self.alive != 1 else "")

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"RUN #{self.ep}", (255, 255, 255)), ("JACKPOT!", GOLD)]
