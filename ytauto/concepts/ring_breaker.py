"""Ring breaker: one ball sits in the middle of seven rings made of tiles. Every hit cracks a tile, a tile with no
HP left falls away – and as soon as a ball slips through a hole the whole ring shatters, a new ball joins and all of
them get faster. The outer rings are tougher, the swarm grows, and the last ring has to be smashed by everyone."""
from __future__ import annotations

import math

from ..sims import TAU, Ball, Painter, Sim, _mix, _reflect

WHITE = (255, 255, 255)
GOLD = (255, 210, 90)
RADII = (105, 160, 215, 272, 330, 392, 458)
WIDTH = (13, 14, 15, 16, 17, 18, 22)
RB = 13.0
G = 260.0


class RingBreaker(Sim):
    kind = "ring_breaker"
    concept = {
        "created": "2026-10-17T19:30:00+00:00",
        "idea": "Seven rings built from tiles around one ball: every hit cracks a tile, a hole lets the ball out, "
                "the ring shatters and a new ball joins – the outer rings have more HP, so the growing swarm has to "
                "hammer its way out.",
        "inspiration": "viral 'can the ball escape?' ring shorts and brick-breaker 'balls vs. HP' simulations – "
                       "here the ball has to carve its own way out instead of waiting for a gap",
        "finale": "the final ring has the most HP; all balls hammer it in a final frenzy, the first one through "
                  "blows the whole ring apart in a shower of tiles",
    }
    titles = ["{onscreen}", "Every hit cracks a tile – can it smash through all 7 rings?",
              "1 ball vs. 7 rings of tiles – wait for the last one"]
    questions = ["Which ring did you think would stop it?", "How many balls will it take? Guess before the end!"]
    body = ("One ball, seven rings of tiles. Every hit cracks a tile and plays the next note of {song}; when a ball "
            "slips through a hole, the whole ring shatters and another ball joins. The outer rings are tougher – the "
            "last one needs the whole swarm.")
    playlist = ("Break out", "Balls smashing their way out.")
    cover_at = 0.95
    trend_words = ("escape", "break", "rings", "smash", "bouncing", "ball")
    slowmo = True
    finale_punch = 1.8
    note_gap = 0.07

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.rings = []          # per ring: list of tile HP (0 = gone)
        self.hp0 = []
        self.n_tiles = []
        for k, r in enumerate(RADII):
            n = int(round(TAU * r / 46))
            hp = (1, 2, 2, 3, 4, 6, 8)[k] + (rnd.random() < 0.5 and k in (3, 4))
            self.rings.append([hp] * n)
            self.hp0.append(hp)
            self.n_tiles.append(n)
        self.k = 0               # current ring to break
        self.final_hp = 1
        a, sp = rnd.uniform(0, TAU), rnd.uniform(430, 500)
        self.v = sp
        self.balls = [Ball(0.0, 0.0, math.cos(a) * sp, math.sin(a) * sp, RB, self.look.color(0.0))]
        self.hits = 0
        self.last_hit = -9.0
        self.cleared_at = [-9.0] * len(RADII)
        self.cracks: list[tuple[float, int, int]] = []    # (time, ring, tile) – short flashes

    # ------------------------------------------------------------------ physics
    def tile_of(self, x: float, y: float, k: int) -> int:
        n = self.n_tiles[k]
        return int((math.atan2(y, x) % TAU) / TAU * n) % n

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            for b in self.balls:
                b.move(dt, 0.0)
            return
        k = self.k
        R, w = RADII[k], WIDTH[k]
        inner = R - w / 2
        ring = self.rings[k]
        for b in self.balls:
            b.move(dt, G)
            d = math.hypot(b.x, b.y) or 1e-9
            if d > R + w / 2 + b.rb:
                self.clear(b)
                return
            if d + b.rb < inner or d > R:
                continue
            j = self.tile_of(b.x, b.y, k)
            if ring[j] <= 0:
                continue                    # slipping through a hole
            nx, ny = b.x / d, b.y / d
            if b.vx * nx + b.vy * ny <= 0:
                continue
            b.x, b.y = nx * (inner - b.rb), ny * (inner - b.rb)
            b.vx, b.vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, 0.16, 300)
            s = math.hypot(b.vx, b.vy)
            v = self.v * self.frenzy()
            b.vx, b.vy = b.vx / s * v, b.vy / s * v
            ring[j] -= 1
            self.hits += 1
            self.last_hit = self.t
            self.cracks.append((self.t, k, j))
            self.events.append((self.t, "bounce", self.hits))
            if ring[j] == 0:
                self.events.append((self.t, "clack", j))

    def frenzy(self) -> float:
        """The final ring speeds everyone up as its HP runs out."""
        if self.k < len(RADII) - 1:
            return 1.0
        return 1.0 + 0.5 * min(1.0, (self.t - self.cleared_at[-2]) / 18)

    def hp_left(self) -> int:
        return sum(self.rings[self.k])

    def clear(self, escaper: Ball) -> None:
        k = self.k
        self.cleared_at[k] = self.t
        self.events.append((self.t, "break", k))
        if k == len(RADII) - 1:
            self.finish()
            return
        self.events.append((self.t, "tone", k + 2))
        self.k += 1
        self.v *= 1.13
        if self.k == len(RADII) - 1:
            self.final_hp = self.hp_left()
        for b in self.balls:
            s = math.hypot(b.vx, b.vy) or 1.0
            b.vx, b.vy = b.vx / s * self.v, b.vy / s * self.v
        # a new ball (two before the final ring) bursts out of the centre
        for _ in range(2 if self.k == len(RADII) - 1 else 1):
            a = self.rnd.uniform(0, TAU)
            col = self.look.color(len(self.balls) / 9)
            self.balls.append(Ball(0.0, 0.0, math.cos(a) * self.v, math.sin(a) * self.v, RB, col))
        # balls that are already outside the new ring are pulled back in (never happens with the spacing above)
        R = RADII[self.k] - WIDTH[self.k] / 2 - RB - 1
        for b in self.balls:
            d = math.hypot(b.x, b.y)
            if d > R:
                b.x, b.y = b.x / d * R, b.y / d * R

    def good(self) -> bool:
        return self.end is not None

    # ------------------------------------------------------------------ picture
    def ring_color(self, k: int) -> tuple[int, int, int]:
        if k == len(RADII) - 1 and self.k == k:     # the final ring heats up from gold to red as it breaks
            u = min(1.0, 2.2 * (1 - self.hp_left() / self.final_hp))
            return (255, int(205 - 150 * u), int(70 - 30 * u))
        return self.look.color(k / (len(RADII) - 1) * 0.8, s=0.85, v=1.0)

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "break":
            col = self.ring_color(i)
            p.parts.burst_ring(p.rng, RADII[i], 0, TAU, col, 160 + 30 * i)
            p.punch(0.35 + 0.1 * i)
        elif kind == "clack":
            k = min(self.k, len(RADII) - 1)
            n = self.n_tiles[k]
            a = (i + 0.5) / n * TAU
            p.parts.burst_point(p.rng, math.cos(a) * RADII[k], math.sin(a) * RADII[k], self.ring_color(k), 14, 320)
        elif kind == "finale":
            for c in (self.ring_color(6), GOLD, WHITE):
                p.parts.burst_ring(p.rng, RADII[-1], 0, TAU, c, 220)

    def draw(self, p: Painter) -> None:
        t = self.t
        self.cracks = [c for c in self.cracks if t - c[0] < 0.25]
        flashing = {(k, j): 1 - (t - t0) / 0.25 for t0, k, j in self.cracks}
        for k in range(len(RADII) - 1, -1, -1):
            if k < self.k or (self.end is not None and k == len(RADII) - 1):
                continue
            col = self.ring_color(k)
            n, R, ring = self.n_tiles[k], RADII[k], self.rings[k]
            span = 360 / n
            for j, hp in enumerate(ring):
                if hp <= 0:
                    continue
                f = hp / self.hp0[k]
                if k == self.k:
                    p.ring(R, j * span + 1.2, span - 2.4, _mix(col, 0.3 + 0.7 * f), WIDTH[k],
                           flashing.get((k, j), 0.0) * 0.8)
                else:
                    p.ring(R, j * span + 1.5, span - 3.0, _mix(col, 0.26), WIDTH[k] * 0.6, 0.0)
        p.particles()
        for i, b in enumerate(self.balls):
            p.trail(i, b.x, b.y, b.rb, b.col, 12)
            p.ball(b.x, b.y, b.rb, WHITE, b.col, 3)
            p.glow_disc(b.x, b.y, b.rb * 2.2, _mix(b.col, 0.8))

    def title(self) -> list[str]:
        return ["Can it smash through", "all 7 rings?"]

    def counter(self) -> str:
        if self.end is not None:
            return "7 of 7 rings smashed"
        if self.k == len(RADII) - 1:
            left = self.hp_left()
            if 0 in self.rings[-1]:
                holes = self.rings[-1].count(0)
                return f"{holes} HOLE{'S' if holes > 1 else ''} OPEN!"
            return f"FINAL RING · {left} HP left"
        return f"ring {self.k + 1} of 7 · {len(self.balls)} ball{'s' if len(self.balls) > 1 else ''}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("BROKE FREE!", WHITE), (f"{self.hits} hits", GOLD)]
