"""Brick core: balls smash through a wall of numbered bricks; green rings add balls, a hidden ×2 doubles them –
until the swarm reaches the core in the middle and cracks it (the shock wave takes every brick left with it)."""
from __future__ import annotations

import math

from PIL import ImageDraw

from ..sims import CX, CY, SS, TAU, Ball, Painter, Sim, _mix

COLS, ROWS = 10, 6
CELL = 94.0
X0, Y0 = -COLS * CELL / 2, -450.0         # top-left corner of the brick wall
BOTTOM = 430.0                             # floor of the box (the balls bounce everywhere, nothing is lost)
RB = 13.0
PLUS, DOUBLE, CORE, BRICK = "plus", "double", "core", "brick"
GREEN, GOLD, CORE_COL = (80, 235, 120), (255, 205, 60), (255, 70, 90)
MAX_BALLS = 48


class BrickCore(Sim):
    kind = "brick_core"
    concept = {
        "created": "2026-10-16T15:00:00+00:00",
        "idea": "Ballz-style brick breaker: balls bounce through a wall of numbered bricks (every hit counts one "
                "down), green +1 rings add a ball, a hidden ×2 ring doubles the swarm – the target is the core "
                "brick in the middle with hundreds of HP.",
        "inspiration": "viral 'ball vs numbered bricks' / Ballz brick-breaker simulations and '1 ball becomes 100' "
                       "multiplying-ball shorts",
        "finale": "the swarm grows until it breaks through to the core; at the last HP the core detonates in slow "
                  "motion and the shock wave blows away every brick that is left",
    }
    titles = ["{onscreen}", "1 ball vs. a wall of bricks – can the swarm crack the core?",
              "Every ring adds a ball – wait for the core"]
    questions = ["How many balls did it take? Guess before the end!", "Would you have aimed for the ×2 first?"]
    body = ("One ball, one wall of numbered bricks. Every hit counts a brick down, every green ring adds a ball, "
            "the gold ×2 ring doubles the whole swarm – and in the middle waits the core. Every hit plays the next "
            "note of {song}, every broken brick cracks.")
    playlist = ("Brick breaker", "Balls vs. numbered bricks – crack the core.")
    cover_at = 0.93
    trend_words = ("brick breaker", "bricks", "multiply", "1 ball", "core")
    slowmo = True
    finale_punch = 1.6
    note_gap = 0.075

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.speed = rnd.uniform(980, 1100)
        self.grid = [[-1] * COLS for _ in range(ROWS)]
        self.bricks: list[list] = []   # [kind, x0, y0, x1, y1, hp, hp0]
        cr, cc = 2, rnd.choice([4, 4, 3, 5])
        self.core = self._add(CORE, cr, cc, 2, 2, int(rnd.uniform(330, 410)))
        free = [(r, c) for r in range(ROWS) for c in range(COLS) if self.grid[r][c] < 0]
        rnd.shuffle(free)
        # the ×2 ring sits right next to the core, the +1 rings spread over the wall (two in the bottom row)
        near = [(r, c) for r, c in free if r in (2, 3) and (c == cc - 1 or c == cc + 2)]
        self._add(DOUBLE, *rnd.choice(near), 1, 1, 1)
        bottom = [(r, c) for r, c in free if r == ROWS - 1 and self.grid[r][c] < 0]
        for r, c in bottom[:2]:
            self._add(PLUS, r, c, 1, 1, 1)
        rest = [(r, c) for r, c in free if self.grid[r][c] < 0 and r < ROWS - 1]
        for r, c in rest[:rnd.randint(11, 13)]:
            self._add(PLUS, r, c, 1, 1, 1)
        top = rnd.uniform(22, 28)
        for r, c in free:
            if self.grid[r][c] < 0:
                depth = (ROWS - 1 - r) / (ROWS - 1)  # higher rows are tougher
                hp = max(1, int(round(top * (0.25 + 0.75 * depth) * rnd.uniform(0.6, 1.3))))
                self._add(BRICK, r, c, 1, 1, hp)
        a = rnd.uniform(-2.3, -0.85)
        self.balls = [Ball(rnd.uniform(-120, 120), BOTTOM - 60, math.cos(a) * self.speed, math.sin(a) * self.speed,
                           RB)]
        self.born = [0.0]
        self.hits = 0
        self.last_note = -9.0
        self.left = sum(1 for b in self.bricks if b[0] == BRICK)
        self.flash: dict[int, float] = {}
        self.doubled = -9.0
        self.boom: list[float] = []
        self.assault: float | None = None  # FINAL ASSAULT: the balls curve towards the core
        self.pull = rnd.uniform(5500, 6500)

    def _add(self, kind: str, r: int, c: int, h: int, w: int, hp: int) -> int:
        i = len(self.bricks)
        self.bricks.append([kind, X0 + c * CELL, Y0 + r * CELL, X0 + (c + w) * CELL, Y0 + (r + h) * CELL, hp, hp])
        for rr in range(r, r + h):
            for c2 in range(c, c + w):
                self.grid[rr][c2] = i
        return i

    # ------------------------------------------------------------- physics
    def _spawn(self, x: float, y: float) -> None:
        if len(self.balls) >= MAX_BALLS:
            return
        a = self.rnd.uniform(0, TAU)
        self.balls.append(Ball(x, y, math.cos(a) * self.speed, math.sin(a) * self.speed, RB))
        self.born.append(self.t)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            for b in self.balls:
                b.x += b.vx * dt * 0.3
                b.y += b.vy * dt * 0.3
            return
        hx, wall_bottom = -X0, Y0 + ROWS * CELL
        bricks, grid = self.bricks, self.grid
        core = bricks[self.core]
        if self.assault is None and self.left <= 8:
            self.assault = self.t
            self.events.append((self.t, "tone", 9))
            self.events.append((self.t, "assault", 0))
        pull = 0.0 if self.assault is None else self.pull * min(1.0, (self.t - self.assault) / 3) * dt
        kx, ky = (core[1] + core[3]) / 2, (core[2] + core[4]) / 2
        for j, b in enumerate(self.balls):
            if pull:
                dx, dy = kx - b.x, ky - b.y
                d = math.hypot(dx, dy) or 1.0
                b.vx, b.vy = b.vx + dx / d * pull, b.vy + dy / d * pull
                m = self.speed / math.hypot(b.vx, b.vy)
                b.vx, b.vy = b.vx * m, b.vy * m
            b.x += b.vx * dt
            b.y += b.vy * dt
            turned = False
            if b.x - RB < -hx or b.x + RB > hx:
                b.x = max(-hx + RB, min(hx - RB, b.x))
                b.vx = -b.vx
                turned = True
            if b.y - RB < Y0 or b.y + RB > BOTTOM:
                b.y = max(Y0 + RB, min(BOTTOM - RB, b.y))
                b.vy = -b.vy
                turned = True
            if b.y - RB < wall_bottom:
                c0, c1 = int((b.x - RB - X0) // CELL), int((b.x + RB - X0) // CELL)
                r0, r1 = int((b.y - RB - Y0) // CELL), int((b.y + RB - Y0) // CELL)
                seen = -1
                for r in range(max(0, r0), min(ROWS - 1, r1) + 1):
                    row = grid[r]
                    for c in range(max(0, c0), min(COLS - 1, c1) + 1):
                        i = row[c]
                        if i < 0 or i == seen:
                            continue
                        seen = i
                        br = bricks[i]
                        kind, x0, y0, x1, y1 = br[0], br[1], br[2], br[3], br[4]
                        if kind == PLUS or kind == DOUBLE:
                            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                            if (b.x - mx) ** 2 + (b.y - my) ** 2 < 34 ** 2:
                                self._collect(i)
                            continue
                        dx, dy = b.x - min(max(b.x, x0), x1), b.y - min(max(b.y, y0), y1)
                        if dx * dx + dy * dy >= RB * RB:
                            continue
                        if abs(dx) > abs(dy):
                            b.vx = math.copysign(abs(b.vx), dx)
                        elif dy:
                            b.vy = math.copysign(abs(b.vy), dy)
                        else:
                            b.vx, b.vy = -b.vx, -b.vy
                        turned = True
                        self._hit(i, j)
                        if self.end is not None:
                            return
                        break
                    else:
                        continue
                    break
            if turned:
                a = math.atan2(b.vy, b.vx) + self.rnd.gauss(0, 0.04)
                q = (a % (math.pi / 2)) / (math.pi / 2)  # keep away from the axes, or a ball runs in a rut
                if q < 0.1 or q > 0.9:
                    a += (0.1 - q if q < 0.5 else 0.9 - q) * math.pi / 2
                b.vx, b.vy = math.cos(a) * self.speed, math.sin(a) * self.speed

    def _collect(self, i: int) -> None:
        br = self.bricks[i]
        mx, my = (br[1] + br[3]) / 2, (br[2] + br[4]) / 2
        self._clear(i)
        if br[0] == PLUS:
            self._spawn(mx, my)
            self.events.append((self.t, "tone", min(9, len(self.balls) // 3)))
            self.events.append((self.t, "plus", i))
        else:
            for _ in range(len(self.balls)):
                self._spawn(mx, my)
            self.doubled = self.t
            self.events.append((self.t, "tone", 9))
            self.events.append((self.t, "double", i))

    def _clear(self, i: int) -> None:
        br = self.bricks[i]
        br[5] = 0
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] == i:
                    self.grid[r][c] = -1

    def _hit(self, i: int, j: int) -> None:
        br = self.bricks[i]
        br[5] -= 1
        self.hits += 1
        self.flash[i] = self.t
        # melody for the hits the viewer follows: the lead ball and the core; the swarm clacks (breaks crack anyway)
        hero = (j == 0 or i == self.core) and self.t - self.last_note >= self.note_gap
        if hero:
            self.last_note = self.t
        self.events.append((self.t, "bounce" if hero else "clack", j))
        if br[5] > 0:
            return
        self._clear(i)
        self.events.append((self.t, "break", i))
        if i == self.core:
            self.finish()
            cx, cy = (br[1] + br[3]) / 2, (br[2] + br[4]) / 2
            self.boom = [self.end + 0.12 + math.hypot((o[1] + o[3]) / 2 - cx, (o[2] + o[4]) / 2 - cy) / 1500
                         if o[5] > 0 else -1.0 for o in self.bricks]
        else:
            self.left -= br[0] == BRICK

    def good(self) -> bool:  # the core must be the climax: a real swarm and a final assault of 5–16 s
        return (len(self.balls) >= 16 and self.assault is not None and self.end is not None
                and 5 <= self.end - self.assault <= 16)

    # ------------------------------------------------------------- picture
    def prepare(self, p: Painter) -> None:
        hx = -X0 + 8
        p.line([(-hx, Y0 - 8), (hx, Y0 - 8), (hx, BOTTOM + 8), (-hx, BOTTOM + 8)], (200, 200, 230), 6,
               glow=None, closed=True, d=p.base_d)

    def brick_color(self, br: list) -> tuple[int, int, int]:
        if br[0] == CORE:
            return CORE_COL
        return self.look.color(min(1.0, br[5] / 40))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            br = self.bricks[i]
            mx, my = (br[1] + br[3]) / 2, (br[2] + br[4]) / 2
            if i != self.core:
                p.parts.burst_point(p.rng, mx, my, self.look.color(0.1), 26, 520)
        elif kind == "plus":
            br = self.bricks[i]
            p.parts.burst_point(p.rng, (br[1] + br[3]) / 2, (br[2] + br[4]) / 2, GREEN, 30, 420)
        elif kind == "double":
            br = self.bricks[i]
            p.parts.burst_point(p.rng, (br[1] + br[3]) / 2, (br[2] + br[4]) / 2, GOLD, 120, 900)
            p.punch(0.9)
        elif kind == "assault":
            p.punch(1.0)
            br = self.bricks[self.core]
            p.parts.burst_point(p.rng, (br[1] + br[3]) / 2, (br[2] + br[4]) / 2, CORE_COL, 160, 1000)
        elif kind == "finale":
            br = self.bricks[self.core]
            cx, cy = (br[1] + br[3]) / 2, (br[2] + br[4]) / 2
            p.parts.burst_point(p.rng, cx, cy, CORE_COL, 360, 1400)
            p.parts.burst_point(p.rng, cx, cy, (255, 255, 255), 160, 900)

    def _box(self, p: Painter, x0, y0, x1, y1, fill, outline=None, width=0.0, rad=12.0) -> None:
        g = 3.0
        p.d.rounded_rectangle(((CX + x0 + g) * SS, (CY + y0 + g) * SS, (CX + x1 - g) * SS, (CY + y1 - g) * SS),
                              radius=int(rad * SS), fill=fill, outline=outline, width=int(width * SS))

    def draw(self, p: Painter) -> None:
        t = self.t
        core = self.bricks[self.core]
        crit = core[5] / core[6] < 0.25 and self.end is None
        for i, br in enumerate(self.bricks):
            kind, x0, y0, x1, y1, hp, hp0 = br
            if self.boom and 0 <= self.boom[i] <= t:
                if self.boom[i] > -0.5:
                    p.parts.burst_point(p.rng, (x0 + x1) / 2, (y0 + y1) / 2, self.brick_color(br), 22, 700)
                    self.boom[i] = -2.0  # burst once (visual only)
                continue
            if hp <= 0:
                continue
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if kind == PLUS or kind == DOUBLE:
                col = GREEN if kind == PLUS else GOLD
                r = 28 + 4 * math.sin(TAU * 1.5 * t + i)
                p.d.ellipse(((CX + mx - r) * SS, (CY + my - r) * SS, (CX + mx + r) * SS, (CY + my + r) * SS),
                            outline=col, width=int(6 * SS))
                p.glow_disc(mx, my, r * 1.3, _mix(col, 0.7))
                continue
            k = max(0.0, 1 - (t - self.flash.get(i, -9)) / 0.12)
            col = self.brick_color(br)
            if kind == CORE:
                pulse = 0.5 + 0.5 * math.sin(TAU * (4 if crit else 1.2) * t)
                fill = tuple(int(c + (255 - c) * max(k * 0.6, 0.25 * pulse * crit)) for c in _mix(col, 0.75))
                self._box(p, x0, y0, x1, y1, fill, (255, 255, 255), 5, 22)
                p.glow_disc(mx, my, CELL * (1.1 + 0.25 * pulse), _mix(col, 0.6 + 0.4 * pulse))
            else:
                fill = tuple(int(c + (255 - c) * 0.6 * k) for c in _mix(col, 0.8))
                self._box(p, x0, y0, x1, y1, fill)
                if k > 0:
                    p.glow_disc(mx, my, CELL * 0.6, _mix(col, k))
        if self.boom and self.end is not None:  # shock wave
            age = t - self.end
            if 0 < age < 1.2:
                cx, cy = (core[1] + core[3]) / 2, (core[2] + core[4]) / 2
                r = 120 + 1500 * age
                p.d.ellipse(((CX + cx - r) * SS, (CY + cy - r) * SS, (CX + cx + r) * SS, (CY + cy + r) * SS),
                            outline=_mix((255, 255, 255), 1 - age / 1.2), width=int(14 * SS))
        p.particles()
        for j, b in enumerate(self.balls):
            new = max(0.0, 1 - (t - self.born[j]) / 0.3)
            col = self.look.color((j * 0.137) % 1.0)
            if self.assault is not None and j < 32:
                p.trail(j, b.x, b.y, RB, col, 6)
            p.ball(b.x, b.y, RB * (1 + new), (255, 255, 255), col, 4)
            if j < 32:
                p.glow_disc(b.x, b.y, RB * 2.2, _mix(col, 0.8))
        p.clip(-470, 500)

    def draw_text(self, p: Painter, d: ImageDraw.ImageDraw) -> None:
        for i, line in enumerate(self.title()):
            p.centered(d, 210 + i * 92, line, p.f_title, (255, 255, 255), 3)
        p.centered(d, 420, self.counter(), p.f_count, self.counter_color, 2)
        for i, br in enumerate(self.bricks):
            kind, x0, y0, x1, y1, hp, hp0 = br
            if hp <= 0 or (self.boom and self.boom[i] < -1.5) or kind == CORE:
                continue
            label = "+1" if kind == PLUS else "×2" if kind == DOUBLE else str(hp)
            f = p.f_small
            tw = d.textlength(label, font=f)
            d.text((CX + (x0 + x1) / 2 - tw / 2, CY + (y0 + y1) / 2 - 21), label, font=f,
                   fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
        core = self.bricks[self.core]
        if core[5] > 0:
            mx, my = CX + (core[1] + core[3]) / 2, CY + (core[2] + core[4]) / 2
            f = p.f_big[70 if core[5] < 1000 else 60]
            tw = d.textlength(str(core[5]), font=f)
            d.text((mx - tw / 2, my - 52), str(core[5]), font=f, fill=(255, 255, 255), stroke_width=5,
                   stroke_fill=(0, 0, 0))
            tw = d.textlength("CORE", font=p.f_small)
            d.text((mx - tw / 2, my - 82), "CORE", font=p.f_small, fill=(255, 230, 230), stroke_width=3,
                   stroke_fill=(0, 0, 0))
        if self.end is None:
            if self.assault is not None:
                pulse = 0.5 + 0.5 * math.cos(TAU * 2.5 * self.t)
                p.centered(d, 1422, f"FINAL ASSAULT – core {core[5]} HP", p.f_count,
                           _mix((255, 70, 70), 0.6 + 0.4 * pulse), 2)
            elif self.t - self.doubled < 1.6:
                p.centered(d, 1422, f"×2 – {len(self.balls)} BALLS!", p.f_count, GOLD, 2)
            elif core[5] / core[6] < 0.25:
                pulse = 0.5 + 0.5 * math.cos(TAU * 2.5 * self.t)
                p.centered(d, 1422, f"CORE CRITICAL – {core[5]} HP", p.f_count,
                           _mix((255, 70, 70), 0.6 + 0.4 * pulse), 2)
            elif core[5] < core[6]:
                p.centered(d, 1422, f"core under attack – {core[5]} HP", p.f_count, (255, 150, 150), 2)
            else:
                p.centered(d, 1422, f"core: {core[5]} HP", p.f_count, (255, 214, 120), 2)
        else:
            p.big_text(d, self.finale(), self.t - self.end)

    def title(self) -> list[str]:
        return ["Every ring adds a ball", "Can they crack the core?"]

    def counter(self) -> str:
        n = len(self.balls)
        return f"{n} ball{'s' if n > 1 else ''} · {self.left} brick{'s' if self.left != 1 else ''} left"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("CORE", CORE_COL), ("CRACKED!", (255, 255, 255)), (f"{len(self.balls)} balls", GREEN)]
