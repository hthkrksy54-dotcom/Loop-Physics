"""Critical mass: a toy chain reaction on a platform full of glossy "fuel" spheres (3D). A neutron hits a sphere,
the sphere splits and throws out 2–3 new neutrons, which split the next ones … Grey bead walls (control rods) swallow
neutrons and keep the chain small. Every round the press pulls rods out of the grid: the chains grow from a few
splits to hundreds – and in the last round there are no rods left at all.

The idea is a reinterpretation of the viral chain-reaction / fission simulations in the @particlesflow look: the
fuel lattice, the rods, the neutrons and every split are simulated (a neutron really has to hit a sphere), nothing
is animated by hand. Melody on the splits (the hero is the chain), clacks for splits closer than note_gap, a tone for
every sphere that drops back into the grid when it is refilled, a crack when rods are pulled.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

SP = 0.12                  # lattice spacing (m)
NL = 21                    # lattice sites per side (rod lines take some of them)
RA = 0.044                 # fuel sphere radius
RN = 0.014                 # neutron radius
VN = 0.95                  # neutron speed (m/s)
RR = 0.03                  # rod bead radius
HALF = 1.32                # platform half size
PHYS = 6                   # physics every 6th step (120 Hz)
NEUTRON = (215, 240, 255)
ROD = (120, 126, 140)
ROUND_T = [12.0, 12.0, 12.5, 13.0]   # rounds with rods; the last round has none and runs until the meltdown
SHADES = 12


def _rods(r: int) -> tuple[list[float], list[float]]:
    """Rod lines (x positions, z positions) that are still in during round r (0-based); the last round has none."""
    a, b = (-6, -2, 2, 6), (-2, 2)
    plan = [(a, a), (a, b), (b, b), (b, (2,))]
    xs, zs = plan[r] if r < len(plan) else ((), ())
    return [k * SP for k in xs], [k * SP for k in zs]


class CriticalMass(Sim):
    kind = "critical_mass"
    concept = {
        "created": "2026-10-26T05:10:00+00:00",
        "idea": "A toy chain reaction in 3D: a platform full of glossy fuel spheres, every neutron that hits one splits "
                "it into two halves and 2–3 new neutrons. Grey bead walls (control rods) swallow neutrons. Every round "
                "rods are pulled out – the chains grow from a dozen splits to hundreds – and the last round has no "
                "rods at all.",
        "inspiration": "the viral 'nuclear chain reaction simulation' shorts (one neutron, then exponential growth), "
                       "rebuilt as a bead material in the style of @particlesflow, with control rods as the twist "
                       "that turns it into an escalating story",
        "finale": "no rods left: one neutron sets off a runaway – hundreds of splits within seconds, the platform "
                  "glows white-hot and every sphere is split (MELTDOWN, slow motion)",
    }
    titles = ["{onscreen}", "Every round we pull out control rods – wait for the last one",
              "One neutron, {k} fuel spheres, no control rods"]
    questions = ["In which round did you think it would go critical?", "How many rods would you leave in?",
                 "Should the next one have more fuel?"]
    body = ("A toy chain reaction: every neutron that hits a fuel sphere splits it into two halves and 2–3 new "
            "neutrons; the grey bead walls are control rods that swallow neutrons. Every round we pull some rods out "
            "– every split plays the next note of {song} – and the last round has none. Everything is simulated in "
            "3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("chain reaction", "critical", "3d", "simulation", "satisfying", "physics", "meltdown")
    slowmo = True
    note_gap = 0.05
    finale_punch = 1.4
    full_frame = True
    tempo = "fast"
    experiment = "rounds"
    cta_y = 1600

    def __init__(self, seed: int):
        super().__init__(seed)
        # fuel lattice: positions in the x-z plane, the rod lines left free
        sx, sz = [], []
        rx, rz = _rods(0)
        for j in range(NL):
            for i in range(NL):
                x, z = (i - (NL - 1) / 2) * SP, (j - (NL - 1) / 2) * SP
                if all(abs(x - q) > 1e-6 for q in rx) and all(abs(z - q) > 1e-6 for q in rz):
                    sx.append(x)
                    sz.append(z)
        self.ax, self.az = np.array(sx), np.array(sz)
        self.K = self.k = len(sx)
        self.alive = np.ones(self.K, bool)
        self.drop = np.full(self.K, -9.0)         # refill: time the sphere started dropping back in
        self.split_t = np.full(self.K, -9.0)
        self.np_ = np.zeros((0, 2))               # neutrons: position, velocity (x, z)
        self.nv = np.zeros((0, 2))
        self.frags: list[list] = []               # [t0, x, z, vx, vz, colour index]
        self.round = 0
        self.r_t0 = 0.0
        self.splits = 0
        self.r_splits = [0]
        self.last_note = -9.0
        self.steps = 0
        self.gun_t = -9.0
        self.pull_t = -9.0
        self.rods_x, self.rods_z = _rods(0)
        self.old_rods = ([], [])
        self.phase = "run"                        # run -> refill -> run ... -> final
        self.recent: list[float] = []
        self.idle = 0.0
        look = self.look.rnd
        top, deep = look.choice([sim3d.GRADIENTS[2], sim3d.GRADIENTS[0], sim3d.GRADIENTS[4]])
        self.shades = [sim3d.lerp_col(top, deep, u / (SHADES - 1)) for u in range(SHADES)]
        self.col_i = np.array([int((abs(x) + abs(z)) / (2 * HALF) * (SHADES - 1)) for x, z in zip(sx, sz)])
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24)])
        self._fire()

    # ---------------------------------------------------------------- physics

    def _fire(self) -> None:
        """The neutron gun at the platform edge fires one neutron into the grid."""
        rnd = self.rnd
        side = rnd.choice([-1, 1])
        a = rnd.uniform(-0.5, 0.5)
        x, z = side * (HALF - 0.05), rnd.uniform(-0.5, 0.5)
        self.np_ = np.vstack([self.np_, [[x, z]]])
        self.nv = np.vstack([self.nv, [[-side * VN * math.cos(a), VN * math.sin(a)]]])
        self.gun_t = self.t
        self.gun = (x, z)
        self.events.append((self.t, "clack", 0))

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        if self.steps % PHYS == 0:
            self._physics(PHYS * dt)

    def _physics(self, h: float) -> None:
        if self.end is not None:  # the last neutrons fly off the empty platform
            if len(self.np_):
                self.np_ = self.np_ + self.nv * h
                keep = (np.abs(self.np_[:, 0]) < HALF) & (np.abs(self.np_[:, 1]) < HALF)
                self.np_, self.nv = self.np_[keep], self.nv[keep]
            self._frags(h)
            return
        rt = self.t - self.r_t0
        final = self.round >= len(ROUND_T)
        if self.phase == "run":
            if len(self.np_) == 0:
                self.idle += h
                if (final or rt < ROUND_T[self.round] - 1.2) and self.idle > 0.35:
                    self._fire()
                    self.idle = 0.0
            if not final and rt >= ROUND_T[self.round] and len(self.np_) == 0:
                self._next_round()
            elif not final and rt >= ROUND_T[self.round] + 1.5:   # stragglers are absorbed by the reset
                self.np_, self.nv = self.np_[:0], self.nv[:0]
                self._next_round()
        elif self.phase == "refill":
            due = (self.drop >= 0) & (self.drop + 0.35 <= self.t) & ~self.alive
            for i in np.nonzero(due)[0]:
                self.alive[i] = True
                self.events.append((self.t, "tone", int(self.col_i[i]) % 10))
            if not ((self.drop > self.t - 0.35) | (~self.alive)).any():
                self.phase = "run"
                self.r_t0 = self.t
                self._fire()
        self._neutrons(h)
        self._frags(h)

    def _next_round(self) -> None:
        self.round += 1
        self.r_splits.append(0)
        self.old_rods = (self.rods_x, self.rods_z)
        self.rods_x, self.rods_z = _rods(self.round)
        self.pull_t = self.t
        self.events.append((self.t, "break", self.round))
        self.phase = "refill"
        dead = np.nonzero(~self.alive)[0]           # split spheres drop back in, one after another
        order = sorted(dead, key=lambda i: (self.az[i], self.ax[i]))
        span = min(2.6, 0.02 * len(order) + 0.8)
        for n, i in enumerate(order):
            self.drop[i] = self.t + 0.9 + span * n / max(1, len(order))

    def _neutrons(self, h: float) -> None:
        if not len(self.np_):
            return
        P = self.np_ + self.nv * h
        keep = (np.abs(P[:, 0]) < HALF) & (np.abs(P[:, 1]) < HALF)
        prev = self.np_
        for rx in self.rods_x:                        # rods swallow neutrons that cross them
            keep &= ~(((prev[:, 0] - rx) * (P[:, 0] - rx) <= 0) | (np.abs(P[:, 0] - rx) < RR + RN))
        for rz in self.rods_z:
            keep &= ~(((prev[:, 1] - rz) * (P[:, 1] - rz) <= 0) | (np.abs(P[:, 1] - rz) < RR + RN))
        P, V = P[keep], self.nv[keep]
        hit = np.full(len(P), -1)
        if len(P) and self.alive.any():
            idx = np.nonzero(self.alive)[0]
            d2 = (P[:, None, 0] - self.ax[None, idx]) ** 2 + (P[:, None, 1] - self.az[None, idx]) ** 2
            j = np.argmin(d2, 1)
            close = d2[np.arange(len(P)), j] < (RA + RN) ** 2
            hit[close] = idx[j[close]]
        newp, newv = [P[hit < 0]], [V[hit < 0]]
        rnd = self.rnd
        done = set()
        for q in np.nonzero(hit >= 0)[0]:
            i = int(hit[q])
            if i in done:
                continue
            done.add(i)
            self.alive[i] = False
            self.drop[i] = -9.0
            self.split_t[i] = self.t
            self.splits += 1
            self.r_splits[-1] += 1
            self.recent.append(self.t)
            if self.t - self.last_note >= self.note_gap:
                self.events.append((self.t, "bounce", self.splits))
                self.last_note = self.t
            else:
                self.events.append((self.t, "clack", self.splits))
            n = 3 if rnd.random() < 0.3 else 2
            a0 = rnd.uniform(0, 2 * math.pi)
            for m in range(n):
                a = a0 + 2 * math.pi * m / n + rnd.uniform(-0.4, 0.4)
                newp.append(np.array([[self.ax[i] + math.cos(a) * (RA + RN + 0.004),
                                       self.az[i] + math.sin(a) * (RA + RN + 0.004)]]))
                newv.append(np.array([[math.cos(a) * VN, math.sin(a) * VN]]))
            b = rnd.uniform(0, 2 * math.pi)
            for sgn in (-1, 1):
                self.frags.append([self.t, self.ax[i], self.az[i], sgn * math.cos(b) * 0.5, sgn * math.sin(b) * 0.5,
                                   int(self.col_i[i])])
        self.np_, self.nv = np.vstack(newp), np.vstack(newv)
        if self.round >= len(ROUND_T) and (not self.alive.any() or
                                           (len(self.np_) == 0 and self.alive.sum() < 0.08 * self.K)):
            self.events.append((self.t, "break", 9))
            self.finish()

    def _frags(self, h: float) -> None:
        self.frags = [f for f in self.frags if self.t - f[0] < 0.7]

    def good(self) -> bool:
        return self.round >= len(ROUND_T) and self.splits >= self.K * 1.2

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, 0.0, 0.05), dist=10.6, yaw=0.55, pitch=0.86, fov=30, cy=H * 0.57)
        self.studio = sim3d.Studio(self.cam, 0.0, slab=HALF + 0.1, thick=0.18, tint=self.tint)
        self._spr: dict = {}

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _rod_pts(self):
        pts = []
        t = self.t
        sets = [(self.rods_x, self.rods_z, 0.0)]
        if t - self.pull_t < 2.0:                   # pulled rods slide out of the grid, away from the camera
            ox = [x for x in self.old_rods[0] if x not in self.rods_x]
            oz = [z for z in self.old_rods[1] if z not in self.rods_z]
            sets.append((ox, oz, (t - self.pull_t) ** 2 * 1.2))
        s0 = np.arange(-HALF + RR, HALF, 2 * RR * 1.05)
        for xs, zs, out in sets:
            s = s0 - out
            for x in xs:
                for k in range(3):
                    pts.append(np.stack([np.full(len(s), x), np.full(len(s), RR + 2 * RR * k), s], 1))
            for z in zs:
                for k in range(3):
                    pts.append(np.stack([s, np.full(len(s), RR + 2 * RR * k), np.full(len(s), z)], 1))
        return np.vstack(pts) if pts else np.zeros((0, 3))

    def render(self, p):
        t = self.t
        heat = sum(1 for x in self.recent if t - 0.5 < x <= t)
        self.recent = [x for x in self.recent if x > t - 0.5]
        pts, rad, cols = [], [], []
        live = np.nonzero(self.alive)[0]
        ys = np.full(len(live), RA)
        falling = np.nonzero((self.drop >= 0) & (self.drop <= t) & (self.drop + 0.35 > t))[0]
        for i in falling:                            # refill: spheres drop back into their place
            live = np.append(live, i)
            u = (t - self.drop[i]) / 0.35
            ys = np.append(ys, RA + 1.2 * (1 - u * u))
        if len(live):
            pts.append(np.stack([self.ax[live], ys, self.az[live]], 1))
            rad.append(np.full(len(live), RA))
            cols += [(255, 255, 255) if t - self.split_t[i] < 0.0 else self.shades[self.col_i[i]] for i in live]
        for f in self.frags:                         # the two halves fly apart and shrink
            a = t - f[0]
            pts.append(np.array([[f[1] + f[3] * a, RA * (1 + 2.2 * a - 4 * a * a) + 0.01, f[2] + f[4] * a]]))
            rad.append(np.array([RA * 0.72 * max(0.15, 1 - a / 0.7)]))
            cols.append(sim3d.lerp_col((255, 255, 230), self.shades[f[5]], min(1.0, a / 0.35)))
        R = self._rod_pts()
        if len(R):
            pts.append(R)
            rad.append(np.full(len(R), RR))
            cols += [ROD] * len(R)
        nn = len(self.np_)
        if nn:
            pts.append(np.stack([self.np_[:, 0], np.full(nn, RA), self.np_[:, 1]], 1))
            rad.append(np.full(nn, RN))
            cols += [NEUTRON] * nn
        img = self.studio.back.copy()
        if pts:
            P, Rr = np.vstack(pts), np.concatenate(rad)
            img = self.studio.shadows(img, P[: len(live)], Rr[: len(live)], 0.45) if len(live) else img
            x, y, z, s = self.cam.project(P)
            rp = np.maximum(1, np.rint(Rr * s)).astype(int)
            for j in np.argsort(-z):
                r = int(rp[j])
                spr = self._sprite(cols[j], r)
                img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        if nn:
            x, y, _, s = self.cam.project(np.stack([self.np_[:, 0], np.full(nn, RA), self.np_[:, 1]], 1))
            for xi, yi in zip(x / 4, y / 4):
                gd.ellipse((xi - 3, yi - 3, xi + 3, yi + 3), fill=(60, 90, 130))
        for f in self.frags:                         # every split flashes
            a = t - f[0]
            if a < 0.25:
                fx, fy = self.cam.point((f[1], RA, f[2]))
                rr = 10 * (1 - a / 0.25) + 3
                gd.ellipse((fx / 4 - rr, fy / 4 - rr, fx / 4 + rr, fy / 4 + rr), fill=(90, 80, 40))
        if t - self.gun_t < 0.3 and self.end is None:
            gx, gy = self.cam.point((self.gun[0], RA, self.gun[1]))
            gd.ellipse((gx / 4 - 8, gy / 4 - 8, gx / 4 + 8, gy / 4 + 8), fill=(80, 120, 170))
        glow = glow.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
        img = ImageChops.add(img, glow)
        hot = min(1.0, heat / 60) if self.end is None else max(0.0, 1 - (t - self.end) / 2.0)
        if hot > 0.02:                               # a runaway heats the whole picture
            img = ImageChops.add(img, Image.new("RGB", (W, H), (int(44 * hot), int(24 * hot), int(6 * hot))))
        return img

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.35)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["What if we pull out", "every control rod?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"{self.splits} SPLITS · ALL FUEL GONE"
        rods = len(self.rods_x) + len(self.rods_z)
        if self.round >= len(ROUND_T):
            return f"NO RODS · {self.r_splits[-1]} splits"
        return f"ROUND {self.round + 1} · {rods} rods · {self.r_splits[-1]} splits"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("CRITICAL", (255, 255, 255)), ("MELTDOWN!", (255, 170, 60))]
