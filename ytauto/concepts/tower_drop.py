"""Tower drop: a ball bounces down a spinning tower of 100+ floors made of glossy beads – every floor has one gap,
the ball drops through when the gap spins under it and the floor it leaves bursts into beads. Faster every ten
floors; the last floors are smashed in FIRE MODE, and the golden base explodes.

A numbered series (experiment "series"): every post of this kind is the next TOWER #N with more floors, and the
finale teases the next one above the follow button. The episode number is the seed + 1 – the run length is planned
exactly (every seed fits the run ranges), so the seed search always takes the next free seed and the numbers count
up by themselves.

3D (ytauto/sim3d.py look): every floor is a disc of touching spheres coloured by depth, the camera falls with the
ball. The fall itself is exact kinematics (bounce period, gravity and gap timing are planned up front), so length,
gap and sound are always in sync.
"""
from __future__ import annotations

import bisect
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

D = 0.46                    # floor spacing (m)
RBD = 0.034                 # bead radius of the floors
RINGS = [0.26 + 0.068 * i for i in range(7)]
RC = 0.464                  # the ball rolls on this ring
RB = 0.072                  # ball radius
POLE = 0.19                 # pole bead radius
GAP = 0.46                  # half width of a floor's gap (rad)
FIRE = 12                   # the last floors are smashed in fire mode
PHYS = 6                    # loose beads move every 6th step (120 Hz)
GOLD = ((255, 214, 64), (255, 120, 28))
WHITE = (250, 250, 255)
SHADES = 12


def _plan(rnd: random.Random, ep: int) -> dict:
    """The whole fall, planned exactly: per floor how often the ball bounces before the gap comes, the bounce period
    (shorter every floor), the times of every contact and the tower's spin – scaled so the run lasts `target` s."""
    F = min(150, 100 + 5 * (ep - 1))
    n = []
    for k in range(F):
        if k >= F - FIRE:
            n.append(-1)                                    # fire mode: smashed on contact
        elif k % 10 == 9:
            n.append(rnd.choice([3, 4, 5]))                 # every tenth floor is a tough one
        else:
            n.append(rnd.choices([0, 1, 2, 3, 4], [2.2, 3, 3, 2, 1])[0])
    turn = rnd.choice([-1, 1])
    target = rnd.uniform(62.5, 67.5)
    h = 0.17                                                # bounce height (m)

    def build(T0: float) -> dict:
        G0 = 8 * h / (T0 * T0)
        acts, segs = [], []                                 # acts: (t, what, floor); segs: (t0, y0, v0, G)
        arr, theta, omega, gaps = [], [], [], []
        t, th, vb, G = 0.0, 0.0, 0.0, G0
        y = RBD + RB + 0.32
        segs.append((0.0, y, 0.0, G0))
        u = math.sqrt(2 * G0 * 0.32)
        t = u / G0
        for k in range(F):
            s = 1.0 + 1.15 * (k / F) ** 1.2
            T, G = T0 / s, G0 * s * s
            vb = G * T / 2
            c = -k * D + RBD + RB
            om = turn * (1 if (k // 10) % 2 == 0 else -1) * 1.35 * GAP / T
            arr.append(t)
            theta.append(th)
            omega.append(om)
            if n[k] < 0:                                    # fire mode
                acts.append((t, "smash", k))
                p, up = t, u * 0.42
                gaps.append(0.0)
            else:
                for j in range(n[k]):
                    acts.append((t + j * T, "bounce", k))
                    segs.append((t + j * T, c, vb, G))
                p = t + n[k] * T
                up = vb if n[k] else u
                acts.append((p, "pass", k))
                gaps.append(-(th + om * (p - t)))           # the gap is right under the ball when it passes
            up = min(up, 1.7 * vb)
            segs.append((p, c, -up, G))
            tf = (-up + math.sqrt(up * up + 2 * G * D)) / G
            th += om * (p + tf - t)
            t, u = p + tf, up + G * tf
        arr.append(t)
        theta.append(th)
        omega.append(0.0)
        acts.append((t, "base", F))
        cb = -F * D + RBD + RB
        segs.append((t, cb, 1.6 * vb, G))                   # the ball pops up from the exploding base ...
        segs.append((t + 3.2 * vb / G, cb, 0.0, 0.0))       # ... and lands on what is left of it
        return {"F": F, "n": n, "acts": acts, "segs": segs, "arr": arr, "theta": theta, "omega": omega,
                "gaps": gaps, "end": t, "T0": T0}

    lo, hi = 0.05, 1.0
    for _ in range(40):                                     # length grows with the bounce period: bisect it
        mid = (lo + hi) / 2
        if build(mid)["end"] < target:
            lo = mid
        else:
            hi = mid
    return build((lo + hi) / 2)


class TowerDrop(Sim):
    kind = "tower_drop"
    concept = {
        "created": "2026-10-23T03:40:00+00:00",
        "idea": "A ball bounces down a spinning tower of 100+ floors, each a disc of hundreds of glossy beads (3D) "
                "with one gap: it drops through when the gap spins under it and the floor bursts into beads. "
                "Every ten floors it gets faster; the last 12 floors are smashed in FIRE MODE. A numbered series: "
                "TOWER #N, five floors more every episode, the finale teases the next tower.",
        "inspiration": "the 'ball falls down the helix tower' mobile-game clips that keep going viral on TikTok and "
                       "Shorts, rebuilt as a 3D bead material in the style of @particlesflow, plus our own "
                       "speed-up formula (escape/stringart) and the 'series' follow experiment",
        "finale": "FIRE MODE: the glowing ball smashes the last 12 floors without stopping (~8 hits/s) and crashes "
                  "into the golden base, which explodes into hundreds of gold beads (slow motion); then "
                  "'NEXT: TOWER #N+1' above the follow button",
    }
    titles = ["{onscreen}", "Tower #{n}: can the ball fall through all {k} floors?",
              "{k} floors, one ball – tower #{n}, wait for fire mode"]
    questions = ["How many floors should tower #{n} have next time?", "Which floor did you think would stop it?",
                 "Should the next tower spin faster?"]
    body = ("Tower #{n}: a ball bounces down a spinning tower of {k} floors made of glossy beads. Every bounce plays "
            "the next note of {song}, every floor it drops through bursts with a crack – faster every ten floors, "
            "and the last twelve are smashed in fire mode. Every episode the tower gets five floors taller. Everything "
            "is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.96
    trend_words = ("ball", "tower", "fall", "3d", "simulation", "satisfying", "faster", "floors")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    tempo = "fast"
    experiment = "series"
    cta_y = 1560
    run_ranges = [(60, 68), (62, 70)]   # every seed fits: the seed search takes the next one, so episodes count up

    @classmethod
    def planned_end(cls, seed: int) -> float:
        return _plan(random.Random(seed), seed + 1)["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        self.ep = self.n = seed + 1
        plan = _plan(self.rnd, self.ep)
        self.F = self.K = plan["F"]
        self.plan = plan
        self.acts = plan["acts"]
        self.ai = 0
        self.segs = plan["segs"]
        self.seg_t = [s[0] for s in self.segs]
        rnd = self.rnd
        # beads of every floor in local coordinates (ring radius, angle), the gap left out
        R, A, FL = [], [], []
        for k in range(self.F):
            g = plan["gaps"][k]
            for r in RINGS:
                m = int(2 * math.pi * r / (2 * RBD * 1.02))
                a = np.arange(m) * 2 * math.pi / m + rnd.uniform(0, 1)
                if plan["n"][k] >= 0:
                    off = (a - g + math.pi) % (2 * math.pi) - math.pi
                    a = a[np.abs(off) > GAP]
                R.append(np.full(len(a), r))
                A.append(a)
                FL.append(np.full(len(a), k))
        base = [0.1 + 0.068 * i for i in range(12)]  # the golden base: a full disc, wider than the floors
        for r in base:
            m = max(6, int(2 * math.pi * r / (2 * RBD * 1.02)))
            R.append(np.full(m, r))
            A.append(np.arange(m) * 2 * math.pi / m)
            FL.append(np.full(m, self.F))
        self.R, self.A, self.FL = np.concatenate(R), np.concatenate(A), np.concatenate(FL).astype(int)
        self.first = np.searchsorted(self.FL, np.arange(self.F + 2))   # bead index range per floor
        N = len(self.R)
        self.state = np.zeros(N, np.int8)      # 0 in the floor, 1 loose, 2 gone
        self.P = np.zeros((N, 3))
        self.V = np.zeros((N, 3))
        self.Pprev = self.P.copy()
        self.flash = np.full(N, -9.0)
        self.loose: np.ndarray = np.zeros(0, int)
        self.k = 0                 # floor the ball is on / falling towards
        self.cleared = 0
        self.fire = False
        self.steps = 0
        self.cam_y = 0.0
        self.y = self.segs[0][1]
        self.v0 = self.plan["T0"]
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.grads = grads
        self.shades = [[sim3d.lerp_col(top, deep, i / (SHADES - 1)) for i in range(SHADES)] for top, deep in grads]
        self.gold = [sim3d.lerp_col(GOLD[0], GOLD[1], i / (SHADES - 1)) for i in range(SHADES)]
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])
        self.phi = 0.35 + 0.3        # world angle of the ball (camera yaw + a little)

    # ---------------------------------------------------------------- physics

    def theta(self, t: float) -> float:
        arr = self.plan["arr"]
        k = max(0, min(len(arr) - 1, bisect.bisect_right(arr, t) - 1))
        return self.plan["theta"][k] + self.plan["omega"][k] * (t - arr[k])

    def ball_y(self, t: float) -> float:
        i = max(0, bisect.bisect_right(self.seg_t, t) - 1)
        t0, y0, v0, G = self.segs[i]
        x = t - t0
        return y0 + v0 * x - G * x * x / 2

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        self.y = self.ball_y(self.t)
        while self.ai < len(self.acts) and self.acts[self.ai][0] <= self.t:
            _, what, k = self.acts[self.ai]
            self.ai += 1
            self._act(what, k)
        if self.end is None:
            goal = -min(self.k, self.F) * D
            self.cam_y += (goal - self.cam_y) * (1 - math.exp(-dt * 9))
        if self.steps % PHYS == 0:
            self._loose(PHYS * dt)

    def _act(self, what: str, k: int) -> None:
        if what == "bounce":
            self.events.append((self.t, "bounce", k))
            self._chip(k)
        elif what == "pass":
            self.events.append((self.t, "break", k))
            self._shatter(k, 1.0)
            self.k, self.cleared = k + 1, k + 1
        elif what == "smash":
            self.fire = True
            self.events.append((self.t, "bounce", k))
            self.events.append((self.t, "break", k))
            self._shatter(k, 1.6)
            self.k, self.cleared = k + 1, k + 1
        elif what == "base":
            self.events.append((self.t, "break", k))
            self._shatter(k, 1.0, fountain=True)
            self.k = self.cleared = self.F
            self.finish()

    def _world(self, idx: np.ndarray, t: float) -> np.ndarray:
        a = self.A[idx] + self.theta(t)
        r = self.R[idx]
        y = -self.FL[idx] * D
        return np.stack([r * np.sin(a), y, r * np.cos(a)], 1)

    def _chip(self, k: int) -> None:
        """A bounce knocks the bead under the ball loose and lights up the ones around it."""
        lo, hi = self.first[k], self.first[k + 1]
        idx = np.arange(lo, hi)
        idx = idx[self.state[idx] == 0]
        if not len(idx):
            return
        P = self._world(idx, self.t)
        bx, bz = RC * math.sin(self.phi), RC * math.cos(self.phi)
        d = np.hypot(P[:, 0] - bx, P[:, 2] - bz)
        self.flash[idx[d < 0.16]] = self.t
        j = idx[np.argsort(d)[:1]]
        self.P[j] = self._world(j, self.t)
        self.Pprev[j] = self.P[j]
        rnd = self.rnd
        self.V[j] = (rnd.uniform(-0.6, 0.6), rnd.uniform(1.0, 1.8), rnd.uniform(0.2, 0.8))
        self.state[j] = 1
        self.loose = np.concatenate([self.loose, j])

    def _shatter(self, k: int, power: float, fountain: bool = False) -> None:
        lo, hi = self.first[k], self.first[k + 1]
        idx = np.arange(lo, hi)
        idx = idx[self.state[idx] == 0]
        if fountain:  # the golden base: the outer rings shoot up like a fountain, the core stays
            idx = idx[self.R[idx] > 0.42]
        if not len(idx):
            return
        P = self._world(idx, self.t)
        self.P[idx] = P
        self.Pprev[idx] = P
        r = np.maximum(self.R[idx], 1e-6)
        out = np.stack([P[:, 0] / r, np.zeros(len(idx)), P[:, 2] / r], 1)
        om = self.plan["omega"][min(k, self.F - 1)]
        tang = np.stack([P[:, 2], np.zeros(len(idx)), -P[:, 0]], 1) * om * 0.6
        rnd = self.rnd
        sp = np.array([rnd.uniform(1.0, 2.2) for _ in idx]) * power
        up = np.array([rnd.uniform(0.3, 1.8) for _ in idx]) * min(power, 1.0)
        if fountain:
            sp = np.array([rnd.uniform(0.3, 1.4) for _ in idx])
            up = np.array([rnd.uniform(2.5, 6.0) for _ in idx])
        self.V[idx] = out * sp[:, None] + (0 if fountain else tang)
        self.V[idx, 1] = up
        self.state[idx] = 1
        self.loose = np.concatenate([self.loose, idx])

    def _loose(self, h: float) -> None:
        idx = self.loose
        if not len(idx):
            return
        self.Pprev[idx] = self.P[idx]
        self.V[idx, 1] -= 11.0 * h
        self.P[idx] += self.V[idx] * h
        if self.end is not None:  # the gold rain lands on what is left of the base
            P, V = self.P, self.V
            top = -self.F * D + 2 * RBD
            on = (np.hypot(P[idx, 0], P[idx, 2]) < 0.9) & (P[idx, 1] < top) & (P[idx, 1] > top - 0.15)
            j = idx[on]
            P[j, 1] = top
            V[j, 1] = np.abs(V[j, 1]) * 0.25
            V[j, 0] *= 0.7
            V[j, 2] *= 0.7
        gone = self.P[idx, 1] < self.cam_y - 4.0
        if gone.any():
            self.state[idx[gone]] = 2
            self.loose = idx[~gone]

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.yaw = 0.35
        self.bg = self._background()
        self._spr: dict = {}

    def _background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        cx, cy = W / 8, H / 8 * 1.05
        glow = np.exp(-(((xx - cx) / (W / 4 * 0.6)) ** 2 + ((yy - cy) / (H / 4 * 0.35)) ** 2))
        arr = np.array(self.tint, np.float32)[None, None, :] * (0.5 + 1.1 * glow)[..., None]
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        return img

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _cam(self) -> sim3d.Camera:
        return sim3d.Camera(target=(0, self.cam_y - 0.2, 0), dist=4.6, yaw=self.yaw, pitch=0.6, fov=36, cy=H * 0.56)

    def _floor_col(self, k: int, r: float) -> tuple:
        if k >= self.F:
            sh = self.gold
        else:
            sh = self.shades[(k // 10) % len(self.shades)]
        u = (r - RINGS[0]) / (RINGS[-1] - RINGS[0])
        return sh[int(np.clip(u, 0, 1) * (SHADES - 1) + 0.5)]

    def render(self, p):
        cam = self._cam()
        img = self.bg.copy()
        t = self.t
        k0 = max(0, int((-self.cam_y - 0.6) / D))
        k1 = min(self.F, int((-self.cam_y + 2.0) / D) + 1)
        idx = np.arange(self.first[k0], self.first[k1 + 1])
        idx = idx[self.state[idx] == 0]
        pts = [self._world(idx, t)] if len(idx) else [np.zeros((0, 3))]
        rad = [np.full(len(idx), RBD)]
        cols = [WHITE if t - self.flash[i] < 0.12 else self._floor_col(int(self.FL[i]), float(self.R[i])) for i in idx]
        a = (self.steps % PHYS) / PHYS
        L = self.loose
        if len(L):
            Lp = self.Pprev[L] + (self.P[L] - self.Pprev[L]) * a
            pts.append(Lp)
            rad.append(np.full(len(L), RBD))
            cols += [self._floor_col(int(self.FL[i]), float(self.R[i])) for i in L]
        # the pole: a column of big grey beads, down to the base
        ys = np.arange(math.floor((self.cam_y - 2.2) / 0.16) * 0.16, self.cam_y + 1.8, 0.16)
        ys = ys[ys > -self.F * D - 0.05]
        pts.append(np.stack([np.zeros(len(ys)), ys, np.zeros(len(ys))], 1))
        rad.append(np.full(len(ys), POLE))
        cols += [(92, 96, 112)] * len(ys)
        ball = np.array([[RC * math.sin(self.phi), self.y, RC * math.cos(self.phi)]])
        pts.append(ball)
        rad.append(np.array([RB]))
        heat = (255, 196, 90) if self.fire else WHITE
        cols.append(heat)
        P = np.vstack(pts)
        Rr = np.concatenate(rad)
        x, y, z, s = cam.project(P)
        rp = np.maximum(1, np.rint(Rr * s)).astype(int)
        ok = (y > -80) & (y < H + 80) & (z > 2.2) & ((Rr > RBD * 1.5) | (rp < 40))  # debris at the lens is left out
        # glow behind the ball (fire mode: a hot trail)
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        bx, by, br = float(x[-1]) / 4, float(y[-1]) / 4, float(RB * s[-1]) / 4
        if self.fire and self.end is None:
            for j in range(8, 0, -1):
                ty = self.ball_y(t - j * 0.012)
                _, yy, _, _ = cam.project(np.array([[ball[0, 0], ty, ball[0, 2]]]))
                rr = br * (1.6 + 0.12 * (8 - j))
                gd.ellipse((bx - rr, float(yy[0]) / 4 - rr, bx + rr, float(yy[0]) / 4 + rr),
                           fill=(int(150 - 10 * j), int(70 - 6 * j), 10))
        rr = br * (3.2 if self.fire else 2.4)
        gd.ellipse((bx - rr, by - rr, bx + rr, by + rr), fill=(120, 80, 30) if self.fire else (60, 60, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
        for j in np.argsort(-z):
            if not ok[j]:
                continue
            r = int(rp[j])
            spr = self._sprite(cols[j], r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        return ImageChops.add(img, glow)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break" and (i % 10 == 9 or i >= self.F - FIRE):
            p.punch(0.35 if i < self.F - FIRE else 0.18)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)
        if self.t - self.end > 0.6:
            p.centered(d, 600, f"NEXT: TOWER #{self.ep + 1} · {min(150, self.F + 5)} FLOORS", p.f_count,
                       (255, 214, 120), 2)

    def title(self) -> list[str]:
        return ["Can the ball fall", f"through {self.F} floors?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"TOWER #{self.ep} · ALL {self.F} FLOORS"
        if self.fire:
            return f"FIRE MODE · floor {min(self.cleared + 1, self.F)}/{self.F}"
        return f"TOWER #{self.ep} · floor {min(self.cleared + 1, self.F)}/{self.F}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"TOWER #{self.ep}", (255, 255, 255)), ("CLEARED!", GOLD[0])]
