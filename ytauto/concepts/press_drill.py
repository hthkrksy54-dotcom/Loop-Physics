"""Press drill: a ball rolls back and forth between two thick walls of glossy beads that a press pushes together –
every hit drills a little deeper into the wall it hits, and every hit makes it faster. The press speeds up too:
the gap shrinks, the hits come faster and faster – until one wall is drilled through and bursts.

A numbered series (experiment "series"): every post of this kind is the next PRESS #N with walls one bead layer
thicker, and the finale teases the next one above the follow button. The run length is planned exactly (the press
speed is bisected per seed so the breakthrough lands on the target time), so every seed fits the run ranges, the
seed search always takes the next free seed and the episode number (seed + 1) counts up by itself.

3D (ytauto/sim3d.py look): the walls are blocks of touching spheres coloured by depth, the drilled-out beads tumble
into the gap and get bulldozed by the press. The ball's flight is exact kinematics (event by event), so every note
lands on a visible wall hit.
"""
from __future__ import annotations

import bisect
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

RBD = 0.03                  # bead radius of the walls
NZ, NY = 24, 6              # beads along the wall and up
RB = 0.09                   # ball radius (rolls on the platform)
G0 = 1.9                    # gap between the wall faces at the start (m)
CONE = 0.27                 # crater widening per metre of depth (the hole is a funnel)
PHYS = 6                    # loose beads move every 6th step (120 Hz)
WHITE = (250, 250, 255)
SHADES = 12


def _layers(ep: int) -> int:
    return min(20, 8 + ep)


def _plan(rnd: random.Random, ep: int) -> dict:
    """The whole duel, event by event: when the ball hits which wall, how deep that wall is drilled after each hit,
    where the press is. The press speed is scaled so the breakthrough lands on `target`."""
    thick = _layers(ep) * 2 * RBD
    target = rnd.uniform(62.5, 67.5)
    v0 = rnd.uniform(4.2, 4.8)
    acc = rnd.uniform(1.0045, 1.0055)
    vmax = rnd.uniform(11.0, 12.5)
    side0 = rnd.choice([-1, 1])
    digs = [rnd.uniform(0.55, 1.45) for _ in range(6000)]
    dig0 = thick / rnd.uniform(240, 262)            # ~500 hits for both walls together

    def build(k: float) -> dict:
        """k scales the press: each wall moves in at u(t) = k (0.25 + t / target) ** 1.6 (so it speeds up)."""
        def face(t: float) -> float:              # inner face of the right wall (left = mirrored); 0 = shut
            return max(0.0, G0 / 2 - k * target / 2.6 * ((0.25 + t / target) ** 2.6 - 0.25 ** 2.6))

        t, x, v, d = 0.0, 0.0, v0 * side0, {-1: 0.0, 1: 0.0}
        hits = []                                  # (t, side, x at hit, depth of that wall after the hit)
        n = 0
        while n < 5000:
            s = 1 if v > 0 else -1
            # solve x + v (tau - t) = s (face(tau) + d[s] - RB) by a few Newton steps (face is smooth)
            tau = t + 0.05
            for _ in range(30):
                f = x + v * (tau - t) - s * (face(tau) + d[s] - RB)
                fp = v + (s * k * (0.25 + tau / target) ** 1.6 if face(tau) > 0 else 0.0)
                tau2 = tau - f / fp
                if abs(tau2 - tau) < 1e-10:
                    tau = tau2
                    break
                tau = max(t + 1e-6, tau2)
            if tau > 3 * target:
                return {"end": math.inf}
            x = x + v * (tau - t)
            t = tau
            d[s] += dig0 * digs[n] * min(2.0, abs(v) / v0) ** 0.5
            n += 1
            if d[s] >= thick:
                d[s] = thick
                hits.append((t, s, x, d[s]))
                return {"end": t, "hits": hits, "k": k, "face": face, "thick": thick, "side": s,
                        "v_end": abs(v), "target": target}
            hits.append((t, s, x, d[s]))
            v = -s * min(vmax, abs(v) * acc)
        return {"end": math.inf}

    lo, hi = 0.0, 0.06
    for _ in range(50):                            # faster press -> more hits per second -> earlier breakthrough
        mid = (lo + hi) / 2
        if build(mid)["end"] > target:
            lo = mid
        else:
            hi = mid
    plan = build(hi)
    return plan


class PressDrill(Sim):
    kind = "press_drill"
    concept = {
        "created": "2026-10-26T03:40:00+00:00",
        "idea": "A ball rolls back and forth between two thick walls of glossy beads (3D) that a press pushes "
                "together: every hit drills a funnel deeper into the wall it hits and makes the ball faster, while "
                "the press speeds up – the gap shrinks and the hits race from ~3 to 12+ per second until one wall "
                "is drilled through. A numbered series: PRESS #N, one bead layer thicker every episode.",
        "inspiration": "the viral 'walls closing in – can it escape?' and 'every bounce makes it faster' ball shorts, "
                       "rebuilt as a 3D bead material in the style of @particlesflow, plus our series format that made "
                       "tower_drop our biggest hit",
        "finale": "the ball punches through the last bead layer at top speed, the drilled wall bursts into hundreds "
                  "of beads (slow motion) and the ball shoots out across the platform; then 'NEXT: PRESS #N+1' above "
                  "the follow button",
    }
    titles = ["{onscreen}", "Press #{n}: can the ball drill out before the walls close?",
              "Every hit makes it faster – press #{n}, {k} cm walls"]
    questions = ["How thick should the walls be for press #{n} next time?", "Left or right – which wall breaks first?",
                 "Did you think it would make it?"]
    body = ("Press #{n}: a ball rolls between two walls made of glossy beads, {k} cm thick, while a press pushes them "
            "together. Every hit drills deeper, makes the ball faster and plays the next note of {song} – the gap "
            "shrinks, the hits come faster and faster, until one wall breaks. Every episode the walls get one bead "
            "layer thicker. Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.97
    trend_words = ("ball", "walls", "closing", "escape", "3d", "simulation", "satisfying", "faster", "drill")
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
        self.L = _layers(self.ep)
        self.thick = plan["thick"]
        self.k = round(self.thick * 100)
        self.face = plan["face"]
        self.hits = plan["hits"]
        self.hit_t = [h[0] for h in self.hits]
        self.hi = 0
        self.depth = {-1: 0.0, 1: 0.0}
        rnd = self.rnd
        self.z0 = rnd.uniform(-0.12, 0.12)     # the ball's lane
        # beads of one wall in local coordinates: depth from the inner face, z, y
        i, j, m = np.meshgrid(np.arange(self.L), np.arange(NZ), np.arange(NY), indexing="ij")
        self.dep = (i * 2 * RBD + RBD).astype(float)
        self.bz = (-(NZ - 1) * RBD + j * 2 * RBD).astype(float)
        self.by = (RBD + m * 2 * RBD).astype(float)
        rad = np.hypot(self.bz - self.z0, self.by - RB)
        need = np.maximum(self.dep - RBD, self.dep + (rad - RB - 0.3 * RBD) / CONE)   # depth that knocks it out
        self.gone = {}
        for s in (-1, 1):
            ds = [h[3] for h in self.hits if h[1] == s]
            ts = [h[0] for h in self.hits if h[1] == s]
            idx = np.searchsorted(np.array(ds), need.ravel(), side="left")
            out = np.full(idx.shape, math.inf)
            ok = idx < len(ts)
            out[ok] = np.array(ts)[idx[ok]] if len(ts) else math.inf
            self.gone[s] = out.reshape(need.shape)                                      # time it is knocked out
        self.flash = {-1: -9.0, 1: -9.0}
        self.burst = None          # side of the wall that bursts at the end
        N = 2 * self.L * NZ * NY
        self.P = np.zeros((N, 3))
        self.V = np.zeros((N, 3))
        self.Pprev = self.P.copy()
        self.lcol = np.zeros(N, int)
        self.loose = np.zeros(0, int)
        self.steps = 0
        self.ball_x, self.ball_v = 0.0, 0.0
        self.esc = None            # after the breakthrough: (t0, x0, v)
        self.quarter = {-1: 0, 1: 0}
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.shades = {s: [sim3d.lerp_col(top, deep, u / (SHADES - 1)) for u in range(SHADES)]
                       for s, (top, deep) in zip((-1, 1), grads[:2])}
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])

    # ---------------------------------------------------------------- physics

    def face_at(self, t: float) -> float:
        return self.face(min(t, self.plan["end"]))

    def ball_at(self, t: float) -> float:
        if self.esc is not None and t >= self.esc[0]:
            t0, x0, v = self.esc
            sp = abs(v)                                  # rolls out and stops near the platform edge
            a = sp * sp / (2 * max(0.3, 1.55 - abs(x0)))
            x = min(t - t0, sp / a)
            return x0 + math.copysign(sp * x - a / 2 * x * x, v)
        i = bisect.bisect_right(self.hit_t, t) - 1
        if i < 0:
            t0, x0 = 0.0, 0.0
            t1, x1 = self.hits[0][0], self.hits[0][2]
        else:
            t0, x0 = self.hits[i][0], self.hits[i][2]
            if i + 1 >= len(self.hits):
                return x0
            t1, x1 = self.hits[i + 1][0], self.hits[i + 1][2]
        return x0 + (x1 - x0) * (t - t0) / max(1e-9, t1 - t0)

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        while self.hi < len(self.hits) and self.hits[self.hi][0] <= self.t:
            self._hit(*self.hits[self.hi])
            self.hi += 1
        self.ball_x = self.ball_at(self.t)
        if self.steps % PHYS == 0:
            self._loose(PHYS * dt)

    def _hit(self, t: float, s: int, x: float, d: float) -> None:
        last = self.hi == len(self.hits) - 1
        self.depth[s] = d
        self.flash[s] = self.t
        self.events.append((self.t, "bounce", self.hi))
        self._knock(s, t)
        q = int(4 * d / self.thick)
        if q > self.quarter[s] and not last:
            self.quarter[s] = q
            self.events.append((self.t, "break", q))
        if last:
            self.events.append((self.t, "break", 9))
            self.burst = s
            self.esc = (self.t, x, s * self.plan["v_end"] * 0.8)
            self._knock(s, t, burst=True)
            self.finish()

    def _index(self, s: int) -> np.ndarray:
        return np.arange(self.L * NZ * NY) + (0 if s < 0 else self.L * NZ * NY)

    def _world(self, s: int, flat: np.ndarray, t: float) -> np.ndarray:
        f = self.face_at(t)
        x = s * (f + self.dep.ravel()[flat])
        return np.stack([x, self.by.ravel()[flat], self.bz.ravel()[flat]], 1)

    def _knock(self, s: int, t: float, burst: bool = False) -> None:
        """Beads knocked out by this hit fly back into the gap (or, at the burst, all the rest outwards)."""
        g = self.gone[s].ravel()
        flat = np.nonzero(g > t if burst else g == t)[0]
        if not len(flat):
            return
        ids = flat + (0 if s < 0 else self.L * NZ * NY)
        P = self._world(s, flat, self.t)
        self.P[ids] = P
        self.Pprev[ids] = P
        rnd = self.rnd
        n = len(flat)
        if burst:
            out = np.array([rnd.uniform(0.8, 3.0) for _ in range(n)])
            self.V[ids, 0] = s * out
            self.V[ids, 1] = [rnd.uniform(0.3, 1.6) for _ in range(n)]
            self.V[ids, 2] = [(z - self.z0) * 4 + rnd.uniform(-0.8, 0.8) for z in P[:, 2]]
            self.gone[s].ravel()[flat] = self.t
        else:
            self.V[ids, 0] = [-s * rnd.uniform(0.6, 2.2) for _ in range(n)]
            self.V[ids, 1] = [rnd.uniform(0.6, 2.0) for _ in range(n)]
            self.V[ids, 2] = [rnd.uniform(-0.7, 0.7) for _ in range(n)]
        if burst and len(self.loose):  # the rubble in front of the burst wall is blown out too
            L = self.loose[s * self.P[self.loose, 0] > 0]
            self.V[L, 0] = s * np.array([rnd.uniform(0.5, 2.0) for _ in range(len(L))])
            self.V[L, 1] = [rnd.uniform(0.2, 1.0) for _ in range(len(L))]
        u = np.clip(self.dep.ravel()[flat] / self.thick, 0, 1)
        self.lcol[ids] = (u * (SHADES - 1) + 0.5).astype(int) + (0 if s < 0 else SHADES)
        self.loose = np.concatenate([self.loose, ids])

    def _loose(self, h: float) -> None:
        idx = self.loose
        if not len(idx):
            return
        P, V = self.P, self.V
        self.Pprev[idx] = P[idx]
        V[idx, 1] -= 9.81 * h
        P[idx] += V[idx] * h
        low = P[idx, 1] < RBD
        j = idx[low]
        P[j, 1] = RBD
        V[j, 1] = np.abs(V[j, 1]) * 0.3
        V[j, 0] *= 0.9
        V[j, 2] *= 0.9
        if self.end is None:  # the press bulldozes the beads in the gap; squeezed ones pop up onto the walls
            f = self.face_at(self.t) - RBD
            top = NY * 2 * RBD + RBD
            ax = np.abs(P[idx, 0])
            foot = (ax > f) & (ax < f + self.thick + 2 * RBD) & (np.abs(P[idx, 2]) < NZ * RBD) & (P[idx, 1] < top)
            k = idx[foot]
            if f > RBD:
                P[k, 0] = np.sign(P[k, 0]) * f
                V[k, 0] = -np.sign(P[k, 0]) * np.abs(V[k, 0]) * 0.2
            else:
                P[k, 1] = top
                V[k] = 0.0

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, 0.1, 0), dist=9.0, yaw=1.32, pitch=0.92, fov=30, cy=H * 0.555)
        self.studio = sim3d.Studio(self.cam, 0.0, slab=1.75, thick=0.18, tint=self.tint)
        self._spr: dict = {}

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _wall(self, s: int, t: float):
        present = self.gone[s] > t
        pad = np.pad(present, 1, constant_values=False)
        pad[:, :, 0] = True                                       # the platform hides the bottom
        inner = pad[1:-1, 1:-1, 1:-1]
        hid = (pad[2:, 1:-1, 1:-1] & pad[:-2, 1:-1, 1:-1] & pad[1:-1, 2:, 1:-1] & pad[1:-1, :-2, 1:-1]
               & pad[1:-1, 1:-1, 2:] & pad[1:-1, 1:-1, :-2])
        vis = np.nonzero((inner & ~hid).ravel())[0]
        P = self._world(s, vis, t)
        u = np.clip(self.dep.ravel()[vis] / self.thick, 0, 1)
        sh = self.shades[s]
        cols = [sh[int(v * (SHADES - 1) + 0.5)] for v in u]
        if t - self.flash[s] < 0.09 and self.end is None:        # the beads around the impact light up
            near = np.hypot(P[:, 2] - self.z0, P[:, 1] - RB) < RB + 2.5 * RBD
            near &= self.dep.ravel()[vis] < self.depth[s] + 3 * RBD
            for q in np.nonzero(near)[0]:
                cols[q] = WHITE
        return P, cols

    def _heat(self) -> tuple:
        u = float(np.clip((self._speed() - 4.5) / 7.0, 0, 1))
        return sim3d.lerp_col(WHITE, (255, 150, 50), u)

    def _speed(self) -> float:
        i = min(max(self.hi, 1), len(self.hits) - 1)
        a, b = self.hits[i - 1], self.hits[i]
        return abs(b[2] - a[2]) / max(1e-9, b[0] - a[0])

    def render(self, p):
        t = self.t
        pts, cols = [], []
        for s in (-1, 1):
            P, c = self._wall(s, t)
            pts.append(P)
            cols += c
        a = (self.steps % PHYS) / PHYS
        L = self.loose
        if len(L):
            pts.append(self.Pprev[L] + (self.P[L] - self.Pprev[L]) * a)
            both = self.shades[-1] + self.shades[1]
            cols += [both[c] for c in self.lcol[L]]
        ball = np.array([[self.ball_x, RB, self.z0]])
        pts.append(ball)
        heat = self._heat()
        cols.append(heat)
        P = np.vstack(pts)
        rad = np.full(len(P), RBD)
        rad[-1] = RB
        img = self.studio.back.copy()
        sh = np.vstack([P[-1:], P[len(P) - 1 - len(L):-1]]) if len(L) else P[-1:]
        img = self.studio.shadows(img, sh, np.full(len(sh), RBD) if len(sh) > 1 else np.array([RB]))
        x, y, z, s = self.cam.project(P)
        rp = np.maximum(1, np.rint(rad * s)).astype(int)
        for j in np.argsort(-z):
            r = int(rp[j])
            spr = self._sprite(cols[j], r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        # glow around the ball, hotter with speed
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        bx, by, br = float(x[-1]) / 4, float(y[-1]) / 4, float(RB * s[-1]) / 4
        u = float(np.clip((self._speed() - 4.5) / 7.0, 0, 1))
        rr = br * (1.5 + 0.7 * u)
        gd.ellipse((bx - rr, by - rr, bx + rr, by + rr), fill=(int(40 + 60 * u), int(40 + 20 * u), int(48 - 28 * u)))
        glow = glow.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(img, glow)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break" and i < 9:
            p.punch(0.3)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)
        if self.t - self.end > 0.6:
            nxt = _layers(self.ep + 1) * 2 * RBD * 100
            p.centered(d, 600, f"NEXT: PRESS #{self.ep + 1} · {nxt:.0f} CM WALLS", p.f_count, (255, 214, 120), 2)

    def title(self) -> list[str]:
        return ["Can it drill out", "before the walls close?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"PRESS #{self.ep} · BROKE OUT"
        gap = max(0.0, 2 * self.face_at(self.t)) * 100
        left = (self.thick - max(self.depth.values())) * 100
        if gap < 0.5:
            return f"WALLS SHUT · {left:.0f} cm to go"
        return f"PRESS #{self.ep} · gap {gap:.0f} cm · wall {left:.0f} cm"

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"PRESS #{self.ep}", (255, 255, 255)), ("BROKE OUT!", (255, 196, 70))]
