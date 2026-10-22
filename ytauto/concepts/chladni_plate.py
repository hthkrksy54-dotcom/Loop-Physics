"""Chladni plate: every note thumps a plate made of 1,681 spheres – the golden beads on it hop off everything that
vibrates and gather on the silent lines, until the sound has drawn a pattern. Six patterns, each more
intricate; at the end one big thump throws every bead into the air and they rain back scattered – the first frame
again (a seamless loop).

3D (ytauto/sim3d.py look): the plate is a grid of glossy spheres on a central post, coloured by how it moves (cyan up,
magenta down) with every thump; the beads are small golden spheres. The vibration is the plate's mode shape
(cos·cos − cos·cos, the classic Chladni figure), the beads are simulated: every thump kicks them in proportion to
how much the plate moves under them, so they settle on the nodal lines by themselves. Short format experiment.
"""
from __future__ import annotations

import math

import numpy as np

from .. import sim3d
from ..sims import H, Sim

PHYS = 6                   # beads every 6th step(): 120 Hz
NG = 41                    # plate spheres per side
HALF = 1.0                 # plate from -1 to 1 m
FLOOR = -0.75              # platform top under the post
NB = 1200                  # golden beads
RB = 0.019
G = 9.81
GOLD = (255, 205, 70)
SHADES = 12
# (n, m) mode pairs, simple to intricate
MODES = [[(1, 2), (1, 3)], [(2, 3), (1, 4)], [(2, 4), (3, 4)], [(1, 5), (2, 5)], [(3, 5), (4, 5)], [(2, 7), (3, 7)],
         [(4, 7), (5, 6)]]


def _mode(n: int, m: int, x, z, sign: int = -1):
    u, v = (x + HALF) / (2 * HALF), (z + HALF) / (2 * HALF)
    return (np.cos(n * math.pi * u) * np.cos(m * math.pi * v)
            + sign * np.cos(m * math.pi * u) * np.cos(n * math.pi * v)) / 2


def _plan(seed: int) -> list[float]:
    """Length of each pattern stage (s) – fixed per seed, so the run length is known up front."""
    r = np.random.default_rng(seed)  # only for the plan; the physics uses self.rnd
    return [float(x) for x in r.uniform(3.0, 3.9, 6)]


class ChladniPlate(Sim):
    kind = "chladni_plate"
    concept = {
        "created": "2026-10-22T04:30:00+00:00",
        "idea": "A Chladni plate made of 1,681 spheres (3D) with 1,200 golden beads on it: every note thumps the "
                "plate, the beads hop off everything that vibrates and gather on the silent lines – six "
                "patterns, each more intricate, then one big thump scatters them for the loop.",
        "inspiration": "viral cymatics / Chladni plate videos (sand drawing patterns to a tone) and the 3D "
                       "particle reels of @particlesflow",
        "finale": "the most intricate pattern, then one big thump throws every bead into the air and they rain "
                  "back scattered – exactly the first frame (seamless loop)",
    }
    titles = ["{onscreen}", "Sound draws these patterns – which one is your favourite?",
              "1,200 golden beads, one plate, six patterns"]
    questions = ["Which pattern was the best – 1 to 6?", "Did you see the pattern coming?"]
    body = ("Every note of {song} thumps a plate made of 1,681 spheres: the golden beads hop off everything that "
            "vibrates and gather on the silent lines, until the sound has drawn a pattern. Everything is simulated "
            "in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.8
    trend_words = ("cymatics", "chladni", "sound", "pattern", "3d", "satisfying", "asmr")
    slowmo = False
    note_gap = 0.06
    finale_punch = 0.7
    full_frame = True
    min_video = 20
    run_ranges = [(17, 22), (20, 26), (24, 32)]
    experiment = "loop"
    cta_y = 1560

    @staticmethod
    def planned_end(seed: int) -> float:
        return sum(_plan(seed))

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.stages = _plan(seed)
        sign = rnd.choice([-1, 1])  # alternating + / − figures: a new set of silent lines every time
        self.modes = [(*rnd.choice(MODES[k]), sign * (-1) ** k) for k in range(len(self.stages))]
        self.ends = list(np.cumsum(self.stages))
        self.stage = 0
        g = np.linspace(-HALF, HALF, NG)
        self.gx, self.gz = np.meshgrid(g, g)
        self.gx, self.gz = self.gx.ravel(), self.gz.ravel()
        self.pr = HALF / (NG - 1)                          # plate sphere radius (they touch)
        self.rest = self.pr + RB                           # bead centre above the plate when resting
        self.bp = np.zeros((NB, 3))
        self.bp[:, 0] = [rnd.uniform(-0.96, 0.96) for _ in range(NB)]
        self.bp[:, 2] = [rnd.uniform(-0.96, 0.96) for _ in range(NB)]
        self.bp[:, 1] = self.rest
        self.bv = np.zeros((NB, 3))
        self.bprev = self.bp.copy()
        self.k = 0
        self.thump_t = -9.0       # last thump (for the plate's ringing)
        self.thump_mode = self.modes[0]
        self.thump_amp = 0.0
        self.thumps = 0
        self.last_stage = 0
        self.firsts: set[int] = set()
        self.next_thump = 0.0
        self.big = False
        self.tint = self.look.rnd.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])
        up, down = self.look.rnd.choice([((90, 230, 255), (255, 80, 200)), ((120, 255, 170), (176, 112, 255)),
                                         ((90, 200, 255), (255, 140, 40))])
        base = (52, 56, 72)
        self.cols_up = [sim3d.lerp_col(base, up, i / (SHADES - 1)) for i in range(SHADES)]
        self.cols_dn = [sim3d.lerp_col(base, down, i / (SHADES - 1)) for i in range(SHADES)]

    def interval(self) -> float:
        """Time between thumps: quicker with every pattern."""
        return 0.3 - 0.028 * self.stage

    def step(self, dt: float) -> None:
        self.t += dt
        self.k += 1
        if self.end is None:
            if self.stage < len(self.stages) and self.t >= self.ends[self.stage]:
                self.stage += 1
                if self.stage == len(self.stages):
                    self._scatter()
            if self.end is None and self.t >= self.next_thump:
                self._thump()
        if self.k % PHYS == 0:
            self._beads(PHYS * dt)

    def _thump(self) -> None:
        n, m, sg = self.modes[self.stage]
        self.thump_t, self.thump_mode, self.thump_amp = self.t, (n, m, sg), 0.07
        self.thumps += 1
        if self.stage != self.last_stage:
            self.last_stage = self.stage
            self.firsts.add(self.thumps)
        self.next_thump = self.t + self.interval()
        self.events.append((self.t, "bounce", self.thumps))
        x, z = self.bp[:, 0], self.bp[:, 2]
        top = float(np.abs(_mode(n, m, self.gx, self.gz, sg)).max())
        f = _mode(n, m, x, z, sg) / top
        a = np.abs(f)
        rest = self.bp[:, 1] <= self.rest + 1e-3
        e = 1e-3  # downhill on |f|: towards the silent lines
        gx = (np.abs(_mode(n, m, x + e, z, sg)) / top - a) / e
        gz = (np.abs(_mode(n, m, x, z + e, sg)) / top - a) / e
        gn = np.hypot(gx, gz) + 1e-9
        ang = np.array([self.rnd.uniform(0, 2 * math.pi) for _ in range(NB)])
        if self.thumps in self.firsts:  # a new note: the old figure is shaken apart first
            vx, vz, vy = np.cos(ang) * 0.5 * (0.4 + a), np.sin(ang) * 0.5 * (0.4 + a), 1.0 + 1.2 * a
        else:
            hop = a * 0.9
            jit = np.maximum(a, 0.1) * 0.4  # a little jitter everywhere keeps the lines thick, not single file
            vx = -gx / gn * hop * 0.7 + np.cos(ang) * jit
            vz = -gz / gn * hop * 0.7 + np.sin(ang) * jit
            vy = 0.35 + 1.6 * a
        self.bv[rest, 0] = vx[rest]
        self.bv[rest, 2] = vz[rest]
        self.bv[rest, 1] = vy[rest]

    def _scatter(self) -> None:
        """The big thump: every bead flies up and lands on a random spot – the first frame again."""
        self.thump_t, self.thump_mode, self.thump_amp = self.t, None, 0.16
        self.events.append((self.t, "break", 0))
        self.finish()
        rnd = self.rnd
        for i in range(NB):
            vy = rnd.uniform(2.4, 3.4)
            tf = 2 * vy / G
            tx, tz = rnd.uniform(-0.96, 0.96), rnd.uniform(-0.96, 0.96)
            self.bv[i] = ((tx - self.bp[i, 0]) / tf, vy, (tz - self.bp[i, 2]) / tf)
            self.bp[i, 1] = self.rest + 1e-3

    def _beads(self, h: float) -> None:
        self.bprev = self.bp.copy()
        P, V = self.bp, self.bv
        air = P[:, 1] > self.rest + 1e-4
        V[air, 1] -= G * h
        P += V * h
        land = P[:, 1] <= self.rest
        P[land, 1] = self.rest
        V[land] = 0.0
        for c in (0, 2):
            out = np.abs(P[:, c]) > 0.97
            P[out, c] = np.sign(P[out, c]) * 0.97
            V[out, c] *= -0.5

    def good(self) -> bool:
        return True

    # ---------------------------------------------------------------- picture

    def _plate(self, t: float):
        """Plate height (and its sign) at time t: the last thump rings and dies away."""
        tau = t - self.thump_t
        if tau < 0 or tau > 0.6:
            return np.zeros(len(self.gx))
        env = self.thump_amp * math.exp(-7 * tau) * math.cos(2 * math.pi * 7 * tau)
        if self.thump_mode is None:  # the big thump: the whole plate jumps
            return np.full(len(self.gx), env * 0.6)
        return env * _mode(*self.thump_mode, self.gx, self.gz)

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.2, 0), dist=7.9, yaw=0.62, pitch=0.8, fov=28, cy=H * 0.54)
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=0.55, thick=0.14, tint=self.tint, posts=[(0.0, 0.0)],
                                   post_top=0.0)

    def render(self, p):
        a = (self.k % PHYS) / PHYS
        y = self._plate(self.t)
        plate = np.stack([self.gx, y, self.gz], 1)
        B = self.bprev + (self.bp - self.bprev) * a
        rest = B[:, 1] <= self.rest + 1e-3
        B = B.copy()
        if rest.any() and self.thump_mode is not None:  # resting beads ride the plate
            tau = self.t - self.thump_t
            if 0 <= tau <= 0.6:
                env = self.thump_amp * math.exp(-7 * tau) * math.cos(2 * math.pi * 7 * tau)
                B[rest, 1] += env * _mode(*self.thump_mode, B[rest, 0], B[rest, 2])
        amp = np.clip(np.abs(y) / 0.05, 0, 1)
        cols = [(self.cols_up if v >= 0 else self.cols_dn)[int(q * (SHADES - 1) + 0.5)] for v, q in zip(y, amp)]
        cols += [GOLD] * NB
        pts = np.vstack([plate, B])
        rad = np.concatenate([np.full(len(plate), self.pr), np.full(NB, RB)])
        img = self.studio.back.copy()
        img = self.studio.shadows(img, plate[::7], np.full(len(plate[::7]), self.pr * 2.4), strength=0.35)
        self.studio.spheres(img, pts, rad, cols)
        img.paste(self.studio.front, (0, 0), self.studio.front)
        return img

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "bounce" and i in self.firsts:  # a new pattern starts
            p.punch(0.3)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["What will the sound", "draw next?"]

    def counter(self) -> str:
        s = min(self.stage, len(self.stages) - 1)
        if s == len(self.stages) - 1 and self.end is None:
            return f"LAST PATTERN · {s + 1} of {len(self.stages)}"
        return f"pattern {s + 1} of {len(self.stages)}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("WHICH ONE", (255, 255, 255)), ("WAS BEST?", GOLD)]
