"""Blade duel: two balls with spinning blades bounce around an arena; every hit upgrades the attacker."""
from __future__ import annotations

import math

from PIL import ImageDraw

from ..sims import CX, CY, SS, TAU, TEAMS, W, Ball, Painter, Sim, _mix

UPGRADES = {  # key: (label on screen, what one hit adds)
    "length": ("LONGER BLADE", "+blade length"),
    "spin": ("FASTER SPIN", "+spin speed"),
    "damage": ("HARDER HITS", "+damage"),
}


class BladeDuel(Sim):
    kind = "blade_duel"
    concept = {
        "created": "2026-10-16T12:00:00+00:00",
        "idea": "Two balls with spinning blades bounce around an arena; every hit cuts the other's HP and "
                "upgrades the attacker (longer blade / faster spin / harder hits) – blades that cross parry and "
                "flip their spin.",
        "inspiration": "viral 'ball battle' duels with weapons and health bars (sword ball vs. dagger ball)",
        "finale": "the fight speeds up as the upgrades stack; the knockout hit shatters the loser in slow motion",
    }
    titles = ["{onscreen}", "Every hit makes it stronger – who wins the blade duel?",
              "Two balls, two spinning blades – who survives?"]
    questions = ["Which upgrade would you pick?", "Did you call the winner before the end?"]
    body = ("Two balls, two spinning blades, one arena. Every hit takes HP from the other ball and upgrades the "
            "attacker – blades that cross parry and flip their spin. Every wall bounce plays the next note of "
            "{song}, every hit cracks.")
    playlist = ("Blade duels", "Two balls, two blades, every hit upgrades the attacker.")
    cover_at = 0.9
    trend_words = ("ball battle", "duel", "which wins", "health bar", "upgrade")
    slowmo = True
    finale_punch = 1.4
    note_gap = 0.09

    R = 440.0       # arena radius
    OY = 30.0       # arena centre (y)
    RB = 50.0       # ball radius
    G = 700.0       # gravity

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        pair = rnd.choice([("length", "spin"), ("length", "damage"), ("spin", "damage")])
        if rnd.random() < 0.5:
            pair = pair[::-1]
        self.up = list(pair)
        self.team = list(rnd.choice([(0, 1), (5, 7), (4, 2), (6, 3), (1, 5)]))
        self.hp0 = rnd.choice([180, 200, 240])
        self.hp = [float(self.hp0)] * 2
        self.blade0, self.spin0 = rnd.uniform(100, 120), rnd.uniform(4.6, 5.6)
        self.blade = [self.blade0] * 2  # blade length beyond the ball
        self.spin = [self.spin0] * 2    # rad/s
        self.dmg = [6.0, 6.0]
        self.dir = [1, -1]
        self.phi = [rnd.uniform(0, TAU), rnd.uniform(0, TAU)]
        self.speed = rnd.uniform(560, 640)
        self.balls = []
        for k, sx in enumerate((-1, 1)):
            a = rnd.uniform(-2.4, -0.8)
            self.balls.append(Ball(sx * 200.0, self.OY + rnd.uniform(-60, 60), math.cos(a) * self.speed * -sx,
                                   math.sin(a) * self.speed, self.RB, TEAMS[self.team[k]][1], TEAMS[self.team[k]][0]))
        self.sd = rnd.uniform(40, 56)  # sudden death: damage ×2, then ×3, ×4 … every 6 s
        self.cool = [-9.0, -9.0]
        self._m = 1
        self.parry_t = -9.0
        self.hits = [0, 0]
        self.last_hit = [-9.0, -9.0]
        self.wall = 0
        self.loser: int | None = None
        self.lead_changes, self._lead = 0, None
        self.min_ratio = 1.0

    # ------------------------------------------------------------- physics
    def tip(self, k: int) -> tuple[float, float, float, float]:
        b, a = self.balls[k], self.phi[k]
        c, s = math.cos(a), math.sin(a)
        r0, r1 = self.RB * 0.55, self.RB + self.blade[k]
        return b.x + c * r0, b.y + s * r0, b.x + c * r1, b.y + s * r1

    def _upgrade(self, k: int) -> None:
        u = self.up[k]
        if u == "length":
            self.blade[k] = min(300.0, self.blade[k] + 12)
        elif u == "spin":
            self.spin[k] = min(26.0, self.spin[k] * 1.12)
        else:
            self.dmg[k] = min(40.0, self.dmg[k] + 2)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            for k in range(2):
                if k != self.loser:
                    self.phi[k] += self.dir[k] * self.spin[k] * dt
            return
        R, oy = self.R, self.OY
        m = self.mult()
        if m != self._m:
            self._m = m
            self.events.append((self.t, "tone", 4 + m))
            self.events.append((self.t, "sudden", m))
        for k, b in enumerate(self.balls):
            self.phi[k] += self.dir[k] * self.spin[k] * dt
            b.move(dt, self.G)
            dx, dy = b.x, b.y - oy
            d = math.hypot(dx, dy)
            if d + b.rb > R:
                nx, ny = dx / d, dy / d
                b.x, b.y = nx * (R - b.rb), oy + ny * (R - b.rb)
                vn = b.vx * nx + b.vy * ny
                if vn > 0:
                    b.vx, b.vy = b.vx - 2 * vn * nx, b.vy - 2 * vn * ny
                    a = math.atan2(b.vy, b.vx) + self.rnd.gauss(0, 0.12)
                    sp = max(self.speed, math.hypot(b.vx, b.vy) * 0.97)
                    b.vx, b.vy = math.cos(a) * sp, math.sin(a) * sp
                    self.wall += 1
                    self.events.append((self.t, "bounce", k))
        a, b = self.balls
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        md = a.rb + b.rb
        if 0 < d < md:
            nx, ny, push = dx / d, dy / d, (md - d) / 2
            a.x, a.y, b.x, b.y = a.x - nx * push, a.y - ny * push, b.x + nx * push, b.y + ny * push
            vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
            if vn < 0:
                a.vx, a.vy, b.vx, b.vy = a.vx + vn * nx, a.vy + vn * ny, b.vx - vn * nx, b.vy - vn * ny
        # blades: parry (crossing blades) or hit (blade cuts the other ball)
        if d > 2 * self.RB + 520:  # far apart: nothing can touch
            return
        t0, t1 = self.tip(0), self.tip(1)
        if self.t - self.parry_t > 0.18 and _cross(t0, t1):
            self.parry_t = self.t
            self.dir = [-self.dir[0], -self.dir[1]]
            self.events.append((self.t, "clack", 0))
            return
        for k in range(2):
            if self.t - self.cool[k] < 0.26:
                continue
            o = self.balls[1 - k]
            x0, y0, x1, y1 = (t0, t1)[k]
            if _seg_dist(o.x, o.y, x0, y0, x1, y1) < o.rb:
                self._hit(k)
                if self.end is not None:
                    return

    def _hit(self, k: int) -> None:
        o, me = self.balls[1 - k], self.balls[k]
        self.cool[k] = self.t
        self.hits[k] += 1
        self.last_hit[1 - k] = self.t
        self.hp[1 - k] = max(0.0, self.hp[1 - k] - self.dmg[k] * self.mult())
        dx, dy = o.x - me.x, o.y - me.y
        d = math.hypot(dx, dy) or 1.0
        o.vx, o.vy = o.vx + dx / d * 420, o.vy + dy / d * 420  # knock-back
        self._upgrade(k)
        self.events.append((self.t, "break", k))
        r = [h / self.hp0 for h in self.hp]
        lead = 0 if r[0] > r[1] else 1 if r[1] > r[0] else self._lead
        if self._lead is not None and lead != self._lead:
            self.lead_changes += 1
        self._lead = lead
        if self.hp[1 - k] <= 0:
            self.loser = 1 - k
            self.finish()
        else:
            self.min_ratio = min(self.min_ratio, max(r))

    def mult(self, t: float | None = None) -> int:
        t = self.t if t is None else t
        return 1 if t < self.sd else 2 + int((t - self.sd) / 6)

    def winner(self) -> int:
        return 1 - self.loser if self.loser is not None else int(self.hp[1] > self.hp[0])

    def good(self) -> bool:
        w = self.winner()
        return self.lead_changes >= 1 and self.hp[w] / self.hp0 <= 0.6

    # ------------------------------------------------------------- picture
    def prepare(self, p: Painter) -> None:
        p.ball(0, self.OY, self.R, (14, 14, 26), d=p.base_d)
        for i in range(1, 4):
            p.line(_circle(0, self.OY, self.R * i / 4, 90), (34, 34, 58), 2, glow=None, d=p.base_d)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            o = self.balls[1 - i]
            p.parts.burst_point(p.rng, o.x, o.y, self.balls[i].col, 18, 420)
            if self.hp[1 - i] / self.hp0 < 0.3:
                p.punch(0.25)
        elif kind == "clack":
            x0, y0, x1, y1 = self.tip(0)
            p.parts.burst_point(p.rng, (x0 + x1) / 2, (y0 + y1) / 2, (255, 240, 200), 14, 380)
        elif kind == "sudden":
            p.punch(0.5 + 0.15 * i)
            p.parts.burst_ring(p.rng, self.R + 7, 0, TAU, (255, 70, 70), 160)
        elif kind == "finale":
            o = self.balls[self.loser]
            p.parts.burst_point(p.rng, o.x, o.y, o.col, 320, 1100)
            p.parts.burst_point(p.rng, o.x, o.y, (255, 255, 255), 120, 700)

    def draw(self, p: Painter) -> None:
        danger = min(self.hp) / self.hp0
        hot = self.end is None and (danger < 0.3 or self.mult() > 1)
        pulse = 0.5 + 0.5 * math.sin(TAU * 3 * self.t) if hot else 0.0
        rim = _mix((255, 70, 70), 0.5 + 0.5 * pulse) if hot else (200, 200, 230)
        p.ring(self.R + 7, 0, 360, rim, 9, 0.3 * pulse)
        p.particles()
        for k, b in enumerate(self.balls):
            if k == self.loser:
                continue
            x0, y0, x1, y1 = self.tip(k)
            ux, uy = x1 - x0, y1 - y0
            n = math.hypot(ux, uy)
            ux, uy = ux / n, uy / n
            w = 21.0
            bx, by = x1 - ux * min(40, n * 0.25), y1 - uy * min(40, n * 0.25)
            poly = [(x0 - uy * w, y0 + ux * w), (bx - uy * w * 0.8, by + ux * w * 0.8), (x1, y1),
                    (bx + uy * w * 0.8, by - ux * w * 0.8), (x0 + uy * w, y0 - ux * w)]
            p.line([(x0, y0), (x1, y1)], b.col, 8, glow=b.col)
            p.d.polygon([((CX + x) * SS, (CY + y) * SS) for x, y in poly], fill=(235, 238, 250),
                        outline=b.col, width=int(4 * SS))
            p.line([(x0, y0), (bx, by)], _mix(b.col, 0.7), 4, glow=None)
        for k, b in enumerate(self.balls):
            if k == self.loser:
                continue
            flash = max(0.0, 1 - (self.t - self.last_hit[k]) / 0.2)
            p.trail(k, b.x, b.y, b.rb, b.col, 8)
            fill = tuple(int(c + (255 - c) * flash) for c in b.col)
            p.ball(b.x, b.y, b.rb, fill, (255, 255, 255), 4)
            p.glow_disc(b.x, b.y, b.rb * 1.45, _mix(b.col, 0.8))
        p.clip(-470, 500)

    def stat(self, k: int) -> str:
        u = self.up[k]
        if u == "length":
            return f"blade {self.blade[k] / self.blade0:.1f}×"
        if u == "spin":
            return f"spin {self.spin[k] / self.spin0:.1f}×"
        return f"dmg {self.dmg[k]:.0f}"

    def draw_text(self, p: Painter, d: ImageDraw.ImageDraw) -> None:
        for i, line in enumerate(self.title()):
            p.centered(d, 210 + i * 92, line, p.f_title, (255, 255, 255), 3)
        gap, x0, x1, y0, y1 = 24, 70, W - 70, 404, 452
        half = (x1 - x0 - gap) / 2
        for k in range(2):
            col = self.balls[k].col
            left = x0 + k * (half + gap)
            frac = self.hp[k] / self.hp0
            d.rounded_rectangle((left, y0, left + half, y1), radius=12, fill=(30, 30, 44))
            if frac > 0:
                w = half * frac
                lx = left if k == 0 else left + half - w
                d.rounded_rectangle((lx, y0, lx + w, y1), radius=12, fill=col)
            d.rounded_rectangle((left, y0, left + half, y1), radius=12, outline=(255, 255, 255), width=3)
            label = f"{math.ceil(self.hp[k])} HP"
            tw = d.textlength(label, font=p.f_small)
            d.text((left + half / 2 - tw / 2, y0 + 5), label, font=p.f_small, fill=(255, 255, 255),
                   stroke_width=3, stroke_fill=(0, 0, 0))
            for j, (txt, f, c) in enumerate(((UPGRADES[self.up[k]][0], p.f_small, col),
                                              (self.stat(k), p.f_small, (235, 235, 245)))):
                tw = d.textlength(txt, font=f)
                tx = left + 6 if k == 0 else left + half - tw - 6
                d.text((tx, y1 + 10 + j * 38), txt, font=f, fill=c, stroke_width=3, stroke_fill=(0, 0, 0))
        if self.end is None:
            m = self.mult()
            if m > 1:
                pulse = 0.5 + 0.5 * math.cos(TAU * 2 * self.t)
                p.centered(d, 1422, f"SUDDEN DEATH – damage ×{m}", p.f_count, _mix((255, 70, 70), 0.6 + 0.4 * pulse), 2)
            else:
                p.centered(d, 1422, f"sudden death in {math.ceil(self.sd - self.t)} s", p.f_count, (255, 214, 120), 2)
        if self.end is not None and self.t >= self.end:
            p.big_text(d, self.finale(), self.t - self.end)

    def title(self) -> list[str]:
        return ["Every hit upgrades it", "Who wins the duel?"]

    def counter(self) -> str:
        return f"{sum(self.hits)} hits"

    def finale(self) -> list[tuple[str, tuple]]:
        w = self.winner()
        return [("K.O.!", (255, 255, 255)), (f"{self.balls[w].name} WINS", self.balls[w].col),
                (f"{math.ceil(self.hp[w])} HP left", (255, 214, 120))]


def _seg_dist(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> float:
    vx, vy = x1 - x0, y1 - y0
    q = max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - x0 - q * vx, py - y0 - q * vy)


def _cross(a: tuple, b: tuple) -> bool:
    def o(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (o(ax0, ay0, ax1, ay1, bx0, by0) * o(ax0, ay0, ax1, ay1, bx1, by1) < 0
            and o(bx0, by0, bx1, by1, ax0, ay0) * o(bx0, by0, bx1, by1, ax1, ay1) < 0)


def _circle(x: float, y: float, r: float, n: int) -> list[tuple[float, float]]:
    return [(x + r * math.cos(TAU * i / n), y + r * math.sin(TAU * i / n)) for i in range(n + 1)]
