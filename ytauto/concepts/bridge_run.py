"""Bridge run: a ball hops from plank to plank across a bridge of hundreds of bead planks over an abyss while the
bridge collapses behind it – every plank snaps in two and tumbles away, and the collapse keeps gaining on the ball.
Every hop is faster than the last; in the final sprint the collapse is right on its heels. Can it make the gold?

A numbered series (experiment "series"): every post of this kind is the next BRIDGE #N with more planks, and the
finale teases the next one above the follow button. The run length is planned exactly (the hop period is bisected
per seed so the landing on the gold lands on the target time), so every seed fits the run ranges, the seed search
always takes the next free seed and the episode number (seed + 1) counts up by itself.

3D (ytauto/sim3d.py look): every plank is a row of touching glossy spheres coloured by depth, rope rails and posts
are bead chains, and a snapped plank half tumbles down as one rigid piece (exact ballistic flight + spin). The
camera runs behind the ball. Hops and the collapse are planned up front, so every note lands on a visible landing.
"""
from __future__ import annotations

import bisect
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

RBD = 0.025                 # bead radius
NX = 12                     # beads across a plank
NR = 2                      # rows of beads per plank
PITCH = 0.14                # plank spacing along the bridge (m)
HALF = NX * RBD             # half width of the deck
RB = 0.062                  # ball radius
RAIL_Y = 0.2                # rope height above the deck
POST = 6                    # a post every 6 planks
START = 16                  # the ball starts on this plank
LAG0, LAG1 = 8.0, 1.3      # the collapse starts this many planks behind the ball and ends this close
SECTION = 50                # planks per colour section (each one a speed-up)
SPRINT = 40                 # the last planks are the final sprint
G = 9.81
GOLD = ((255, 222, 90), (255, 140, 30))
WHITE = (250, 250, 255)
SHADES = 8
FOG = 6


def _planks(ep: int) -> int:
    return min(800, 500 + 25 * (ep - 1))


def _plan(rnd: random.Random, ep: int) -> dict:
    """Every hop (take-off, landing plank, time), the holes in the deck and when each plank snaps – the hop period
    is bisected so the ball lands on the gold at `target` s."""
    NP = _planks(ep)
    target = rnd.uniform(62.5, 67.5)
    holes = set()
    k = START + 30
    while k < NP - 12:                                      # missing planks the ball must jump
        w = rnd.choice([2, 2, 3])
        holes.update(range(k, k + w))
        k += rnd.randint(28, 46)
    lens = [rnd.choices([1, 2, 3], [7, 3, 0.4])[0] for _ in range(2000)]
    spin = [rnd.uniform(-1, 1) for _ in range(NP + 1)]

    def build(T0: float) -> dict:
        hops = []                                           # (t take-off, t landing, k from, k to)
        t, k, i = 0.0, START, 0
        while k < NP:
            nxt = min(NP, k + lens[i % len(lens)])
            while nxt in holes:
                nxt += 1
            u = k / NP
            T = T0 / (1 + 2.1 * u ** 1.25) * (0.86 if NP - k <= SPRINT else 1.0)
            T *= 1 + 0.12 * (nxt - k - 1)
            hops.append((t, t + T, k, nxt))
            t, k, i = t + T, nxt, i + 1
        return {"hops": hops, "end": t}

    lo, hi = 0.05, 1.0
    for _ in range(45):
        mid = (lo + hi) / 2
        if build(mid)["end"] < target:
            lo = mid
        else:
            hi = mid
    plan = build((lo + hi) / 2)
    end = plan["end"]
    # the collapse front: lags LAG0 planks behind the ball at the start and LAG1 at the end
    ts = np.arange(-1.0, end + 1e-9, 1 / 240)
    land_t = np.array([h[1] for h in plan["hops"]])
    land_k = np.array([h[3] for h in plan["hops"]], float)
    prog = np.interp(ts, np.concatenate([[0.0], land_t]), np.concatenate([[START], land_k]))
    lag = LAG1 + (LAG0 - LAG1) * np.clip(1 - ts / end, 0, None) ** 1.4
    front = np.maximum.accumulate(prog - lag)
    snap = np.full(NP, math.inf)
    reach = np.searchsorted(front, np.arange(NP) + 0.5)
    ok = reach < len(ts)
    snap[ok] = ts[reach[ok]]
    snap[snap > end] = math.inf                             # what is left at the finale goes all at once
    plan.update(NP=NP, holes=holes, snap=snap, spin=spin, target=target)
    return plan


class BridgeRun(Sim):
    kind = "bridge_run"
    concept = {
        "created": "2026-10-27T03:40:00+00:00",
        "idea": "A ball hops from plank to plank across a bridge of 500+ planks made of glossy beads (3D) over an "
                "abyss while the bridge collapses behind it: every plank snaps in two and tumbles away, the collapse "
                "keeps gaining, every hop is faster (~4 → 11 hops/s) and there are holes to jump. A numbered series: "
                "BRIDGE #N, 25 planks longer every episode.",
        "inspiration": "the viral 'collapsing bridge / run before it falls' chase clips and 'every bounce makes it "
                       "faster' ball shorts, rebuilt as a 3D bead material in the style of @particlesflow, plus our "
                       "series format (tower_drop, our biggest hit)",
        "finale": "FINAL SPRINT: the collapse is one plank behind, the ball leaps onto the golden platform as the "
                  "last planks and both rope rails drop into the abyss (slow motion) and a fountain of gold beads "
                  "shoots up; then 'NEXT: BRIDGE #N+1' above the follow button",
    }
    titles = ["{onscreen}", "Bridge #{n}: can the ball cross {k} planks before it collapses?",
              "{k} planks, one ball, the bridge is falling – bridge #{n}"]
    questions = ["How many planks should bridge #{n} have next time?", "At which plank did you think it was over?",
                 "Should the collapse be faster next time?"]
    body = ("Bridge #{n}: a ball hops across a bridge of {k} planks made of glossy beads while the bridge collapses "
            "behind it. Every landing plays the next note of {song}, every plank that snaps clacks – the hops get "
            "faster and faster and the collapse keeps gaining. Every episode the bridge gets 25 planks longer. "
            "Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.96
    trend_words = ("ball", "bridge", "collapse", "run", "3d", "simulation", "satisfying", "faster", "escape")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    tempo = "fast"
    experiment = "series"
    cta_y = 1590
    run_ranges = [(60, 68), (62, 70)]   # every seed fits: the seed search takes the next one, so episodes count up

    @classmethod
    def planned_end(cls, seed: int) -> float:
        return _plan(random.Random(seed), seed + 1)["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        self.ep = self.n = seed + 1
        plan = self.plan = _plan(self.rnd, self.ep)
        self.NP = self.k = plan["NP"]
        self.hops = plan["hops"]
        self.hop_t = [h[0] for h in self.hops]
        self.hi = 0
        self.snap = plan["snap"]
        self.order = np.argsort(self.snap)
        self.si = 0
        self.holes = plan["holes"]
        self.on = START                 # plank the ball is on / flying to
        self.landed = {START: -9.0}     # plank -> time of the ball's landing (flash + dip)
        rnd = self.rnd
        # every snapped half flies off as a rigid piece: launch velocity and spin, drawn up front
        self.kick = np.array([[rnd.uniform(-0.7, -0.2), rnd.uniform(-0.6, 0.3), rnd.uniform(-0.4, 0.4),
                               rnd.uniform(2.0, 5.0), rnd.uniform(-2.5, 2.5)] for _ in range(2 * self.NP)])
        self.fountain = np.array([[rnd.uniform(0, 2 * math.pi), rnd.uniform(0.4, 1.6), rnd.uniform(3.2, 6.2),
                                   rnd.uniform(0, 0.25)] for _ in range(260)])
        # bead offsets of a plank half (x across, z along) and its rope bead
        xs = (np.arange(NX) - (NX - 1) / 2) * 2 * RBD
        zs = (np.arange(NR) - (NR - 1) / 2) * 2 * RBD
        X, Z = np.meshgrid(xs, zs)
        self.off = np.stack([X.ravel(), np.zeros(X.size), Z.ravel()], 1)
        self.u = np.abs(self.off[:, 0]) / HALF                  # 0 middle .. 1 edge (colour)
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.grads = grads
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])
        self.yaw = look.choice([-0.16, 0.16])
        self.cam_z = -START * PITCH
        self.fall_all = None

    # ---------------------------------------------------------------- physics

    def step(self, dt: float) -> None:
        self.t += dt
        while self.si < self.NP and self.snap[self.order[self.si]] <= self.t:
            k = int(self.order[self.si])
            self.si += 1
            if k not in self.holes and k != self.NP and self.t > 0:
                self.events.append((self.t, "clack", k))
        while self.hi < len(self.hops) and self.hops[self.hi][1] <= self.t:
            _, _, _, k = self.hops[self.hi]
            self.hi += 1
            self.on = k
            self.landed[k] = self.t
            self.events.append((self.t, "bounce", k))
            if k % SECTION == 0 and k < self.NP:
                self.events.append((self.t, "break", k))
            if k >= self.NP:
                self.events.append((self.t, "break", k))
                self.fall_all = self.t
                self.finish()
        if self.end is None:
            goal = self.ball()[2]
            self.cam_z += (goal - self.cam_z) * (1 - math.exp(-dt * 10))

    def ball(self, t: float | None = None) -> tuple[float, float, float]:
        t = self.t if t is None else t
        i = bisect.bisect_right(self.hop_t, t) - 1
        if i < 0:
            return 0.0, RB, -START * PITCH
        t0, t1, a, b = self.hops[i]
        if t >= t1:
            return 0.0, RB, -b * PITCH
        u = (t - t0) / (t1 - t0)
        h = 0.05 + 0.045 * (b - a)
        return 0.0, RB + 4 * h * u * (1 - u), -(a + (b - a) * u) * PITCH

    def snapped(self, k: int) -> float:
        s = float(self.snap[k]) if k < self.NP else math.inf
        if self.fall_all is not None and k < self.NP:
            s = min(s, self.fall_all + 0.02 * (self.NP - k))
        return s

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.bg = self._background()
        self._spr: dict = {}

    def _background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        glow = np.exp(-(((xx - W / 8) / (W / 4 * 0.7)) ** 2 + ((yy - H / 4 * 0.42) / (H / 4 * 0.3)) ** 2))
        deep = np.clip((yy / (H / 4) - 0.55) / 0.45, 0, 1)          # the abyss gets darker downwards
        arr = np.array(self.tint, np.float32)[None, None, :] * (0.45 + 1.2 * glow - 0.3 * deep)[..., None]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _cam(self) -> sim3d.Camera:
        return sim3d.Camera(target=(0, -0.1, self.cam_z - 0.55), dist=5.2, yaw=self.yaw, pitch=0.66, fov=34,
                            cy=H * 0.53)

    def _shade(self, k: int, u: float) -> tuple:
        if k >= self.NP:
            top, deep = GOLD
        else:
            top, deep = self.grads[(k // SECTION) % len(self.grads)]
        return sim3d.lerp_col(top, deep, round(u * (SHADES - 1)) / (SHADES - 1))

    def _piece(self, k: int, side: int, t: float) -> np.ndarray:
        """World positions of one plank half (side -1 left, +1 right) incl. its rope beads and post."""
        off = self.off[(self.off[:, 0] * side) > 0]
        rope = np.array([[side * (HALF + RBD), RAIL_Y - 0.03 * math.sin(math.pi * (k % POST) / POST), z]
                         for z in (-PITCH / 4, PITCH / 4)])
        parts = [off, rope]
        if k % POST == 0:
            parts.append(np.array([[side * (HALF + RBD), y, 0.0] for y in (0.05, 0.1, 0.15)]))
        L = np.vstack(parts)
        c = np.array([0.0, 0.0, -k * PITCH])
        s = self.snapped(k)
        if t < s:                                             # still in the bridge: shake when the collapse is near
            near = s - t
            if near < 0.6 and k != self.NP:
                c[1] += 0.012 * (0.6 - near) / 0.6 * math.sin(70 * t + k)
            lt = self.landed.get(k)
            if lt is not None and 0 <= t - lt < 0.25:
                c[1] -= 0.018 * math.sin(math.pi * (t - lt) / 0.25)
            return L + c
        tau = t - s
        kx, ky, kz, w1, w2 = self.kick[2 * k + (side > 0)]
        hinge = np.array([side * HALF * 0.0, 0.0, 0.0])
        a1 = side * w1 * tau                                   # the half swings down around its outer end
        a2 = w2 * tau
        ca, sa, cb, sb = math.cos(a1), math.sin(a1), math.cos(a2), math.sin(a2)
        R1 = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]])  # around z (the plank's long axis tilts)
        R2 = np.array([[1, 0, 0], [0, cb, -sb], [0, sb, cb]])  # around x (it tumbles)
        Lr = (L - hinge) @ (R2 @ R1).T + hinge
        move = np.array([side * kx * -0.6 * tau, ky * tau - G / 2 * tau * tau, kz * tau])
        return Lr + c + move

    def render(self, p):
        cam = self._cam()
        img = self.bg.copy()
        t = self.t
        on = self.on
        bz = self.ball(t)[2]
        k0 = max(0, int(-bz / PITCH) - 26)
        k1 = min(self.NP - 1, int(-bz / PITCH) + 52)
        pts, cols, rads = [], [], []
        for k in range(k0, k1 + 1):
            if k in self.holes:
                continue
            s = self.snapped(k)
            if t - s > 1.6:                                    # long gone into the abyss
                continue
            lt = self.landed.get(k)
            hot = lt is not None and 0 <= t - lt < 0.1 and self.end is None
            for side in (-1, 1):
                P = self._piece(k, side, t)
                m = int(np.sum((self.off[:, 0] * side) > 0))
                pts.append(P)
                rads.append(np.full(len(P), RBD))
                us = self.u[(self.off[:, 0] * side) > 0]
                cols += [WHITE if hot else self._shade(k, float(u)) for u in us]
                cols += [(150, 154, 170)] * (len(P) - m)       # rope and post beads: steel grey
        # the golden platform
        gx = (np.arange(15) - 7) * 2 * RBD
        gz = np.arange(10) * 2 * RBD
        GX, GZ = np.meshgrid(gx, gz)
        for y in (0.0, -2 * RBD):
            gp = np.stack([GX.ravel(), np.full(GX.size, y), -self.NP * PITCH - GZ.ravel()], 1)
            pts.append(gp)
            rads.append(np.full(len(gp), RBD))
            gu = np.abs(GX.ravel()) / (7 * 2 * RBD)
            cols += [self._shade(self.NP, float(u)) for u in gu]
        if self.end is not None:                               # fountain of gold beads at the finale
            tau = t - self.end
            f = self.fountain
            live = tau > f[:, 3]
            if live.any():
                ft = tau - f[live, 3]
                a, r0, up = f[live, 0], f[live, 1], f[live, 2]
                x = np.cos(a) * (0.32 + r0 * 0.5 * ft)
                z = -self.NP * PITCH - 0.22 + np.sin(a) * (0.2 + r0 * 0.5 * ft)
                y = up * ft - G / 2 * ft * ft
                keep = y > -1.5
                fp = np.stack([x[keep], y[keep], z[keep]], 1)
                pts.append(fp)
                rads.append(np.full(len(fp), RBD))
                cols += [GOLD[0] if i % 2 else GOLD[1] for i in range(len(fp))]
        bx, by, bzz = self.ball(t)
        pts.append(np.array([[bx, by, bzz]]))
        rads.append(np.array([RB]))
        heat = self._heat()
        cols.append(heat)
        P = np.vstack(pts)
        Rr = np.concatenate(rads)
        x, y, z, s = cam.project(P)
        rp = np.maximum(1, np.rint(Rr * s)).astype(int)
        ok = (y > 440) & (y < H + 60) & (x > -60) & (x < W + 60) & (z > 0.8) & ((rp < 60) | (Rr > RBD * 1.5))
        fog = np.clip((z - 3.0) / 9.0, 0, 0.85)
        # shadow of the ball on the deck under it, glow around it
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        sx, sy = cam.point((bx, 0.0, bzz))
        bsx, bsy, br = float(x[-1]) / 4, float(y[-1]) / 4, float(RB * s[-1]) / 4
        u = self._speed_u()
        rr = br * (1.6 + 1.2 * u)
        gd.ellipse((bsx - rr, bsy - rr, bsx + rr, bsy + rr), fill=(int(45 + 110 * u), int(45 + 40 * u), int(55 - 35 * u)))
        glow = glow.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
        tint = np.array(self.tint, float)
        shadow_done = False
        for j in np.argsort(-z):
            if not ok[j]:
                continue
            if not shadow_done and z[j] < z[-1] + 0.02:       # the ball's soft shadow goes under the near beads
                shadow_done = True
                d = ImageDraw.Draw(img, "RGBA")
                sr = RB * float(s[-1]) * 0.9
                d.ellipse((sx - sr, sy - sr * 0.4, sx + sr, sy + sr * 0.4), fill=(0, 0, 0, 90))
            c = cols[j]
            if fog[j] > 0.05:
                q = round(float(fog[j]) * FOG) / FOG
                c = tuple(int(a + (b * 1.4 - a) * q) for a, b in zip(c, tint))
            r = int(rp[j])
            spr = self._sprite(c, r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        return ImageChops.add(img, glow)

    def _speed_u(self) -> float:
        i = min(max(self.hi, 1), len(self.hops) - 1)
        t0, t1, _, _ = self.hops[i]
        return float(np.clip((0.26 - (t1 - t0)) / 0.16, 0, 1))

    def _heat(self) -> tuple:
        return sim3d.lerp_col(WHITE, (255, 150, 50), self._speed_u())

    def behind(self) -> float:
        """How many planks the collapse is behind the ball."""
        n = sum(1 for k in range(max(0, self.on - 30), self.on) if self.snapped(k) > self.t and k not in self.holes)
        return n

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break" and i < self.NP:
            p.punch(0.35)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            super().draw_text(p, d)
            return
        p.big_text(d, self.finale(), self.t - self.end, cy=330)
        if self.t - self.end > 0.6:
            p.centered(d, 600, f"NEXT: BRIDGE #{self.ep + 1} · {_planks(self.ep + 1)} PLANKS", p.f_count,
                       (255, 214, 120), 2)

    def title(self) -> list[str]:
        return ["Can the ball cross", f"{self.NP} planks in time?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"BRIDGE #{self.ep} · ALL {self.NP} PLANKS"
        n = self.behind()
        gap = f"collapse {n} behind" if n else "COLLAPSE ON ITS HEELS"
        if self.NP - self.on <= SPRINT:
            return f"FINAL SPRINT · {self.NP - self.on} to go" if n else f"{self.NP - self.on} TO GO · {gap}"
        return f"plank {self.on}/{self.NP} · {gap}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"BRIDGE #{self.ep}", (255, 255, 255)), ("CROSSED!", GOLD[0])]
