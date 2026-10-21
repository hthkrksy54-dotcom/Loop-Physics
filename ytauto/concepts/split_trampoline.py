"""Split trampoline: every bounce of the golden ball on a trampoline of 1,296 spheres adds a new ball – faster and
faster, until the frame can't hold the weight and the whole net drops.

3D (ytauto/sim3d.py): the trampoline is a pinned net of touching spheres that dents under every landing (coloured by
depth); the golden ball bounces lower and quicker as the net fills up, every one of its landings plays the next note
and pops out a new ball, all the other balls keep bouncing like popcorn (wooden clacks). At the limit the frame lets
go and the net falls onto the platform like a sack around the pile.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

N, SIZE = 36, 2.0          # 36×36 spheres on a 2 m trampoline
FLOOR = -1.25              # platform top (m)
PHYS = 6                   # physics every 6th step(): 120 Hz
CAP = 240                  # ball slots
GOLD = (255, 196, 48)
RG, RB = 0.11, 0.058      # radius of the golden ball / the others


def _plan(seed: int) -> tuple[int, float]:
    """How many balls the frame holds and how hard the golden ball starts – fixed per seed."""
    goal = (130, 140, 150, 160, 170, 180)[seed % 6]
    return goal, 2.6 + 0.1 * ((seed * 7) % 5)


class SplitTrampoline(Sim):
    kind = "split_trampoline"
    concept = {
        "created": "2026-10-21T03:40:00+00:00",
        "idea": "A trampoline made of 1,296 touching spheres (3D): every landing of the golden ball pops out a new "
                "ball, the golden ball bounces lower and faster as the net fills, all the others keep bouncing like "
                "popcorn – the counter races to the frame's limit.",
        "inspiration": "viral '1 ball becomes 100' multiply shorts and the 3D particle-cloth reels of @particlesflow",
        "finale": "at the limit the frame lets go: the whole net drops onto the platform and wraps the pile like a "
                  "sack (slow motion)",
    }
    titles = ["{onscreen}", "Every golden bounce adds a ball – can the trampoline hold them all?",
              "1 golden ball, 1,296-sphere trampoline – watch the counter"]
    questions = ["How many balls did you think it would hold?", "Which ball did you follow?"]
    body = ("A trampoline made of 1,296 touching spheres. Every time the golden ball lands, it plays the next note of "
            "{song} and a new ball pops out – the others keep bouncing (wooden clacks) until the frame gives up. "
            "Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.9
    trend_words = ("3d", "trampoline", "multiply", "1 ball", "simulation", "satisfying")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.1
    full_frame = True
    tempo = "fast"
    cta_y = 590

    def __init__(self, seed: int):
        super().__init__(seed)
        self.goal, self.v0 = _plan(seed)
        self.net = sim3d.Sheet(N, SIZE, 0.0, iters=10, compliance=6e-5)
        self.net.pin_border()
        self.balls = b = sim3d.Balls(CAP)
        self.fresh = np.zeros(CAP, bool)
        self.bprev = b.p.copy()
        self.gold = b.add((0.0, 0.75, 0.0), (0.0, -2.5, 0.0), RG, 200.0, GOLD)  # heavy: it ploughs through the crowd
        look = self.look.rnd
        cool = look.choice([((90, 230, 255), (150, 70, 255)), ((176, 112, 255), (64, 92, 255)),
                            ((150, 240, 70), (20, 170, 120))])  # cool colours, so the golden ball stands out
        self.palette = [sim3d.lerp_col(*cool, look.random()) for _ in range(10)] + [(236, 240, 248)] * 2
        for k in range(5):  # a few balls already in the air: something happens from the first frame
            a = k * 2 * math.pi / 5 + 0.4
            self._spawn((0.42 * math.cos(a), 0.45 + 0.12 * k, 0.42 * math.sin(a)), (0.0, -1.0, 0.0))
        self.k = 0
        self.prev_sheet = np.zeros(CAP, bool)
        self.launched = np.zeros(CAP, bool)
        self.contact = np.zeros(CAP)
        self.gold_hits = 0
        self.drop = None
        top, deep = self.look.rnd.choice([((255, 120, 200), (255, 140, 40)), ((255, 80, 80), (255, 190, 60)),
                                          ((255, 214, 64), (255, 92, 28))])
        self.shades = [sim3d.lerp_col(top, deep, i / 23) for i in range(24)]
        self.tint = self.look.rnd.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])

    def _spawn(self, p, v) -> None:
        b = self.balls
        if b.n < CAP:
            self.fresh[b.n] = True
            b.add(p, v, RB, 6.0, self.palette[b.n % len(self.palette)])

    @property
    def count(self) -> int:
        return self.balls.n

    def step(self, dt: float) -> None:
        self.t += dt
        self.k += 1
        if self.k % PHYS == 0:
            self._physics(PHYS * dt)

    def _launch(self, i: int, speed: float) -> None:
        """The trampoline throws the ball back up, aimed at a random spot on the net."""
        b, rnd = self.balls, self.rnd
        flight = 2 * speed / 9.81
        lim = 0.25 if i == self.gold else 0.72
        tx, tz = rnd.uniform(-lim, lim), rnd.uniform(-lim, lim)
        b.v[i] = ((tx - b.p[i, 0]) / flight, speed, (tz - b.p[i, 2]) / flight)
        self.launched[i] = True

    def _physics(self, h: float) -> None:
        b = self.balls
        self.bprev = b.p.copy()
        vy = b.v[:, 1].copy()
        self.net.step(h, b, FLOOR, damp=0.996 if self.end is None else 0.99)
        if self.end is None:  # the frame's invisible side walls keep the balls above the net
            for c in (0, 2):
                out = np.abs(b.p[:, c]) > 0.9
                b.v[out, c] = -np.sign(b.p[out, c]) * np.abs(b.v[out, c])
        sheet = ((b.touch & 1) > 0) & b.on
        new = sheet & ~self.prev_sheet & (vy < -0.8)
        self.contact = np.where(sheet, self.contact + h, 0.0)
        self.launched &= sheet & (self.contact < 0.25)  # buried under the pile: the trampoline throws it again
        self.prev_sheet = sheet
        if self.end is not None:
            return
        fill = min(1.0, self.count / self.goal)
        for i in np.nonzero(new)[0]:
            if i == self.gold:
                self.gold_hits += 1
                self.events.append((self.t, "bounce", self.gold_hits))
                g = b.p[i]
                a = self.rnd.uniform(0, 2 * math.pi)
                self._spawn((g[0] + 0.17 * math.cos(a), g[1] + 0.1, g[2] + 0.17 * math.sin(a)),
                            (0.9 * math.cos(a), 2.6 + self.rnd.uniform(0, 1.2), 0.9 * math.sin(a)))
                if self.count >= self.goal:
                    self._overload()
                    return
            elif self.fresh[i]:  # a newborn ball's first landing is a hero hit too
                self.fresh[i] = False
                self.events.append((self.t, "land", int(i)))
            elif vy[i] < -1.2:
                self.events.append((self.t, "clack", int(i)))
        ready = sheet & ~self.launched & ((b.v[:, 1] > 0.05) | (self.contact > 0.12))
        ready[self.gold] = sheet[self.gold] and not self.launched[self.gold] and self.contact[self.gold] > 0.03
        for i in np.nonzero(ready)[0]:
            if i == self.gold:  # lower and quicker as the net fills up
                self._launch(i, self.v0 * (1 - 0.35 * fill))
            else:
                self._launch(i, self.rnd.uniform(1.2, 2.3))  # lower than the golden one

    def _overload(self) -> None:
        self.events.append((self.t, "break", 0))
        self.finish()
        self.net.w[:] = 1.0  # the frame lets go: the net drops with everything on it

    def good(self) -> bool:
        return self.count >= self.goal

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.4, 0), dist=10.6, yaw=0.62, pitch=0.6, fov=28, cy=H * 0.55)
        a = SIZE / 2
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=1.2, thick=0.16, tint=self.tint,
                                   posts=[(-a, -a), (a, -a), (a, a), (-a, a)], post_top=0.0, frame_y=-0.03,
                                   frame_half=a)

    def render(self, p):
        a = (self.k % PHYS) / PHYS
        P = self.net.lerp(a).reshape(-1, 3)
        b = self.balls
        on = np.nonzero(b.on)[0]
        B = self.bprev[on] + (b.p[on] - self.bprev[on]) * a
        u = np.clip(-P[:, 1] / 0.35, 0, 1)
        cols = [self.shades[int(v * 23 + 0.5)] for v in u] + [b.col[i] for i in on]
        pts = np.vstack([P, B])
        rad = np.concatenate([np.full(len(P), self.net.r), b.r[on]])
        img = self.studio.back.copy()
        img = self.studio.shadows(img, pts, rad)
        self.studio.spheres(img, pts, rad, cols)
        img.paste(self.studio.front, (0, 0), self.studio.front)
        g = self.gold  # a warm halo, so the eye finds the golden ball in the crowd
        x, y, _, sc = self.cam.project((self.bprev[g] + (b.p[g] - self.bprev[g]) * a)[None, :])
        rr = float(RG * sc[0]) * 1.7
        halo = Image.new("RGB", (W // 4, H // 4))
        ImageDraw.Draw(halo).ellipse(((x[0] - rr) / 4, (y[0] - rr) / 4, (x[0] + rr) / 4, (y[0] + rr) / 4),
                                     fill=(80, 50, 6))
        halo = halo.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(img, halo)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["Every golden bounce", "adds a new ball"]

    def counter(self) -> str:
        left = self.goal - self.count
        if self.end is None and left <= 10:
            return f"{self.count} balls · {left} TO THE LIMIT"
        return f"{self.count} / {self.goal} balls"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("THE FRAME", (255, 255, 255)), ("GAVE UP!", GOLD)]
