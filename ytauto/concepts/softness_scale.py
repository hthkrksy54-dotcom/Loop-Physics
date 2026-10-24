"""Softness scale: the same net of 1,024 spheres, round after round softer – 0 %, 10 %, … 100 % – and every round
the same rain of steel balls and the golden ball drop onto it. Stiff nets fling the balls around like a drum skin,
soft ones swallow them; at 100 % the golden ball tears straight through.

The viral "0 % vs 100 % softness" format rebuilt with the 3D toolkit (ytauto/sim3d.py): the net is real XPBD cloth,
only its compliance changes from round to round, so every difference you see and hear is simulated.
"""
from __future__ import annotations

import numpy as np

from .. import sim3d
from ..sims import H, Sim

N, SIZE = 32, 2.0
FLOOR = -1.3
PHYS = 6                   # physics every 6th step(): 120 Hz
ROUNDS = 11                # 0 %, 10 %, … 100 %
STEEL, GOLD = (226, 230, 240), (255, 190, 40)
# net colour per round: cool and hard -> hot and soft
COOL = ((150, 200, 255), (60, 90, 220))
HOT = ((255, 120, 200), (255, 60, 60))


def _round_len(seed: int) -> float:
    return 5.9 + (seed * 0.37) % 0.6


def _compliance(k: int) -> float:
    """Softness k/10 -> XPBD compliance: from a drum-tight skin to wet cloth (log scale, so the sag grows evenly)."""
    return 10 ** (-5.25 + 1.5 * k / (ROUNDS - 2)) if k < ROUNDS - 1 else 10 ** -2.8


class SoftnessScale(Sim):
    kind = "softness_scale"
    concept = {
        "created": "2026-10-24T04:30:00+00:00",
        "idea": "The same net of 1,024 touching spheres (3D) gets softer every round – 0 %, 10 %, … 100 % – and every "
                "round the same rain of steel balls and the golden ball drop onto it: hard nets fling them around like "
                "a drum skin (a rattle of notes), soft ones swallow them silently, deeper and deeper.",
        "inspiration": "the viral '0% vs 100% softness' soft-body clips (Blender softness scales on TikTok, Reels "
                       "and Snapchat) rebuilt as one simulated material in the @particlesflow look",
        "finale": "100 %: the net sags like wet cloth, the golden ball lands and tears straight through, the whole "
                  "pile pours onto the platform (slow motion)",
    }
    titles = ["{onscreen}", "Same net, 0% to 100% softness – watch what 100% does",
              "The same balls on 11 nets from 0% to 100% softness"]
    questions = ["Which softness was the most satisfying?", "At what % did you think it would tear?",
                 "Should we try 200% next?"]
    body = ("The same net of 1,024 spheres, softer every round from 0% to 100% – and every round the same steel balls "
            "and the golden ball drop on it. Every landing plays the next note of {song}. Everything is simulated in "
            "3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("softness", "0%", "100%", "soft body", "3d", "satisfying", "simulation", "net")
    slowmo = True
    note_gap = 0.07
    finale_punch = 1.2
    full_frame = True
    experiment = "softness"
    cta_y = 1560
    run_ranges = [(61, 67), (64, 71)]

    @staticmethod
    def planned_end(seed: int) -> float:
        return (ROUNDS - 1) * _round_len(seed) + 4.2

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.D = _round_len(seed)
        # one rain pattern for every round, so the rounds are a fair comparison
        self.rain = [(0.05 + 0.3 * j, rnd.uniform(-0.55, 0.55), rnd.uniform(-0.55, 0.55), rnd.uniform(0.09, 0.11))
                     for j in range(10)]
        self.gold_at = 3.35
        self.gold_xz = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12))
        self.round = -1
        self.k = 0
        self.rt = 0.0
        self.last_note = -9.0
        self.weak = None
        self.flash_at = -9.0
        top, deep = self.look.rnd.choice([sim3d.GRADIENTS[1], sim3d.GRADIENTS[4]])
        self.cool = (top, deep)
        self.tint = self.look.rnd.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])
        self._new_round()

    def _new_round(self) -> None:
        self.round += 1
        self.rt = 0.0
        self.net = sim3d.Sheet(N, SIZE, 0.0, iters=12, compliance=_compliance(self.round))
        self.net.pin_border()
        self.balls = sim3d.Balls(14)
        self.bprev = self.balls.p.copy()
        self.next = 0
        self.gold = -1
        self.prev_touch = np.zeros(14, np.int8)
        if self.round == ROUNDS - 1:
            self.net.tear[:] = 40.0   # the rain must not tear it – the golden ball does
        u = self.round / (ROUNDS - 1)
        top = sim3d.lerp_col(self.cool[0], HOT[0], u ** 1.3)
        deep = sim3d.lerp_col(self.cool[1], HOT[1], u ** 1.3)
        self.shades = [sim3d.lerp_col(top, deep, i / 23) for i in range(24)]
        if self.round:
            self.events.append((self.t, "break", self.round))  # the old pile pops, the next net snaps in

    def step(self, dt: float) -> None:
        self.t += dt
        self.k += 1
        if self.end is None and self.round < ROUNDS - 1 and self.t >= (self.round + 1) * self.D:
            self._new_round()
        if self.k % PHYS == 0:
            self._physics(PHYS * dt)

    def _physics(self, h: float) -> None:
        self.rt += h
        b = self.balls
        while self.next < len(self.rain) and self.rain[self.next][0] <= self.rt:
            _, x, z, r = self.rain[self.next]
            b.add((x, 1.0, z), (0.0, -1.5, 0.0), r, 25.0, STEEL)
            self.next += 1
        if self.gold < 0 and self.rt >= self.gold_at:
            self.gold = b.add((self.gold_xz[0], 1.25, self.gold_xz[1]), (0.0, -3.0, 0.0), 0.2, 260.0, GOLD)
        last = self.round == ROUNDS - 1
        self.bprev = b.p.copy()
        vy = b.v[:, 1].copy()
        broke = self.net.step(h, b, FLOOR, damp=0.997 if self.end is None else 0.985)
        new = (b.touch > 0) & (self.prev_touch == 0) & (vy < -0.5) & b.on
        for i in np.nonzero(new)[0]:
            if self.end is not None:
                break
            hero = i == self.gold or vy[i] < -1.6
            if hero and self.t - self.last_note >= self.note_gap:
                self.events.append((self.t, "bounce", int(i)))
                self.last_note = self.t
            else:
                self.events.append((self.t, "clack", int(i)))
        self.prev_touch = b.touch.copy()
        if last and self.gold >= 0 and self.weak is None and b.touch[self.gold]:
            self.weak = self.t
        if self.weak is not None:  # 100 %: the net gives way under the golden ball, the hole keeps growing
            gx, gz = b.p[self.gold, 0], b.p[self.gold, 2]
            P = self.net.P.reshape(-1, 3)
            reach = min(0.9, 0.25 + 0.6 * (self.t - self.weak))
            self.net.tear[np.hypot(P[:, 0] - gx, P[:, 2] - gz) < reach] = 1.25
        if broke and self.end is None and last:
            self.events.append((self.t, "break", 99))
            self.finish()
        if self.end is None and last and self.rt > 4.1:  # safety: the finale always comes
            self.events.append((self.t, "break", 99))
            self.finish()

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.5, 0), dist=10.8, yaw=0.62, pitch=0.5, fov=28, cy=H * 0.55)
        a = SIZE / 2
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=1.15, thick=0.16, tint=self.tint,
                                   posts=[(-a, -a), (a, -a), (a, a), (-a, a)], post_top=0.0, frame_y=-0.03,
                                   frame_half=a)

    def render(self, p):
        a = (self.k % PHYS) / PHYS
        P = self.net.lerp(a).reshape(-1, 3)
        b = self.balls
        on = np.nonzero(b.on)[0]
        B = self.bprev[on] + (b.p[on] - self.bprev[on]) * a
        u = np.clip(-P[:, 1] / 1.1, 0, 1)
        cols = [self.shades[int(v * 23 + 0.5)] for v in u] + [b.col[i] for i in on]
        pts = np.vstack([P, B])
        rad = np.concatenate([np.full(len(P), self.net.r), b.r[on]])
        img = self.studio.back.copy()
        img = self.studio.shadows(img, pts, rad)
        self.studio.spheres(img, pts, rad, cols)
        img.paste(self.studio.front, (0, 0), self.studio.front)
        return img

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.15 if i < 99 else 0.8)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is not None and self.t >= self.end:
            p.big_text(d, self.finale(), self.t - self.end, cy=330)
            return
        super().draw_text(p, d)
        u = self.round / (ROUNDS - 1)
        col = sim3d.lerp_col((170, 215, 255), (255, 110, 170), u)
        pct = f"{self.round * 10}%"
        pop = max(0.0, 1 - (self.t - self.round * self.D) / 0.35)
        size = int(150 + 30 * pop) // 10 * 10
        font = p.f_big.get(size, p.f_big[150])
        w = d.textlength(pct, font=font)
        d.text(((1080 - w) / 2, 520), pct, font=font, fill=col, stroke_width=5, stroke_fill=(0, 0, 0))

    def title(self) -> list[str]:
        return ["Same net, same balls", "0% to 100% softness"]

    def counter(self) -> str:
        if self.round == ROUNDS - 1:
            return "MAXIMUM SOFTNESS"
        return f"softness {self.round * 10}% · round {self.round + 1}/{ROUNDS}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("100% SOFT =", (255, 255, 255)), ("TORN!", GOLD)]
