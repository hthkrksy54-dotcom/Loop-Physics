"""Giant net: a net of 1,296 spheres catches a rain of steel balls – until the golden giant drops.

The first concept built with the 3D toolkit (ytauto/sim3d.py): the net is a sheet of touching spheres that stretches,
sags (coloured by depth) and finally tears; everything is simulated with position based dynamics and rendered as
shaded spheres on a platform – nothing is animated by hand.
"""
from __future__ import annotations

import numpy as np

from .. import sim3d
from ..sims import H, Sim

N, SIZE = 36, 2.0          # 36×36 spheres on a 2 m net
FLOOR = -1.3               # platform top (m) – room for the pile to pour through the torn net
PHYS = 6                   # physics every 6th step(): 120 Hz
STEEL, GOLD = (226, 230, 240), (255, 190, 40)


def _giant_at(seed: int) -> float:
    """When the golden giant drops – fixed per seed, so the run length is known before simulating."""
    return 58.5 + (seed * 37) % 23


class GiantNet(Sim):
    kind = "giant_net"
    concept = {
        "created": "2026-10-20T08:30:00+00:00",
        "idea": "A net of 1,296 touching spheres (3D, simulated like cloth) catches a rain of steel balls that "
                "gets faster and faster – the net sags deeper with every ball, coloured by depth – until a golden "
                "giant drops onto the pile.",
        "inspiration": "viral 3D particle-sheet simulations (spheres that behave like cloth on a platform)",
        "finale": "the golden giant lands, the net tears open and the whole pile pours through onto the platform "
                  "(slow motion)",
    }
    titles = ["{onscreen}", "1,296 balls make a net – then the golden giant drops", "Can this net hold the giant?"]
    questions = ["How many balls did you think it would hold?", "Did you expect it to tear right there?"]
    body = ("A net made of 1,296 touching spheres catches a rain of steel balls – every landing plays the next "
            "note of {song} – and sags deeper with every ball until the golden giant drops. Everything is "
            "simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("3d", "net", "cloth", "particles", "simulation")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    cta_y = 590          # between the finale text and the net, clear of the pile

    @staticmethod
    def planned_end(seed: int) -> float:
        return _giant_at(seed) + 0.6

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.net = sim3d.Sheet(N, SIZE, 0.0, iters=10, compliance=5e-5)
        self.net.pin_border()
        self.balls = sim3d.Balls(220)
        self.bprev = self.balls.p.copy()
        self.T = _giant_at(seed)
        self.drops = [(t, rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0.06, 0.075))
                      for t in (0.05, 0.3, 0.55)]  # three at once: something happens from the first frame
        t = 1.2
        while t < self.T - 2.0 and len(self.drops) < 210:  # then the rain gets faster and faster
            self.drops.append((t, rnd.uniform(-0.72, 0.72), rnd.uniform(-0.72, 0.72), rnd.uniform(0.06, 0.075)))
            t += (0.13 + 0.95 * (1 - t / self.T) ** 1.8) * self.T / 60
        self.next = 0
        self.giant = -1
        self.weak = None           # time the giant first touched the pile / net
        self.k = 0
        self.landed = 0
        self.prev_touch = np.zeros(220, np.int8)
        self.counted = np.zeros(220, bool)
        top, deep = self.look.rnd.choice(sim3d.GRADIENTS)
        self.shades = [sim3d.lerp_col(top, deep, i / 23) for i in range(24)]
        self.tint = self.look.rnd.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])

    def step(self, dt: float) -> None:
        self.t += dt
        self.k += 1
        if self.k % PHYS == 0:
            self._physics(PHYS * dt)

    def _physics(self, h: float) -> None:
        b = self.balls
        while self.next < len(self.drops) and self.drops[self.next][0] <= self.t:
            _, x, z, r = self.drops[self.next]
            b.add((x, 1.1, z), (0.0, -1.2, 0.0), r, 25.0, STEEL)
            self.next += 1
        if self.giant < 0 and self.t >= self.T:
            self.giant = b.add((0.05, 1.45, -0.05), (0.0, -4.0, 0.0), 0.2, 300.0, GOLD)
        self.bprev = b.p.copy()
        vy = b.v[:, 1].copy()
        broke = self.net.step(h, b, FLOOR, damp=0.996 if self.end is None else 0.985)
        new = (b.touch > 0) & (self.prev_touch == 0) & (vy < -0.7) & b.on
        for i in np.nonzero(new)[0]:
            if self.end is None:
                self.events.append((self.t, "bounce", int(i)))
            if i != self.giant and not self.counted[i]:
                self.counted[i] = True
                self.landed += 1
        self.prev_touch = b.touch.copy()
        if self.giant >= 0 and self.weak is None and b.touch[self.giant]:
            self.weak = self.t
        if self.weak is not None:  # the net gives way under the giant, and the hole keeps growing
            gx, gz = b.p[self.giant, 0], b.p[self.giant, 2]
            P = self.net.P.reshape(-1, 3)
            reach = min(0.85, 0.3 + 0.5 * (self.t - self.weak))
            self.net.tear[np.hypot(P[:, 0] - gx, P[:, 2] - gz) < reach] = 1.3
            net = self.net  # spheres torn loose from every link just drop instead of flying off
            links = np.bincount(net.la, net.alive, N * N) + np.bincount(net.lb, net.alive, N * N)
            loose = (links == 0).reshape(N, N)
            net.V[loose, 0] *= 0.8
            net.V[loose, 2] *= 0.8
        if broke and self.end is None:
            self.events.append((self.t, "break", 0))
            self.finish()

    def good(self) -> bool:
        return self.landed >= 60

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.45, 0), dist=11.5, yaw=0.62, pitch=0.52, fov=28, cy=H * 0.52)
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
        u = np.clip(-P[:, 1] / 0.8, 0, 1)
        cols = [self.shades[int(v * 23 + 0.5)] for v in u] + [b.col[i] for i in on]
        pts = np.vstack([P, B])
        rad = np.concatenate([np.full(len(P), self.net.r), b.r[on]])
        img = self.studio.back.copy()
        img = self.studio.shadows(img, pts, rad)
        self.studio.spheres(img, pts, rad, cols)
        img.paste(self.studio.front, (0, 0), self.studio.front)
        return img

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)  # up top, so the tear stays in view

    def title(self) -> list[str]:
        return ["Can the net hold", "the golden giant?"]

    def counter(self) -> str:
        if self.giant >= 0 and self.end is None:
            return "THE GIANT IS COMING"
        return f"{self.landed} ball{'' if self.landed == 1 else 's'} in the net"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("THE NET", (255, 255, 255)), ("TORE!", GOLD)]
