"""Zombie tag: forty coloured balls and one green zombie ball in a closing arena. Every survivor the zombie touches
turns into a zombie too, the horde hunts the nearest survivor and the arena shrinks second by second. Survive until
the clock hits zero – or the last survivor gets caught."""
from __future__ import annotations

import colorsys
import math

import numpy as np

from ..sims import TAU, Painter, Sim, _mix

WHITE = (255, 255, 255)
GOLD = (255, 210, 90)
ZOMBIE = (120, 255, 90)
ZDARK = (40, 120, 30)
RING = (255, 140, 40)
RB = 14.0
N = 40
TICK = 6            # physics runs every 6th step (120 Hz) – fast enough at these speeds, cheap enough to search seeds
R0, R1 = 470.0, 165.0
FINAL = 8.0         # the last seconds: the whole horde hunts
TURN = 1.5          # seconds a bitten ball needs to turn into a hunting zombie


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


class ZombieTag(Sim):
    kind = "zombie_tag"
    concept = {
        "created": "2026-10-18T08:40:00+00:00",
        "idea": "Forty balls and one zombie ball in a shrinking arena: every ball the zombie touches turns into a "
                "zombie, the horde hunts the nearest survivor while the survivors flee – survive the countdown or "
                "the last one gets caught.",
        "inspiration": "viral 'red ball vs. blue ball – catch it before the timer runs out' chase shorts and the "
                       "'last ball standing' elimination trend, turned into a Halloween infection outbreak",
        "finale": "the arena keeps closing, the horde gets faster and the final 10 seconds count down; either the "
                  "last survivor is caught (slow motion, green explosion) or the clock hits zero and the survivors "
                  "blast the horde away in a golden shockwave",
    }
    titles = ["{onscreen}", "1 zombie vs. 40 balls – every touch infects",
              "The arena shrinks every second – who survives the zombie outbreak?"]
    questions = ["Team zombie or team survivor? 🧟", "Which colour did you root for – did it make it?",
                 "How many survive? Guess before the end!"]
    body = ("One green zombie ball, forty survivors, a shrinking arena. Every touch turns a survivor into a zombie "
            "(each one rings a higher note), every bounce off the wall plays the next note of {song}. The horde hunts "
            "the nearest survivor – can anyone last until the clock runs out?")
    playlist = ("Zombie outbreak", "One touch and you're one of them.")
    cover_at = 0.8
    trend_words = ("zombie", "survive", "halloween", "last ball standing", "chase", "ball", "simulation")
    slowmo = True
    finale_punch = 1.6
    note_gap = 0.11

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.T = float(rnd.choice((60, 64, 68, 72, 76)))   # survive this long
        self.vs = rnd.uniform(250, 275)                      # survivor speed
        self.flee = rnd.uniform(150, 190)                    # survivors notice a zombie this close
        self.pace = rnd.uniform(0.8, 1.0)                    # shape of the even pace the horde keeps up with
        self.sprint = rnd.uniform(0.84, 0.94)
        self.left_at_end = rnd.uniform(0.6, 2.2)            # the pace aims at about this many survivors at zero                # horde speed in the final hunt
        self.gain = rnd.uniform(2.5, 3.5)                    # how strongly it speeds up when it falls behind
        self.dodge = rnd.uniform(3.0, 4.0)                   # how hard survivors swerve away from danger                  # how much faster the horde gets towards the end
        x, y = [], []
        while len(x) < N:                                    # survivors spread over the arena, none near the centre
            a, r = rnd.uniform(0, TAU), math.sqrt(rnd.uniform(0.12, 0.85)) * (R0 - 30)
            px, py = math.cos(a) * r, math.sin(a) * r
            if all((px - qx) ** 2 + (py - qy) ** 2 > (2.6 * RB) ** 2 for qx, qy in zip(x, y)):
                x.append(px)
                y.append(py)
        x.append(0.0)
        y.append(0.0)
        self.x, self.y = np.array(x), np.array(y)
        ang = np.array([rnd.uniform(0, TAU) for _ in range(N + 1)])
        self.vx, self.vy = np.cos(ang) * self.vs, np.sin(ang) * self.vs
        self.z = np.zeros(N + 1, bool)
        self.z[N] = True
        self.bit_at = np.full(N + 1, -9.0)                    # when each ball turned
        self.bit_at[N] = 0.0
        hues = (0.0, 0.04, 0.08, 0.13, 0.55, 0.6, 0.66, 0.74, 0.8, 0.86, 0.92, 0.97)
        off = self.look.rnd.uniform(-0.015, 0.015)
        self.cols = [_hsv(hues[i % len(hues)] + off, 0.55 + 0.35 * ((i * 7) % 5) / 4, 1.0) for i in range(N)]
        self.cols.append(ZOMBIE)                             # survivors: every colour but green – green is the horde
        self.n_step = 0
        self.wall_hits = 0
        self.last_bite = -9.0
        self.last_xy = (0.0, 0.0)
        self.won = False

    # ------------------------------------------------------------------ physics
    def radius(self, t: float | None = None) -> float:
        u = min(1.0, (self.t if t is None else t) / self.T)
        return R0 - (R0 - R1) * u

    def vz(self) -> float:
        """The horde is hungrier the further it lags behind an even pace (one survivor every T/N seconds) – so
        something happens every few seconds and the last survivors are hunted down right at the end."""
        u = min(1.0, self.t / self.T)
        lag = (self.survivors() - self.target()) / N
        if self.final():                                    # the final hunt: almost as fast as the survivors
            return self.vs * max(self.sprint, min(1.3, 0.95 + self.gain * lag))
        return self.vs * min(1.3, max(0.25, 0.5 + 0.45 * u + self.gain * lag))

    def target(self) -> float:
        u = min(1.0, self.t / self.T)
        return self.left_at_end + (N - self.left_at_end) * (1 - u) ** self.pace

    def hunting(self) -> bool:
        """Ahead of the pace the horde stops hunting and just shambles around."""
        u = min(1.0, self.t / self.T)
        return self.survivors() > self.target() - 1.0

    def final(self) -> bool:
        return self.T - self.t <= FINAL

    def survivors(self) -> int:
        return int(N + 1 - self.z.sum())

    def step(self, dt: float) -> None:
        self.t += dt
        self.n_step += 1
        if self.n_step % TICK:
            return
        h = dt * TICK
        if self.end is not None:                             # outro: everybody coasts and slows down
            self.x += self.vx * h
            self.y += self.vy * h
            self.vx *= 0.985
            self.vy *= 0.985
            return
        x, y, z = self.x, self.y, self.z
        dx = x[None, :] - x[:, None]                         # dx[i, j] = x_j - x_i
        dy = y[None, :] - y[:, None]
        d2 = dx * dx + dy * dy
        np.fill_diagonal(d2, 1e12)
        s = ~z
        act = z & (self.t - self.bit_at > TURN)              # freshly bitten balls need a moment to turn
        # zombies chase the nearest survivor, survivors run from the nearest zombie
        if s.any() and z.any():
            dz = np.where(s[None, :], d2, 1e12)              # distance to survivors only
            tgt = dz.argmin(axis=1)
            idx = np.arange(N + 1)
            ux, uy = dx[idx, tgt], dy[idx, tgt]
            n = np.sqrt(ux * ux + uy * uy) + 1e-9
            vz = self.vz()
            k = min(1.0, 2.4 * h)
            if not self.hunting():                           # shambling: the horde gathers in the middle
                ux, uy = -x - self.vy * 0.8, -y + self.vx * 0.8
                n = np.sqrt(ux * ux + uy * uy) + 1e-9
                k *= 0.5
            self.vx[act] += (ux[act] / n[act] * vz - self.vx[act]) * k
            self.vy[act] += (uy[act] / n[act] * vz - self.vy[act]) * k
            # survivors: away from every hunting zombie close by (closer = stronger) and away from the wall
            d = np.sqrt(d2)
            thr = np.where(act[None, :] & (d < self.flee), (1 - d / self.flee) ** 2 / (d + 1e-9), 0.0)
            ax = -(thr * dx).sum(axis=1)
            ay = -(thr * dy).sum(axis=1)
            r = np.sqrt(x * x + y * y) + 1e-9
            wall = np.clip((r - (self.radius() - 110)) / 110, 0, 1) ** 2
            ax -= x / r * wall * 1.4
            ay -= y / r * wall * 1.4
            am = np.sqrt(ax * ax + ay * ay)
            run = s & (am > 1e-6)
            if run.any():
                sp = np.sqrt(self.vx[run] ** 2 + self.vy[run] ** 2) + 1e-9
                gx = self.vx[run] / sp + ax[run] * self.dodge
                gy = self.vy[run] / sp + ay[run] * self.dodge
                gm = np.sqrt(gx * gx + gy * gy) + 1e-9
                k = min(1.0, 6.0 * h)
                self.vx[run] += (gx / gm * self.vs - self.vx[run]) * k
                self.vy[run] += (gy / gm * self.vs - self.vy[run]) * k
        # constant speed for everybody
        sp = np.sqrt(self.vx ** 2 + self.vy ** 2) + 1e-9
        want = np.where(act, self.vz() if self.hunting() else self.vs * 0.25, np.where(z, 40.0, self.vs))
        self.vx *= want / sp
        self.vy *= want / sp
        x += self.vx * h
        y += self.vy * h
        # bites: a zombie touching a survivor turns it
        hit = (d2 < (2 * RB) ** 2)
        bitten = s & (hit & act[:, None]).any(axis=0) if self.hunting() else np.zeros(N + 1, bool)
        for j in np.nonzero(bitten)[0]:
            z[j] = True
            self.bit_at[j] = self.t
            self.last_bite = self.t
            self.last_xy = (float(x[j]), float(y[j]))
            self.events.append((self.t, "tone", min(39, 6 + int(z.sum()) // 2)))
            self.events.append((self.t, "break", int(j)))
        # same-team balls push each other apart (soft), so the horde stays a crowd of separate balls
        ii, jj = np.nonzero(np.triu(hit & ~bitten[:, None] & ~bitten[None, :], 1))
        if len(ii):
            ddx, ddy = dx[ii, jj], dy[ii, jj]
            dd = np.sqrt(ddx * ddx + ddy * ddy) + 1e-9
            push = (2 * RB - dd) / 2 / dd
            np.add.at(x, ii, -ddx * push)
            np.add.at(y, ii, -ddy * push)
            np.add.at(x, jj, ddx * push)
            np.add.at(y, jj, ddy * push)
        # the closing wall
        R = self.radius() - RB
        r = np.sqrt(x * x + y * y) + 1e-9
        out = r > R
        if out.any():
            nx, ny = x[out] / r[out], y[out] / r[out]
            x[out], y[out] = nx * R, ny * R
            vn = self.vx[out] * nx + self.vy[out] * ny
            back = vn > 0
            self.vx[out] -= np.where(back, 2 * vn * nx, 0)
            self.vy[out] -= np.where(back, 2 * vn * ny, 0)
            if back.any():
                self.wall_hits += 1
                self.events.append((self.t, "bounce", self.wall_hits))
        left = self.survivors()
        if left == 0:
            self.finish()
        elif self.t >= self.T:
            self.won = True
            self.finish()

    def good(self) -> bool:
        return self.end is not None and (self.won and self.survivors() <= 4 or not self.won and self.end > self.T - 14)

    # ------------------------------------------------------------------ picture
    def ring_color(self) -> tuple[int, int, int]:
        u = min(1.0, self.t / self.T)
        return (255, int(150 - 110 * u), int(40 + 20 * u))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            x, y = float(self.x[i]), float(self.y[i])
            p.parts.burst_point(p.rng, x, y, self.cols[i], 18, 260)
            p.parts.burst_point(p.rng, x, y, ZOMBIE, 10, 180)
            left = self.survivors()
            if left <= 5 or left % 10 == 0:
                p.punch(0.25 + 0.1 * max(0, 6 - left))
        elif kind == "finale":
            R = self.radius()
            if self.won:
                for c in (GOLD, WHITE, GOLD):
                    p.parts.burst_ring(p.rng, R, 0, TAU, c, 240)
                for j in np.nonzero(~self.z)[0]:
                    p.parts.burst_point(p.rng, float(self.x[j]), float(self.y[j]), GOLD, 80, 700)
                # the survivors' shockwave blows the horde outwards
                self.vx += self.x * 3.0
                self.vy += self.y * 3.0
            else:
                lx, ly = self.last_xy
                p.parts.burst_point(p.rng, lx, ly, ZOMBIE, 160, 800)
                p.parts.burst_ring(p.rng, R, 0, TAU, ZOMBIE, 260)

    def draw(self, p: Painter) -> None:
        t = self.t
        R = self.radius(min(t, self.end) if self.end is not None else t)
        final = self.end is None and self.T - t <= FINAL
        pulse = 0.5 + 0.5 * math.sin(t * (14 if final else 5))
        p.ring(R + 8, 0, 360, self.ring_color(), 12, (0.35 * pulse) if final else 0.0)
        p.ring(R0 + 8, 0, 360, _mix(RING, 0.18), 3, 0.0)        # where the arena started
        p.particles()
        z = self.z
        last = self.survivors() <= 5
        for j in range(N + 1):
            x, y = float(self.x[j]), float(self.y[j])
            if z[j]:
                fresh = max(0.0, 1 - (t - self.bit_at[j]) / 0.5)
                p.glow_disc(x, y, RB * (2.2 + 1.6 * fresh), _mix(ZOMBIE, 0.4 if last else 0.55))
                p.ball(x, y, RB, ZDARK, _mix(ZOMBIE, 0.75) if last and fresh < 0.5 else
                       (ZOMBIE if fresh < 0.5 else WHITE), 3)
            else:
                col = self.cols[j]
                rb = RB * 1.35 if last else RB              # the last few stand out from the horde
                p.trail(j, x, y, rb, GOLD if last else col, 12 if last else 10)
                if last:
                    p.glow_disc(x, y, rb * (2.8 + 0.8 * pulse), _mix(GOLD, 0.85))
                p.ball(x, y, rb, col, WHITE, 4 if last else 3)

    def title(self) -> list[str]:
        return ["Can anyone survive", f"{int(self.T)} seconds?"]

    def counter(self) -> str:
        left = self.survivors()
        if self.end is not None:
            return f"{left} survivor{'s' if left != 1 else ''} · {N + 1 - left} zombies"
        rest = max(0.0, self.T - self.t)
        if left == 1:
            return f"LAST SURVIVOR! · {rest:.1f}s"
        if rest <= FINAL:
            return f"FINAL {math.ceil(rest)} SECONDS · {left} left"
        return f"{left} survivors · {int(math.ceil(rest))}s left"

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return GOLD if self.survivors() > 3 else (255, 90, 70)

    def finale(self) -> list[tuple[str, tuple]]:
        left = self.survivors()
        if self.won:
            return [(f"{left} SURVIVED!" if left > 1 else "1 SURVIVED!", GOLD), ("the horde loses", WHITE)]
        return [("NOBODY SURVIVED", ZOMBIE), (f"caught at {self.end:.0f}s of {self.T:.0f}", WHITE)]
