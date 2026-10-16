"""TEMPLATE – copy to ytauto/concepts/<kind>.py and turn it into a new concept (files starting with "_" are ignored).

A working example: a ball bounces inside a circle and gets faster with every bounce; at the end it is so fast that
the circle shatters (escalating finale). It shows everything a concept needs:

- physics in step(dt) with self.rnd only (deterministic per seed), visuals with self.look (palette) only
- events for the sound: "bounce" (next melody note), "tone" (own note per index i), "clack", "break" (sparkle),
  and self.finish() for the finale (chord + shake/flash); the soundtrack is generated from these events
- the picture in draw(p) with the Painter helpers, scenery in prepare(p), stamps/particles in on_event(p, ...)
- title() (the question on screen), counter() (live number under it), finale() (big text at the end)
- metadata for Instagram/YouTube: titles, questions, body, playlist, cover_at, trend_words, concept
"""
from __future__ import annotations

import math

from ..sims import TAU, Ball, Painter, Sim, _mix, _reflect


class SpeedDemon(Sim):
    kind = "speeddemon_example"  # unique, lowercase, no spaces – also the playlist/stat key
    concept = {
        "created": "2000-01-01T00:00:00+00:00",  # ISO time – the queue posts the oldest unposted concept first
        "idea": "Every bounce makes the ball a bit faster until the circle shatters",
        "inspiration": "viral 'every bounce speeds up' shorts",
        "finale": "at top speed the circle shatters into particles",
    }
    titles = ["{onscreen}", "Every bounce makes it faster – wait for it"]  # {onscreen} = title() joined, {song} = melody
    questions = ["At what speed would you stop it?"]
    body = "Every bounce makes the ball a little faster and plays the next note of {song}."
    playlist = ("Faster and faster", "Every bounce speeds it up.")
    cover_at = 0.9         # share of the run that makes the best cover frame
    trend_words = ("faster", "speed", "speeds up")
    slowmo = True          # replay the finale moment in slow motion (render decides per seed)
    note_gap = 0.06        # shortest gap between melody notes

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.R = rnd.uniform(400, 440)
        self.acc = rnd.uniform(1.022, 1.032)
        a, sp = rnd.uniform(0, TAU), rnd.uniform(420, 520)
        self.ball = Ball(0.0, -100.0, math.cos(a) * sp, math.sin(a) * sp, 16.0)
        self.top = rnd.uniform(3600, 4200)  # px/s that shatters the circle
        self.start = sp
        self.bounces, self.last_hit = 0, -9.0

    def speed(self) -> float:
        return math.hypot(self.ball.vx, self.ball.vy)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        b = self.ball
        b.move(dt, 900.0)
        d = math.hypot(b.x, b.y) or 1e-9
        if d + b.rb < self.R:
            return
        nx, ny = b.x / d, b.y / d
        b.x, b.y = nx * (self.R - b.rb), ny * (self.R - b.rb)
        if b.vx * nx + b.vy * ny > 0:
            b.vx, b.vy = _reflect(b.vx, b.vy, nx, ny, self.rnd, 0.08, 250)
            k = min(self.acc, 5000 / math.hypot(b.vx, b.vy))
            b.vx, b.vy = b.vx * k, b.vy * k
            self.bounces += 1
            self.last_hit = self.t
            self.events.append((self.t, "bounce", self.bounces))
            if self.speed() >= self.top:
                self.finish()

    def color(self) -> tuple[int, int, int]:
        return self.look.color(min(1.0, self.speed() / self.top))

    def on_event(self, p: Painter, kind: str, i: int) -> None:
        if kind == "bounce" and i % 10 == 0:
            p.punch(0.25)  # small escalation steps on the way
        elif kind == "finale":
            p.parts.burst_ring(p.rng, self.R, 0, TAU, self.color(), 260)

    def draw(self, p: Painter) -> None:
        flash = max(0.0, 1 - (self.t - self.last_hit) / 0.18) * 0.7
        if self.end is None:
            p.ring(self.R + 6, 0, 360, self.color(), 10, flash)
        p.particles()
        b, col = self.ball, self.color()
        p.trail(0, b.x, b.y, b.rb, col, 16)
        p.ball(b.x, b.y, b.rb, (255, 255, 255), col, 3)
        p.glow_disc(b.x, b.y, b.rb * 2, _mix(col, 0.9))

    def title(self) -> list[str]:
        return ["Every bounce makes", "the ball faster"]

    def counter(self) -> str:
        return f"speed ×{self.speed() / self.start:.1f}"  # a live, honest number that builds suspense

    def finale_text(self) -> str:
        return "SHATTERED!"
