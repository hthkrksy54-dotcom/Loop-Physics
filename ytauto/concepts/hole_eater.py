"""Hole eater: a black hole in the platform swallows a city of glossy beads – pebbles, cubes, trees, houses,
towers – and grows with everything it eats, faster and faster, until it is big enough for the golden tower.

The hole.io formula (one of the most viral satisfying formats) rebuilt in the 3D bead look of ytauto/sim3d.py: every
object is a stack of touching shaded spheres coloured by height, it tumbles into the hole and sinks into the dark.
A numbered series (experiment "series"): LEVEL #N – the golden tower is two floors taller every level and the
finale teases the next one. The episode number is the seed + 1: the whole run is planned up front (path, growth,
every swallow), so every seed fits the run ranges and the seed search always takes the next free seed.

Planned kinematics, no XPBD: the hole spirals inwards along a path whose spacing follows its radius, every object
falls the moment it lies completely over the hole – so length, sound and picture are exact by construction.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

A = 2.75                 # platform half size (m)
RB = 0.04                # carpet bead radius
R0, RF = 0.17, 0.74      # hole radius at the start / when it reaches the golden tower
G = 9.81
SHADES = 10
GOLD = ((255, 222, 90), (220, 120, 20))
CARPET = ((120, 150, 255), (90, 230, 210))


def _hole_r(r: float, r0: float) -> float:
    """Hole radius by how far the spiral has come inwards (r = distance of the hole from the centre)."""
    u = min(1.0, max(0.0, 1 - r / r0))
    return R0 + (RF - R0) * u ** 1.25


def _plan(rnd: random.Random, ep: int) -> dict:
    """Path, timing, every object and the moment it falls – the whole run, planned exactly."""
    floors = min(30, 16 + 2 * (ep - 1))          # the golden tower grows two floors every level
    r0 = A - 0.22
    th = rnd.uniform(0, 2 * math.pi)
    turn = rnd.choice([-1, 1])
    pts, rads, r = [], [], r0
    while r > 0.0:                               # inward spiral; one turn moves in by 1.55 hole radii
        R = _hole_r(r, r0)
        pts.append((r * math.cos(th), r * math.sin(th)))
        rads.append(R)
        dth = 0.006 / max(r, 0.12)
        th += turn * dth
        r -= 1.35 * R / (2 * math.pi) * dth
    pts.append((0.0, 0.0))
    rads.append(RF)
    P = np.array(pts)
    Rr = np.array(rads)
    seg = np.hypot(*(P[1:] - P[:-1]).T)
    S = np.concatenate([[0.0], np.cumsum(seg)])  # arc length per path sample
    L = S[-1]
    target = rnd.uniform(62.0, 68.0)
    arrive = target - 1.1                        # the hole reaches the tower; it sinks for ~1 s, then the finale
    k = 3.2 / arrive                             # speed grows 4.2× from start to the tower
    v0 = L / (arrive + k * arrive * arrive / 2)

    def time_at(s):                              # s(t) = v0 (t + k t²/2)  ->  t(s)
        return (-1 + np.sqrt(1 + 2 * k * np.asarray(s) / v0)) / k

    T = time_at(S)
    # objects: placed ahead of the hole along the path, sized to what the hole will be when it gets there
    objs = []                                    # (x, z, foot, kind, size)
    kinds = ["cube", "gem", "pillar", "tree", "house", "pyramid", "tower"]
    t = 0.25
    while t < arrive - 1.2:
        s = v0 * (t + k * t * t / 2)
        i = min(len(S) - 1, int(np.searchsorted(S, s)))
        R = Rr[i]
        j = min(len(S) - 1, i + 3)
        dx, dz = P[j] - P[max(0, i - 3)]
        n = math.hypot(dx, dz) or 1.0
        for _ in range(4):                       # a few tries to find a free spot
            f = R * rnd.uniform(0.28, 0.62)
            off = rnd.uniform(-0.4, 0.4) * R
            x, z = P[i][0] - dz / n * off, P[i][1] + dx / n * off
            if math.hypot(x, z) > 0.72 + f and all((x - o[0]) ** 2 + (z - o[1]) ** 2 > (f + o[2] + 0.02) ** 2
                                                   for o in objs[-40:]):
                u = t / arrive
                pool = kinds[:3] if u < 0.25 else kinds[:5] if u < 0.55 else kinds
                objs.append((x, z, f, rnd.choice(pool), rnd.uniform(0.85, 1.15)))
                break
        t += 0.42 - 0.24 * (t / arrive) ** 0.8     # 2.4 -> 5.5 objects per second
    # carpet of small beads over the whole platform
    g = np.arange(-A + 0.09, A - 0.08, 2.05 * RB * 1.3)
    cx, cz = np.meshgrid(g, g)
    cx = cx.ravel() + np.array([rnd.uniform(-0.012, 0.012) for _ in range(cx.size)])
    cz = cz.ravel() + np.array([rnd.uniform(-0.012, 0.012) for _ in range(cz.size)])
    rc = np.hypot(cx, cz)
    keep = (rc > 0.85) & (rc < r0 + R0 * 0.5)    # a round city; room for the golden tower
    for x, z, f, _, _ in objs:
        keep &= np.hypot(cx - x, cz - z) > f + RB
    cx, cz = cx[keep], cz[keep]
    return {"P": P, "R": Rr, "S": S, "T": T, "objs": objs, "carpet": (cx, cz), "arrive": arrive,
            "floors": floors, "v0": v0, "k": k, "end": arrive + 1.0, "turn": turn}


def _fall_times(P, Rr, T, x, z, foot) -> np.ndarray:
    """First moment the hole covers each point completely (centre distance < R - foot); inf if never."""
    out = np.full(len(x), np.inf)
    chunk = 400
    for a in range(0, len(x), chunk):
        X, Z, F = x[a:a + chunk, None], z[a:a + chunk, None], foot[a:a + chunk, None]
        d = np.hypot(P[None, :, 0] - X, P[None, :, 1] - Z)
        ok = d < (Rr[None, :] - F)
        hit = ok.any(1)
        first = ok.argmax(1)
        out[a:a + chunk][hit] = T[first[hit]]
    return out


def _shape(kind: str, foot: float, size: float, rnd: random.Random):
    """Bead offsets (relative to the object's floor centre) and their height share for colouring."""
    pts = []
    if kind == "gem":                           # one big glossy bead
        return np.array([[0.0, foot * 0.8, 0.0]]), np.array([foot * 0.8]), np.array([1.0])
    if kind == "tree":                          # trunk column + round crown
        rb = foot / 3.2
        h = int(3 * size) + 2
        pts += [(0, rb + 2 * rb * i, 0) for i in range(h)]
        cy = rb + 2 * rb * h + rb * 1.4
        for a in range(-2, 3):
            for b in range(-2, 3):
                for c in range(-2, 3):
                    if a * a + b * b + c * c <= 5:
                        pts.append((a * rb * 1.6, cy + c * rb * 1.6, b * rb * 1.6))
    else:
        n = {"cube": 3, "pillar": 2, "house": 4, "pyramid": 5, "tower": 3}[kind]
        rb = foot / (n * 1.42)
        hgt = {"cube": 3, "pillar": int(5 * size) + 2, "house": 3, "pyramid": 0, "tower": int(8 * size) + 4}[kind]
        c0 = -(n - 1) * rb
        for y in range(hgt):
            for i in range(n):
                for j in range(n):
                    edge = i in (0, n - 1) or j in (0, n - 1) or y == hgt - 1
                    if edge or n <= 3:
                        pts.append((c0 + 2 * rb * i, rb + 2 * rb * y, c0 + 2 * rb * j))
        if kind in ("house", "pyramid"):        # a stepped roof
            base = hgt
            m = n
            while m > 0:
                c = -(m - 1) * rb
                for i in range(m):
                    for j in range(m):
                        pts.append((c + 2 * rb * i, rb + 2 * rb * base, c + 2 * rb * j))
                base += 1
                m -= 1
    p = np.array(pts, float)
    top = p[:, 1].max() or 1.0
    return p, np.full(len(p), rb), p[:, 1] / top


def _tower(floors: int):
    """The golden tower: a hollow square column of beads with a stepped crown."""
    rb, n = 0.05, 7
    c0 = -(n - 1) * rb
    pts = []
    for y in range(floors):
        for i in range(n):
            for j in range(n):
                if i in (0, n - 1) or j in (0, n - 1):
                    pts.append((c0 + 2 * rb * i, rb + 2 * rb * y, c0 + 2 * rb * j))
    base, m = floors, n
    while m > 0:
        c = -(m - 1) * rb
        for i in range(m):
            for j in range(m):
                if m <= 2 or i in (0, m - 1) or j in (0, m - 1):
                    pts.append((c + 2 * rb * i, rb + 2 * rb * base, c + 2 * rb * j))
        base += 1
        m -= 2
    p = np.array(pts, float)
    return p, np.full(len(p), rb), p[:, 1] / p[:, 1].max()


class HoleEater(Sim):
    kind = "hole_eater"
    concept = {
        "created": "2026-10-24T03:30:00+00:00",
        "idea": "A black hole in a platform swallows a whole city of glossy beads (3D) – a carpet of thousands of "
                "beads, cubes, trees, houses, towers – it grows with everything it eats and gets faster and faster, "
                "spiralling inwards to the golden tower in the middle. A numbered series: LEVEL #N, the tower gets "
                "two floors taller every level.",
        "inspiration": "the hole.io 'hole eats everything' clips that keep going viral on TikTok and Shorts, rebuilt "
                       "as a bead material in the style of @particlesflow, plus our speed-up formula and the "
                       "'series' follow experiment (tower_drop ×2.2)",
        "finale": "the hole is finally big enough: the golden tower tilts and sinks into the dark in one piece "
                  "(slow motion), then the hole opens up and swallows the rest of the platform – 'NEXT: LEVEL #N+1'",
    }
    titles = ["{onscreen}", "Level {n}: can the hole eat the whole city – and the golden tower?",
              "This hole eats everything – level {n}, wait for the golden tower"]
    questions = ["Which object was the most satisfying to fall in?", "How tall should the golden tower be at "
                 "level {n} + 1?", "Would you have gone for the tower earlier?"]
    body = ("Level {n}: a black hole swallows a city of glossy beads – every object it eats plays the next note of "
            "{song}, the carpet of small beads clicks – and it grows and speeds up with every bite until it is big "
            "enough for the golden tower. Every level the tower is two floors taller. Everything is simulated in 3D, "
            "nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("hole", "eats", "everything", "3d", "satisfying", "simulation", "city", "asmr")
    slowmo = True
    note_gap = 0.08
    finale_punch = 1.1
    full_frame = True
    tempo = "fast"
    experiment = "series"
    cta_y = 1560
    run_ranges = [(60, 66), (63, 70)]   # every seed fits: the seed search takes the next one, so levels count up

    @classmethod
    def planned_end(cls, seed: int) -> float:
        return _plan(random.Random(seed), seed + 1)["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        self.ep = self.n = seed + 1
        rnd = self.rnd
        plan = self.plan = _plan(rnd, self.ep)
        self.K = plan["floors"]
        P, Rr, T = plan["P"], plan["R"], plan["T"]
        self.PT = T
        # every bead of the scene: world rest position, radius, colour index, object id
        shapes = []
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.grad_cols = [[sim3d.lerp_col(top, deep, i / (SHADES - 1)) for i in range(SHADES)] for top, deep in grads]
        self.gold = [sim3d.lerp_col(GOLD[0], GOLD[1], i / (SHADES - 1)) for i in range(SHADES)]
        self.carpet_cols = [sim3d.lerp_col(*look.choice([CARPET, ((255, 150, 200), (150, 120, 255)),
                                                         ((150, 240, 120), (90, 200, 255))]), i / (SHADES - 1))
                            for i in range(SHADES)]
        objs = plan["objs"]
        ox, oz, of = (np.array([o[i] for o in objs]) for i in range(3))
        cx, cz = plan["carpet"]
        self.n_obj = len(objs)
        # object 0..n_obj-1, then carpet beads, then the tower
        cents, foots, lists = [], [], []
        for oi, (x, z, f, kind, size) in enumerate(objs):
            p, r, u = _shape(kind, f, size, rnd)
            gi = oi % len(self.grad_cols)
            cols = [self.grad_cols[gi][int((1 - v) * (SHADES - 1) + 0.5)] for v in u]
            shapes.append((p, r, cols))
        tp, tr, tu = _tower(self.K)
        self.tower_shape = (tp, tr, [self.gold[int((1 - v) * (SHADES - 1) + 0.5)] for v in tu])
        fo = _fall_times(P, Rr, T, ox, oz, of) if len(objs) else np.zeros(0)
        fc = _fall_times(P, Rr, T, cx, cz, np.full(len(cx), RB * 0.3))
        self.shapes = shapes
        self.obj_c = np.stack([ox, oz], 1) if len(objs) else np.zeros((0, 2))
        self.obj_f = of
        self.obj_t = fo
        self.car = np.stack([cx, cz], 1)
        self.car_t = fc
        self.car_col = [self.carpet_cols[int(((x + z) / (4 * A) + 0.5) * (SHADES - 1) + 0.5)] for x, z in self.car]
        self.tower_t = plan["arrive"] - 0.15
        self.total = sum(len(s[0]) for s in shapes) + len(cx) + len(tp)
        self.bead_w = np.array([len(s[0]) for s in shapes])
        # the schedule: (time, kind, index) – melody for every object, a click for carpet beads, crack for big ones
        sched = [(float(t), "obj", i) for i, t in enumerate(fo) if np.isfinite(t)]
        sched += [(float(t), "car", i) for i, t in enumerate(fc) if np.isfinite(t)]
        sched.append((self.tower_t, "tower", 0))
        sched.sort()
        self.sched = sched
        self.si = 0
        self.eaten = 0
        self.objs_eaten = 0
        self.last_note = -9.0
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])
        self.rim = look.choice([(90, 200, 255), (255, 90, 160), (150, 255, 120), (255, 170, 60)])
        # fall direction of every object: towards the hole centre at the moment it falls
        self.obj_dir = np.zeros((self.n_obj, 2))
        self.obj_spin = np.array([rnd.uniform(1.5, 4.0) * rnd.choice([-1, 1]) for _ in range(self.n_obj)])
        for i in range(self.n_obj):
            if np.isfinite(fo[i]):
                hx, hz = self.hole(fo[i])[:2]
                d = np.array([hx, hz]) - self.obj_c[i]
                n = np.hypot(*d)
                self.obj_dir[i] = d / n if n > 1e-6 else (1.0, 0.0)

    # ---------------------------------------------------------------- planned motion

    def hole(self, t: float) -> tuple[float, float, float]:
        """Hole centre x, z and radius at time t (after the finale it opens up over the whole platform)."""
        T, P, Rr = self.PT, self.plan["P"], self.plan["R"]
        if t >= T[-1]:
            R = RF
            if self.end is not None and t > self.end + 0.5:
                R = RF + (A * 1.6 - RF) * min(1.0, (t - self.end - 0.5) / 2.2) ** 1.6
            return 0.0, 0.0, R
        i = int(np.searchsorted(T, t))
        i = max(1, min(len(T) - 1, i))
        a = (t - T[i - 1]) / max(1e-9, T[i] - T[i - 1])
        x = P[i - 1, 0] + (P[i, 0] - P[i - 1, 0]) * a
        z = P[i - 1, 1] + (P[i, 1] - P[i - 1, 1]) * a
        return x, z, Rr[i - 1] + (Rr[i] - Rr[i - 1]) * a

    def step(self, dt: float) -> None:
        self.t += dt
        while self.si < len(self.sched) and self.sched[self.si][0] <= self.t:
            _, what, i = self.sched[self.si]
            self.si += 1
            if self.end is not None:
                continue
            if what == "obj":
                self.eaten += int(self.bead_w[i])
                self.objs_eaten += 1
                if self.t - self.last_note >= self.note_gap:
                    self.events.append((self.t, "bounce", i))
                    self.last_note = self.t
                else:
                    self.events.append((self.t, "clack", i))
                if self.objs_eaten % 40 == 0:
                    self.events.append((self.t, "break", i))
            elif what == "car":
                self.eaten += 1
                self.events.append((self.t, "clack", i))
            else:
                self.tower_fell = self.t
                self.events.append((self.t, "bounce", -1))
                self.events.append((self.t, "break", -1))
        if self.end is None and self.t >= self.plan["end"]:
            self.eaten += len(self.tower_shape[0])
            self.finish()

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        glow = np.exp(-(((xx - W / 8) / (W / 4 * 0.7)) ** 2 + ((yy - H / 8 * 1.1) / (H / 4 * 0.4)) ** 2))
        arr = np.array(self.tint, np.float32)[None, None, :] * (0.45 + 1.0 * glow)[..., None]
        self.bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        self._spr: dict = {}

    def _sprite(self, col, r: int) -> Image.Image:
        if r > 10:  # big sprites in ~6 % steps: far fewer to shade, the eye cannot tell
            r = int(round(10 * 1.06 ** round(math.log(r / 10) / math.log(1.06))))
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = sim3d._sphere(col, r)
        return s

    def _cam(self, t: float) -> sim3d.Camera:
        hx, hz, R = self.hole(min(t, self.PT[-1]))
        u = (R - R0) / (RF - R0)
        w = min(1.0, u ** 1.5 * 0.9)
        tx, tz = hx * (1 - w), hz * (1 - w)
        dist = 2.7 + 6.6 * u ** 1.1
        ty = 0.15 * u
        if self.end is not None and t > self.end:  # pull back to see the platform go
            e = min(1.0, (t - self.end) / 2.5)
            dist += 2.5 * e * e
        return sim3d.Camera(target=(tx, ty, tz), dist=dist, yaw=0.55, pitch=1.12 - 0.2 * u, fov=34, cy=H * 0.53)

    def _fall(self, tau: np.ndarray, d: np.ndarray, spin: np.ndarray, off: np.ndarray, c: np.ndarray,
              heavy: float = 1.0) -> np.ndarray:
        """Bead positions of falling objects: slide towards the hole centre, tilt over, drop."""
        tau = np.maximum(tau, 0)
        slide = np.minimum(tau, 0.25) * 0.9
        ang = np.minimum(tau * np.abs(spin) * 0.9, 1.4) * np.sign(spin)
        # tilt the offset around the horizontal axis perpendicular to the fall direction
        ax = np.stack([-d[:, 1], np.zeros(len(d)), d[:, 0]], 1)
        cos, sin = np.cos(ang)[:, None], np.sin(ang)[:, None]
        rot = off * cos + np.cross(ax, off) * sin + ax * (np.sum(ax * off, 1, keepdims=True)) * (1 - cos)
        x = c[:, 0] + d[:, 0] * slide + rot[:, 0]
        z = c[:, 1] + d[:, 1] * slide + rot[:, 2]
        y = rot[:, 1] - 0.5 * G * heavy * tau ** 2
        return np.stack([x, y, z], 1)

    def render(self, p):
        t = self.t
        cam = self._cam(t)
        img = self.bg.copy()
        dr = ImageDraw.Draw(img)
        self._floor(dr, cam)
        hx, hz, R = self.hole(t)
        # rim, far inner wall and the dark inside of the hole
        ang = np.linspace(0, 2 * math.pi, 72)
        rim = np.stack([hx + R * np.cos(ang), np.zeros(72), hz + R * np.sin(ang)], 1)
        deep = rim.copy()
        deep[:, 1] = -0.5 * R
        rx, ry, _, _ = cam.project(rim)
        qx, qy, _, _ = cam.project(deep)
        mask = Image.new("L", (W, H))
        md = ImageDraw.Draw(mask)
        poly = [(float(a), float(b)) for a, b in zip(rx, ry)]
        md.polygon(poly, fill=255)
        dr.polygon(poly, fill=(46, 48, 62))
        dr.polygon([(float(a), float(b)) for a, b in zip(qx, qy)], fill=(5, 5, 9))
        # beads: static ones on the floor and falling ones
        pts, rad, cols = [], [], []
        # carpet
        ct = self.car_t
        on = ct > t - 1.2
        idx = np.nonzero(on)[0]
        if len(idx):
            tau = t - ct[idx]
            falling = tau > 0
            y = np.full(len(idx), RB)
            y[falling] = RB - 0.5 * G * tau[falling] ** 2
            pts.append(np.stack([self.car[idx, 0], y, self.car[idx, 1]], 1))
            rad.append(np.full(len(idx), RB))
            cols += [self.car_col[i] for i in idx]
        # objects
        ot = self.obj_t
        for i in np.nonzero(ot > t - 1.3)[0]:
            off, r, oc = self.shapes[i]
            c = self.obj_c[i]
            tau = t - ot[i]
            if tau <= 0:
                P = np.column_stack([off[:, 0] + c[0], off[:, 1], off[:, 2] + c[1]])
            else:
                m = len(off)
                P = self._fall(np.full(m, tau), np.repeat(self.obj_dir[i][None], m, 0),
                               np.full(m, self.obj_spin[i]), off, np.repeat(c[None], m, 0))
            pts.append(P)
            rad.append(r)
            cols += oc
        # the golden tower
        tp, tr, tc = self.tower_shape
        tau = t - self.tower_t
        if tau < 3.0:
            if tau <= 0:
                P = tp.copy()
            else:
                m = len(tp)
                P = self._fall(np.full(m, tau * 0.75), np.repeat(np.array([[0.6, 0.8]]), m, 0),
                               np.full(m, 0.35), tp, np.zeros((m, 2)), heavy=0.55)
            pts.append(P)
            rad.append(tr)
            cols += tc
        if not pts:
            return img
        Pw = np.vstack(pts)
        Rw = np.concatenate(rad)
        x, y, z, s = cam.project(Pw)
        rp = np.maximum(1, np.rint(Rw * s)).astype(int)
        vis = (x > -40) & (x < W + 40) & (y > -40) & (y < H + 40) & (z > 0.8) & (Pw[:, 1] > -2.5)
        below = vis & (Pw[:, 1] < -Rw * 0.2)
        above = vis & ~below
        # beads inside the hole: darker the deeper they are, only visible through the opening
        if below.any():
            layer = img.copy()
            for j in np.nonzero(below)[0][np.argsort(-z[below])]:
                k = max(0.12, 1 + Pw[j, 1] / max(0.4, 1.4 * R))
                k = round(k * 8) / 8
                col = tuple(int(c * k) for c in cols[j])
                spr = self._sprite(col, int(rp[j]))
                h = spr.width // 2
                layer.paste(spr, (int(x[j]) - h, int(y[j]) - h), spr)
            img = Image.composite(layer, img, mask)
        # contact shadows of what stands on the floor (quarter resolution)
        sh = Image.new("L", (W // 4, H // 4))
        sd = ImageDraw.Draw(sh)
        for i in np.nonzero(ot > t)[0]:
            cxp, cyp = cam.point((self.obj_c[i, 0], 0.0, self.obj_c[i, 1]))
            _, _, _, ss = cam.project(np.array([[self.obj_c[i, 0], 0.0, self.obj_c[i, 1]]]))
            rr = self.obj_f[i] * float(ss[0]) / 4 * 1.25
            sd.ellipse((cxp / 4 - rr, cyp / 4 - rr * 0.6, cxp / 4 + rr, cyp / 4 + rr * 0.6), fill=150)
        if tau <= 0:
            cxp, cyp = cam.point((0.0, 0.0, 0.0))
            _, _, _, ss = cam.project(np.array([[0.0, 0.0, 0.0]]))
            rr = 0.5 * float(ss[0]) / 4
            sd.ellipse((cxp / 4 - rr, cyp / 4 - rr * 0.6, cxp / 4 + rr, cyp / 4 + rr * 0.6), fill=170)
        sh = sh.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
        sh = ImageChops.multiply(sh, ImageChops.invert(mask))
        img = Image.composite(Image.new("RGB", (W, H), (4, 4, 8)), img, sh)
        # glowing rim (pulses with every object it eats)
        last = max((e[0] for e in self.events[-6:] if e[1] in ("bounce", "break")), default=-9.0)
        flash = max(0.0, 1 - (t - last) / 0.25)
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        gcol = tuple(int(c * (0.55 + 0.45 * flash)) for c in self.rim)
        gd.line([(a / 4, b / 4) for a, b in poly] + [(poly[0][0] / 4, poly[0][1] / 4)], fill=gcol, width=3)
        glow = glow.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        img = ImageChops.add(img, glow)
        dr = ImageDraw.Draw(img)
        dr.line(poly + [poly[0]], fill=tuple(min(255, int(c * 0.7 + 255 * 0.3 * flash)) for c in self.rim), width=3)
        # beads above the floor, back to front
        for j in np.nonzero(above)[0][np.argsort(-z[above])]:
            spr = self._sprite(cols[j], int(rp[j]))
            h = spr.width // 2
            img.paste(spr, (int(x[j]) - h, int(y[j]) - h), spr)
        return img

    def _floor(self, d: ImageDraw.ImageDraw, cam: sim3d.Camera) -> None:
        a, th = A, 0.18
        top = [(-a, 0, -a), (a, 0, -a), (a, 0, a), (-a, 0, a)]
        ex, ez = cam.eye[0], cam.eye[2]
        col = (58, 60, 72)
        for (x0, z0), (x1, z1), lit in [((a, -a), (a, a), ex > 0), ((-a, a), (-a, -a), ex < 0),
                                        ((-a, a), (a, a), ez > 0), ((a, -a), (-a, -a), ez < 0)]:
            if lit:
                q = [cam.point(p) for p in [(x0, 0, z0), (x1, 0, z1), (x1, -th, z1), (x0, -th, z0)]]
                d.polygon(q, fill=tuple(int(c * (0.62 if x0 == x1 else 0.46)) for c in col))
        q = [cam.point(p) for p in top]
        d.polygon(q, fill=col)
        for k in np.arange(-a, a + 0.01, 0.5):   # faint tiles on the platform
            for p0, p1 in (((k, 0, -a), (k, 0, a)), ((-a, 0, k), (a, 0, k))):
                d.line([cam.point(p0), cam.point(p1)], fill=(66, 68, 82), width=2)
        d.line(q + [q[0]], fill=(98, 100, 116), width=3)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.25 if i >= 0 else 0.6)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)
        if self.t - self.end > 0.6:
            p.centered(d, 600, f"NEXT: LEVEL #{self.ep + 1} · {min(30, self.K + 2)}-FLOOR TOWER", p.f_count,
                       (255, 214, 120), 2)

    def title(self) -> list[str]:
        return ["Can the hole eat", "the golden tower?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"LEVEL #{self.ep} · 100% EATEN"
        if self.t >= self.tower_t:
            return "THE TOWER FALLS!"
        pct = min(99, int(100 * self.eaten / self.total))
        return f"LEVEL #{self.ep} · {pct}% eaten"

    def finale(self) -> list[tuple[str, tuple]]:
        return [(f"LEVEL #{self.ep}", (255, 255, 255)), ("CLEARED!", GOLD[0])]
