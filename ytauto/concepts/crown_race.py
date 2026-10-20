"""Crown race: four coloured balls race through a field of pinball bumpers – every bumper hit is a point and paints the
bumper in the ball's colour. The leader wears the crown, and the crown makes it slower, so the lead keeps changing
hands until the final sprint and a photo finish."""
from __future__ import annotations

import math

from ..sims import TAU, TEAMS, Ball, Painter, Sim, _mix, _reflect

WHITE = (255, 255, 255)
GOLD = (255, 210, 70)
RB = 22.0
CROWN = 0.8         # the crown slows its wearer to this share of the speed
FINAL = 10          # the last points are the final sprint


class CrownRace(Sim):
    kind = "crown_race"
    concept = {
        "created": "2026-10-20T04:40:00+00:00",
        "idea": "Four coloured balls race through a field of pinball bumpers; every bumper hit is a point and paints "
                "the bumper in that colour. The leader wears the crown – and the crown slows it down – so the lead "
                "keeps changing hands.",
        "inspiration": "viral 'which colour wins?' ball race shorts and pinball / pop-bumper satisfying clips, with "
                       "a catch-up rule borrowed from Mario Kart so every race stays close",
        "finale": "the final sprint: everybody speeds up, the bumpers flash and the last points decide a photo "
                  "finish in slow motion; the winner's colour floods every bumper",
    }
    titles = ["{onscreen}", "The leader wears the crown – and the crown slows it down",
              "Every bumper hit is a point – which colour wins the crown race?"]
    questions = ["Which colour did you pick? 👑", "Fair rule or unfair – should the crown slow you down?"]
    body = ("Four balls race through a field of bumpers: every hit is a point and paints the bumper. The crown "
            "holder's hits play the next note of {song}, the others knock – and the crown makes its wearer slower, "
            "so the lead keeps changing until the photo finish.")
    playlist = ("Crown race", "The leader wears the crown – and it slows it down.")
    cover_at = 0.97
    trend_words = ("which color wins", "race", "pinball", "bumpers", "crown", "ball", "simulation")
    slowmo = True
    finale_punch = 1.5
    note_gap = 0.05

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.R = 430.0
        self.goal = rnd.choice((170, 180, 190, 200))
        self.v = rnd.uniform(640, 700)
        # bumpers: a centre one and two rings, slightly jittered
        self.bump: list[tuple[float, float, float]] = [(0.0, 0.0, rnd.uniform(48, 56))]
        for ring, n, r in ((165, 5, 36), (312, 8, 30)):
            off = rnd.uniform(0, TAU)
            for k in range(n):
                a = off + TAU * k / n
                self.bump.append((math.cos(a) * ring, math.sin(a) * ring, r + rnd.uniform(-3, 3)))
        self.owner = [-1] * len(self.bump)
        self.bump_hit = [-9.0] * len(self.bump)
        lineup = rnd.choice(((0, 1, 2, 3), (4, 7, 5, 6), (0, 1, 3, 6), (2, 4, 1, 5)))
        self.teams = [TEAMS[k] for k in lineup]
        self.balls = []
        for i in range(4):
            a = TAU * i / 4 + rnd.uniform(-0.2, 0.2) + math.pi / 4
            d = rnd.uniform(0, TAU)
            self.balls.append(Ball(math.cos(a) * 255, math.sin(a) * 255, math.cos(d) * self.v, math.sin(d) * self.v,
                                   RB, self.teams[i][1], self.teams[i][0]))
        self.score = [0] * 4
        self.king = -1
        self.crowned = -9.0
        self.winner = -1
        self.last_xy = (0.0, 0.0)

    def sprint(self) -> bool:
        return max(self.score) >= self.goal - FINAL

    def speed_of(self, i: int) -> float:
        v = self.v * (1.25 if self.sprint() else 1.0)
        return v * (CROWN if i == self.king else 1.0)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        for i, b in enumerate(self.balls):
            b.move(dt, 0.0)
            r = math.hypot(b.x, b.y)
            if r + RB > self.R:
                nx, ny = b.x / r, b.y / r
                b.x, b.y = nx * (self.R - RB), ny * (self.R - RB)
                if b.vx * nx + b.vy * ny > 0:
                    b.vx, b.vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, 0.1, 200)
            for k, (bx, by, br) in enumerate(self.bump):
                dx, dy = b.x - bx, b.y - by
                md = br + RB
                if abs(dx) >= md or abs(dy) >= md:
                    continue
                d = math.hypot(dx, dy)
                if d >= md or d == 0:
                    continue
                nx, ny = dx / d, dy / d
                b.x, b.y = bx + nx * md, by + ny * md
                if b.vx * nx + b.vy * ny < 0:
                    b.vx, b.vy = _reflect(b.vx, b.vy, -nx, -ny, self.rnd, 0.12, 200)
                    self._point(i, k)
                    if self.end is not None:
                        return
            sp = math.hypot(b.vx, b.vy) or 1.0
            want = self.speed_of(i)
            k = 1 + (want / sp - 1) * min(1.0, 4 * dt)       # ease towards the target speed
            b.vx, b.vy = b.vx * k, b.vy * k
        self._collide()

    def _point(self, i: int, k: int) -> None:
        self.score[i] += 1
        self.owner[k] = i
        self.bump_hit[k] = self.t
        b = self.balls[i]
        self.last_xy = (b.x, b.y)
        lead = max(range(4), key=lambda j: (self.score[j], j == self.king))
        if lead != self.king and self.score[lead] > (self.score[self.king] if self.king >= 0 else 0):
            self.king = lead
            self.crowned = self.t
            self.events.append((self.t, "break", lead))          # the crown changes hands
        # the crown holder carries the melody, everybody else knocks
        self.events.append((self.t, "bounce" if i == self.king else "clack", i))
        if self.score[i] >= self.goal:
            self.winner = i
            self.finish()

    def _collide(self) -> None:
        bs = self.balls
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if d >= 2 * RB or d == 0:
                    continue
                nx, ny, push = dx / d, dy / d, (2 * RB - d) / 2
                a.x, a.y, b.x, b.y = a.x - nx * push, a.y - ny * push, b.x + nx * push, b.y + ny * push
                vn = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                if vn < 0:
                    a.vx, a.vy, b.vx, b.vy = a.vx + vn * nx, a.vy + vn * ny, b.vx - vn * nx, b.vy - vn * ny
                    self.events.append((self.t, "clack", 0))

    def good(self) -> bool:
        if self.end is None:
            return False
        s = sorted(self.score, reverse=True)
        return s[0] - s[1] <= 4                                   # a close finish

    # ------------------------------------------------------------------ picture
    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            b = self.balls[i]
            p.parts.burst_point(p.rng, b.x, b.y, GOLD, 40, 420)
            p.punch(0.3 if self.sprint() else 0.15)
        elif kind == "finale":
            col = self.teams[self.winner][1]
            x, y = self.last_xy
            p.parts.burst_point(p.rng, x, y, col, 220, 900)
            p.parts.burst_point(p.rng, x, y, GOLD, 120, 700)
            p.parts.burst_ring(p.rng, self.R, 0, TAU, col, 240)
            self.owner = [self.winner] * len(self.bump)

    def draw(self, p: Painter) -> None:
        t = self.t
        sprint = self.end is None and self.sprint()
        pulse = 0.5 + 0.5 * math.sin(t * 14)
        p.ring(self.R + 6, 0, 360, GOLD if sprint else (110, 110, 160), 8, 0.3 * pulse if sprint else 0.0)
        for k, (bx, by, br) in enumerate(self.bump):
            o = self.owner[k]
            col = self.teams[o][1] if o >= 0 else (90, 90, 120)
            f = max(0.0, 1 - (t - self.bump_hit[k]) / 0.2)
            rr = br * (1 + 0.12 * f)
            p.glow_disc(bx, by, rr * 1.5, _mix(col, 0.3 + 0.45 * f))
            p.ball(bx, by, rr, _mix(col, 0.12 + 0.5 * f), tuple(int(c + (255 - c) * f) for c in col), 6)
        p.particles()
        for i, b in enumerate(self.balls):
            col = self.teams[i][1]
            p.trail(i, b.x, b.y, RB, col, 12)
            p.glow_disc(b.x, b.y, RB * 2.2, _mix(col, 0.8))
            p.ball(b.x, b.y, RB, col, WHITE, 5)
            if i == self.king:                                    # the crown
                cy = b.y - RB - 16
                pts = [(b.x - 22, cy + 10), (b.x - 22, cy - 10), (b.x - 11, cy), (b.x, cy - 16), (b.x + 11, cy),
                       (b.x + 22, cy - 10), (b.x + 22, cy + 10)]
                p.line(pts, GOLD, 7, glow=GOLD, closed=True)

    def draw_text(self, p: Painter, d) -> None:
        super().draw_text(p, d)
        # the scoreboard under the arena
        y = 960 + self.R + 18
        w = 220
        x0 = 540 - 2 * w + w / 2
        for i, (name, col) in enumerate(self.teams):
            txt = str(self.score[i])
            tw = d.textlength(txt, font=p.f_count)
            x = x0 + i * w
            if i == self.king:
                d.rounded_rectangle((x - 70, y - 4, x + 70, y + 60), radius=18, outline=GOLD, width=4)
            d.text((x - tw / 2, y), txt, font=p.f_count, fill=col, stroke_width=2, stroke_fill=(0, 0, 0))

    def title(self) -> list[str]:
        return ["Which colour gets", f"{self.goal} hits first?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"{self.teams[self.winner][0]} WINS"
        left = self.goal - max(self.score)
        if self.sprint():
            return f"FINAL SPRINT · {left} to go"
        if self.king < 0:
            return "first hit takes the crown"
        return f"{self.teams[self.king][0]} has the crown · {left} to go"

    @property
    def counter_color(self) -> tuple[int, int, int]:
        return self.teams[self.king][1] if self.king >= 0 else (255, 214, 120)

    def finale(self) -> list[tuple[str, tuple]]:
        name, col = self.teams[self.winner]
        s = sorted(self.score, reverse=True)
        return [(f"{name} WINS!", col), (f"{s[0]} – {s[1]}", WHITE)]
