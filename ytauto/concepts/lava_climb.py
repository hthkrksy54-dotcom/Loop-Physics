"""Lava climb: five coloured balls jump from platform to platform up an endless tower while lava rises below them.
Every landing launches the ball towards a platform above – a near miss means falling back down. The lava gets faster
every second and swallows whoever falls behind; the first ball through the golden exit at the top escapes."""
from __future__ import annotations

import math

from ..sims import CX, CY, SS, TAU, TEAMS, W, Painter, Sim, _mix

WHITE = (255, 255, 255)
GOLD = (255, 210, 90)
LAVA = (235, 70, 18)
LAVA_TOP = (255, 190, 60)
TICK = 3            # physics every 3rd step (240 Hz) – landings are found by crossing, so nothing tunnels
G = 1900.0
RB = 17.0
HW = 490.0          # the tower walls
FINAL_ROWS = 10     # the last floors: final sprint, the lava surges


class LavaClimb(Sim):
    kind = "lava_climb"
    concept = {
        "created": "2026-10-19T13:20:00+00:00",
        "idea": "Five coloured balls jump from platform to platform up a tall tower while lava rises from below: "
                "every landing launches the ball at a platform above, a miss means falling back down, the lava "
                "speeds up and swallows whoever falls behind – the first ball through the golden exit escapes.",
        "inspiration": "viral 'which ball escapes / last ball standing' elimination shorts and the 'floor is lava' "
                       "climbing clips (Doodle-Jump style ball races), turned into a Halloween-season lava race",
        "finale": "the final 10 floors: the platforms get narrow, the lava surges right behind the leader; the "
                  "winner bursts through the golden exit (slow motion, gold explosion) and the lava floods the "
                  "whole tower below",
    }
    titles = ["{onscreen}", "5 balls, 1 exit – the lava never stops rising",
              "The floor is lava – which colour makes it to the top?"]
    questions = ["Which colour did you pick at the start? 🔥", "Who got burned first – did you see it coming?",
                 "Would your colour have made it?"]
    body = ("Five balls race up a tower of platforms while the lava rises below them – and it gets faster every "
            "second. Every landing plays the next note of {song}, every ball the lava catches is out. Only the first "
            "one through the golden exit at the top escapes.")
    playlist = ("Floor is lava", "Climb or burn – only one escapes.")
    cover_at = 0.85
    trend_words = ("lava", "escape", "floor is lava", "last ball standing", "race", "ball", "simulation")
    slowmo = True
    finale_punch = 1.5
    note_gap = 0.1

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.dy = rnd.uniform(108, 122)                        # floor height
        self.rows = rnd.randint(145, 200)                        # floors to the exit
        self.J = math.sqrt(2 * G * 2.35 * self.dy)              # jump speed: reaches two floors up
        self.creep = rnd.uniform(35, 45)                         # the lava always rises at least this fast ...
        self.close = rnd.uniform(38, 52)                         # ... and closes in on the last ball this fast
        self.D = 480.0                                           # how far below the last ball the lava lurks
        self.y0 = 300.0                                         # the ground floor
        n = 5
        teams = rnd.sample(range(len(TEAMS)), n)
        self.names = [TEAMS[c][0] for c in teams]
        self.cols = [TEAMS[c][1] for c in teams]
        self.x = [-360 + 720 * i / (n - 1) for i in range(n)]
        self.y = [self.y0 - RB] * n
        self.vx = [0.0] * n
        self.vy = [-self.J * rnd.uniform(0.3, 0.9) for _ in range(n)]
        self.jump = [rnd.uniform(0.97, 1.03) for _ in range(n)]   # each ball jumps a little differently
        self.aim = [rnd.uniform(12, 30) for _ in range(n)]        # how sloppy it aims
        self.greed = [rnd.uniform(0.45, 0.8) for _ in range(n)]   # how often it goes for two floors at once
        self.alive = [True] * n
        self.floor = [0] * n                                       # floor of the last landing
        self.best = [0] * n
        self.dead_at: list[tuple[float, int]] = []
        # platforms: [x, half width, kind ("n" normal, "s" spring, "c" crumbles), alive, last hit]
        self.plat: list[list[list]] = [[[0.0, HW, "n", True, -9.0]]]
        for r in range(1, self.rows):
            u = r / self.rows
            k = 1 if rnd.random() < 0.5 + 0.3 * u else 2
            row = []
            for _ in range(k):
                for _try in range(12):
                    hw = rnd.uniform(70, 125) * (1 - 0.25 * u)
                    x = rnd.uniform(-HW + hw + 10, HW - hw - 10)
                    if all(abs(x - q[0]) > hw + q[1] + 60 for q in row):
                        break
                kind = "n"
                if r > 4 and rnd.random() < 0.06:
                    kind = "s"
                elif r > 6 and k == 2 and rnd.random() < 0.3:  # crumbling only next to a solid one
                    kind = "c"
                row.append([x, hw, kind, True, -9.0])
            self.plat.append(row)
        self.plat.append([[0.0, HW, "e", True, -9.0]])          # the exit
        self.lava = self.y0 + 420.0
        self.winner = -1
        self.n_step = 0
        self.landings = 0
        self.cam, self.zoom = self.y0 - 150, 1.0
        self.last_out = (-9.0, 0)

    # ------------------------------------------------------------------ physics
    def top(self, r: int) -> float:
        return self.y0 - r * self.dy

    def leader(self) -> int:
        if self.winner >= 0:
            return self.winner
        live = [j for j in range(len(self.x)) if self.alive[j]] or list(range(len(self.x)))
        return min(live, key=lambda j: self.y[j])

    def final(self) -> bool:
        return self.best[self.leader()] >= self.rows - FINAL_ROWS

    def _launch(self, j: int, r: int, spring: bool) -> None:
        rnd = self.rnd
        behind = (self.y[j] - self.y[self.leader()]) / self.dy    # floors behind the leader: catches up a bit
        J = self.J * self.jump[j] * (1.38 if spring else 1.0) * (1 + 0.035 * max(0.0, min(5.0, behind - 2)))
        self.vy[j] = -J
        reach = J * J / (2 * G) * 0.93
        cands = []
        for rr in range(r + 1, min(len(self.plat), r + 5)):
            if (rr - r) * self.dy > reach:
                break
            for q in self.plat[rr]:
                if q[3]:
                    cands.append((rr, q))
        if not cands:
            self.vx[j] = rnd.gauss(0, 60)
            return
        if rnd.random() < self.greed[j]:
            hi = max(c[0] for c in cands)
            rr, q = min((c for c in cands if c[0] == hi), key=lambda c: abs(c[1][0] - self.x[j]))
        else:
            rr, q = rnd.choice(cands)
        tx = q[0] + rnd.gauss(0, q[1] * 0.22) + rnd.gauss(0, self.aim[j])
        rise = (rr - r) * self.dy
        t = (J + math.sqrt(max(0.0, J * J - 2 * G * rise))) / G
        self.vx[j] = max(-760.0, min(760.0, (tx - self.x[j]) / t))

    def step(self, dt: float) -> None:
        self.t += dt
        self.n_step += 1
        if self.n_step % TICK:
            return
        h = dt * TICK
        n = len(self.x)
        # the lava creeps up all the time and closes in on the last ball – after every ball it burns it backs
        # off a little; with two left it gets really close, and in the final sprint it surges behind the leader
        if self.end is None:
            live = [self.y[j] for j in range(n) if self.alive[j]]
            left = len(live)
            floor_d = 120.0 if left > 1 else (330.0 if self.final() else 420.0)
            plan = 5 - 4.3 * min(1.0, self.t / (self.rows / 2.45)) ** 0.85   # about one ball out every 15 s
            if left > plan + 0.4 or self.final():
                self.D = max(floor_d, self.D - self.close * (1.5 if self.final() else 1.0) * h)
            else:
                self.D = min(560.0, self.D + 35 * h)
            want = max(live) + self.D if live else self.lava
            v = self.creep + 0.25 * self.t + max(0.0, min(700.0, (self.lava - want) * 2.2))
        else:
            v = 650.0
        self.lava = max(self.lava - v * h, self.top(len(self.plat) - 1) + 60)
        for j in range(n):
            if not self.alive[j]:
                continue
            y_prev = self.y[j]
            self.vy[j] += G * h
            self.x[j] += self.vx[j] * h
            self.y[j] += self.vy[j] * h
            if abs(self.x[j]) > HW - RB:
                self.x[j] = math.copysign(HW - RB, self.x[j])
                self.vx[j] = -self.vx[j] * 0.7
            if self.vy[j] > 0:                                    # falling: did it cross a platform top?
                b0, b1 = y_prev + RB, self.y[j] + RB
                r_hi = int(math.floor((self.y0 - b0) / self.dy))
                r_lo = int(math.ceil((self.y0 - b1) / self.dy))
                for r in range(max(0, r_lo), min(len(self.plat) - 1, r_hi) + 1):
                    top = self.top(r)
                    if not b0 <= top <= b1:
                        continue
                    for q in self.plat[r]:
                        if q[3] and abs(self.x[j] - q[0]) <= q[1] + RB * 0.4:
                            self._land(j, r, q)
                            break
                    else:
                        continue
                    break
            if self.end is None and self.y[j] + RB * 0.3 > self.lava:
                self.alive[j] = False
                self.dead_at.append((self.t, j))
                self.last_out = (self.t, j)
                self.D = max(self.D, 520.0)
                self.events.append((self.t, "break", j))
                if self.end is None and not any(self.alive):
                    self.finish()
            elif self.end is not None and self.y[j] > self.lava and j != self.winner:
                self.alive[j] = False
                self.dead_at.append((self.t, j))
                self.events.append((self.t, "break", j))
        # balls in the way knock each other aside
        for a in range(n):
            if not self.alive[a]:
                continue
            for b in range(a + 1, n):
                if not self.alive[b]:
                    continue
                dx, dy = self.x[b] - self.x[a], self.y[b] - self.y[a]
                d2 = dx * dx + dy * dy
                if d2 >= (2 * RB) ** 2 or d2 < 1e-6:
                    continue
                d = math.sqrt(d2)
                nx, ny = dx / d, dy / d
                push = (2 * RB - d) / 2
                self.x[a] -= nx * push
                self.y[a] -= ny * push
                self.x[b] += nx * push
                self.y[b] += ny * push
                vn = (self.vx[b] - self.vx[a]) * nx + (self.vy[b] - self.vy[a]) * ny
                if vn < 0:
                    self.vx[a] += vn * nx
                    self.vy[a] += vn * ny
                    self.vx[b] -= vn * nx
                    self.vy[b] -= vn * ny
                    self.events.append((self.t, "clack", a))
        self._camera(h)

    def _land(self, j: int, r: int, q: list) -> None:
        self.y[j] = self.top(r) - RB
        q[4] = self.t
        self.floor[j] = r
        self.best[j] = max(self.best[j], r)
        if q[2] == "e":                                           # the exit
            self.vy[j] = -self.J * 0.45
            self.vx[j] *= 0.3
            if self.end is None:
                self.winner = j
                self.finish()
            return
        self.landings += 1
        self.events.append((self.t, "bounce", j))
        if q[2] == "s":
            self.events.append((self.t, "tone", 30))
        if q[2] == "c":
            q[3] = False
            self.events.append((self.t, "clack", 1000 + r))
        if self.end is not None and j != self.winner:
            self.vy[j] = -self.J * 0.6                            # no way up any more – just hopping in panic
            self.vx[j] = self.rnd.gauss(0, 120)
            return
        self._launch(j, r, q[2] == "s")

    def _camera(self, h: float) -> None:
        n = len(self.x)
        live = [j for j in range(n) if self.alive[j]] or [self.leader()]
        hi = min(self.y[j] for j in live) - 170
        lo = self.lava + 110                                      # the lava is always in the picture ...
        if self.end is not None or self.final():                   # the exit (and its chequer) fully in view
            hi = min(hi, self.top(len(self.plat) - 1) - 260)
        span = max(lo - hi, 900.0)
        zoom = max(0.52, min(1.0, 940 / span))
        cam = (hi + lo) / 2 + 15 / zoom
        if (lo - hi) * zoom > 940:                                # ... unless the leader is far ahead of it
            cam = hi + 470 / zoom
        k = min(1.0, 2.5 * h)
        self.zoom += (zoom - self.zoom) * k
        self.cam += (cam - self.cam) * min(1.0, 3.5 * h)

    def good(self) -> bool:
        """A winner escapes, at least two balls burned on the way, and the lava was close behind at the end."""
        return (self.winner >= 0 and len(self.dead_at) >= 3 and self.dead_at[-1][0] > 0.62 * self.end
                and self.lava - self.y[self.winner] < 700)

    # ------------------------------------------------------------------ picture
    def at(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom, (y - self.cam) * self.zoom

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            x, y = self.at(self.x[i], min(self.y[i], self.lava))
            p.parts.burst_point(p.rng, x, y, self.cols[i], 120, 620)
            p.parts.burst_point(p.rng, x, y, LAVA_TOP, 60, 420)
            p.punch(0.55 if self.end is None else 0.25)
        elif kind == "clack" and i >= 1000:
            r = i - 1000
            for q in self.plat[r]:
                if not q[3]:
                    x1, y1 = self.at(q[0] - q[1], self.top(r))
                    x2, y2 = self.at(q[0] + q[1], self.top(r))
                    p.parts.burst_path(p.rng, [(x1, y1), (x2, y2)], (200, 170, 140), 22)
        elif kind == "finale" and self.winner >= 0:
            x, y = self.at(self.x[self.winner], self.y[self.winner])
            p.parts.burst_point(p.rng, x, y, GOLD, 260, 950)
            p.parts.burst_point(p.rng, x, y, self.cols[self.winner], 160, 700)

    def plat_color(self, r: int) -> tuple[int, int, int]:
        return self.look.color(r / self.rows, s=0.5, v=0.95)

    def draw(self, p: Painter) -> None:
        z = self.zoom
        top_y, bot_y = self.cam - 560 / z, self.cam + 560 / z
        for side in (-1, 1):                                       # tower walls
            p.line([self.at(side * (HW + 6), top_y), self.at(side * (HW + 6), bot_y)], (120, 110, 150),
                   max(2, 6 * z), glow=None)
        r_lo = max(0, int((self.y0 - bot_y) / self.dy) - 1)
        r_hi = min(len(self.plat) - 1, int((self.y0 - top_y) / self.dy) + 1)
        for r in range(r_lo, r_hi + 1):
            yy = self.top(r)
            for q in self.plat[r]:
                if not q[3]:
                    continue
                x, hw, kind, _, hit = q
                flash = max(0.0, 1 - (self.t - hit) / 0.22)
                a, b = self.at(x - hw, yy), self.at(x + hw, yy)
                if kind == "e":
                    sq = 28 * z
                    xa = a[0]
                    c = 0
                    while xa < b[0] - 1:
                        for row in range(2):
                            col = (250, 250, 250) if (c + row) % 2 else (30, 28, 36)
                            X, Y = (CX + xa) * SS, (CY + a[1] - sq * (2 - row)) * SS
                            p.d.rectangle((X, Y, X + sq * SS, Y + sq * SS), fill=col)
                        xa += sq
                        c += 1
                    p.line([a, b], GOLD, 10 * z, 0.3 + 0.7 * flash)
                    continue
                col = self.plat_color(r)
                if kind == "s":
                    col = (90, 255, 140)
                    p.line([(a[0] + 12 * z, a[1] + 4 * z), (b[0] - 12 * z, b[1] + 4 * z)], (40, 120, 70), 9 * z,
                           glow=None)
                elif kind == "c":
                    col = (200, 165, 130)
                p.line([a, b], col, max(3, 12 * z), flash * 0.8, glow=True if (flash or kind == "s") else None)
                if kind == "c":
                    mx = (a[0] + b[0]) / 2
                    p.line([(mx - 6 * z, a[1] - 5 * z), (mx + 3 * z, a[1] + 1), (mx - 2 * z, a[1] + 6 * z)],
                           (60, 40, 30), max(1.5, 3 * z), glow=None)
        self._draw_lava(p)
        p.particles()
        lead = self.leader()
        for j in sorted(range(len(self.x)), key=lambda j: j == lead):
            if not self.alive[j] and j != self.winner:
                continue
            x, y = self.at(self.x[j], self.y[j])
            p.trail(("b", j), x, y, RB * z, self.cols[j], 10)
            gold = j == self.winner and self.end is not None
            p.ball(x, y, max(RB * z, 12), self.cols[j], GOLD if gold else WHITE, max(2, (5 if gold else 3) * z))
            p.glow_disc(x, y, RB * 1.8 * z + (10 if j == lead else 0), GOLD if gold else self.cols[j])
        p.clip(-470, 500)

    def _draw_lava(self, p: Painter) -> None:
        z, t = self.zoom, self.t
        pts = []
        for k in range(0, 41):
            x = -HW - 20 + k * (2 * HW + 40) / 40
            y = self.lava + 9 * math.sin(0.021 * x + 3.1 * t) + 6 * math.sin(0.057 * x - 4.3 * t)
            pts.append(self.at(x, y))
        if min(q[1] for q in pts) > 990:
            return
        poly = pts + [(pts[-1][0], 1000.0), (pts[0][0], 1000.0)]
        p.d.polygon([((CX + x) * SS, (CY + y) * SS) for x, y in poly], fill=LAVA)
        deep = [(x, y + 70 * z) for x, y in pts] + [(pts[-1][0], 1000.0), (pts[0][0], 1000.0)]
        p.d.polygon([((CX + x) * SS, (CY + y) * SS) for x, y in deep], fill=(170, 34, 10))
        p.g.polygon([((CX + x) / 4, (CY + y) / 4) for x, y in poly], fill=(110, 36, 6))
        p.line(pts, LAVA_TOP, max(4, 9 * z), glow=(255, 120, 30))
        for k in range(14):                                       # bubbles popping up and down
            ph = (t * (0.6 + 0.07 * k) + k * 0.37) % 1.0
            bx = -HW + (k * 137.0) % (2 * HW)
            by = self.lava + 40 + 160 * (1 - ph)
            x, y = self.at(bx, by)
            if y < 500:
                p.ball(x, y, (4 + 9 * ph) * z, (255, 150, 40))

    def draw_text(self, p: Painter, d) -> None:
        super().draw_text(p, d)
        x, y0, y1 = W - 40, 560, 1400                            # progress bar: floors and the lava
        top = len(self.plat) - 1
        d.line((x, y0, x, y1), fill=(110, 110, 140), width=6)
        d.line((x - 14, y0, x + 14, y0), fill=GOLD, width=5)
        ly = y1 - (y1 - y0) * max(0.0, min(1.0, (self.y0 - self.lava) / (top * self.dy)))
        d.rectangle((x - 7, ly, x + 7, y1), fill=LAVA)
        lead = self.leader()
        for j in sorted(range(len(self.x)), key=lambda j: j == lead):
            if not self.alive[j] and j != self.winner:
                continue
            yy = y1 - (y1 - y0) * max(0.0, min(1.0, (self.y0 - self.y[j]) / (top * self.dy)))
            r = 15 if j == lead else 10
            d.ellipse((x - r, yy - r, x + r, yy + r), fill=self.cols[j], outline=WHITE, width=3 if j == lead else 2)

    # ------------------------------------------------------------------ text
    @property
    def counter_color(self) -> tuple[int, int, int]:
        t0, j = self.last_out
        if self.end is None and self.t - t0 < 1.6:
            return LAVA_TOP
        return self.cols[self.leader()]

    def title(self) -> list[str]:
        return ["Which ball escapes", "the rising lava?"]

    def counter(self) -> str:
        t0, j = self.last_out
        if self.end is None and self.t - t0 < 1.6:
            return f"{self.names[j]} BURNED! · {sum(self.alive)} left"
        top = len(self.plat) - 1
        lead = self.leader()
        if self.end is None and self.final():
            togo = top - self.best[lead]
            return f"FINAL SPRINT · {togo} floor{'s' if togo != 1 else ''} to go"
        if self.end is not None and self.winner >= 0:
            return f"{self.names[lead]} reached floor {top}!"
        return f"{self.names[lead]} leads · floor {self.best[lead]}/{top}"

    def finale(self) -> list[tuple[str, tuple]]:
        if self.winner < 0:
            return [("LAVA", LAVA_TOP), ("WINS!", WHITE)]
        return [(self.names[self.winner], self.cols[self.winner]), ("ESCAPED!", GOLD)]
