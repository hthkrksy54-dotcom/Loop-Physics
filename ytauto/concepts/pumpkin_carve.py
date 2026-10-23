"""Pumpkin carve: a giant pumpkin made of 4,000 glossy orange beads sits on the platform; steel balls fly in one
after another and every hit knocks beads out of its face – eye, eye, nose, then the mouth, faster and faster –
until the jack-o'-lantern is carved and the candle inside lights it up.

3D (ytauto/sim3d.py look): the pumpkin is a ribbed shell of touching spheres, the knocked-out beads tumble onto the
platform and pile up, a warm light inside grows with every hole and shines through the carved face. The shots are
planned up front (which beads each hit knocks out, when it lands), so length and sound are exact; the flight,
rebound and the falling beads are simulated.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

FLOOR = -1.0
SLAB = 1.35
RX, RY = 0.92, 0.70          # pumpkin half width / half height
CY = FLOOR + RY * 0.96       # pumpkin centre
NB = 4000                    # beads in the shell
BR = 0.027                   # bead radius (touching)
ZOOM = 1.18                  # face size
RB = 0.06                    # steel ball radius
FLY = 0.42                   # flight time of a shot (s)
PHYS = 6
YAW = 0.18                   # camera yaw; the face looks straight at the camera
ORANGE = ((255, 170, 40), (215, 70, 10))
STEEL = (225, 230, 240)
STEM = (96, 150, 60)
SHADES = 12

# faces in (azimuth, elevation) degrees from the face's centre; azimuth > 0 = right on screen
FACES = {
    "classic": [
        ("LEFT EYE", [(-42, 8), (-12, 8), (-27, 34)]),
        ("RIGHT EYE", [(12, 8), (42, 8), (27, 34)]),
        ("NOSE", [(-8, -6), (8, -6), (0, 8)]),
        ("MOUTH", [(-50, -12), (-34, -16), (-28, -10), (-18, -18), (-6, -18), (0, -11), (6, -18), (18, -18),
                   (28, -10), (34, -16), (50, -12), (38, -32), (16, -44), (-16, -44), (-38, -32)]),
    ],
    "angry": [
        ("LEFT EYE", [(-46, 22), (-12, 8), (-18, 26), (-38, 32)]),
        ("RIGHT EYE", [(12, 8), (46, 22), (38, 32), (18, 26)]),
        ("NOSE", [(-9, -8), (9, -8), (0, 5)]),
        ("MOUTH", [(-52, -8), (-36, -20), (-28, -12), (-16, -24), (-8, -16), (0, -26), (8, -16), (16, -24),
                   (28, -12), (36, -20), (52, -8), (40, -36), (20, -46), (-20, -46), (-40, -36)]),
    ],
    "grin": [
        ("LEFT EYE", [(-40, 10), (-16, 10), (-16, 26), (-28, 34), (-40, 26)]),
        ("RIGHT EYE", [(16, 10), (40, 10), (40, 26), (28, 34), (16, 26)]),
        ("NOSE", [(-7, -4), (7, -4), (0, 8)]),
        ("MOUTH", [(-56, -4), (-30, -18), (0, -22), (30, -18), (56, -4), (44, -26), (22, -40), (0, -44),
                   (-22, -40), (-44, -26)]),
    ],
}


def _inside(x: np.ndarray, y: np.ndarray, poly: list) -> np.ndarray:
    """Points (x, y) inside a polygon (even-odd rule)."""
    res = np.zeros(len(x), bool)
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        cross = (y1 > y) != (y2 > y)
        xs = x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-9)
        res ^= cross & (x < xs)
    return res


def _shell(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Bead centres of a ribbed pumpkin (local, centre at the origin) plus azimuth/elevation in degrees relative to
    the face (which points along +z turned by YAW) and the outward normals."""
    i = np.arange(n) + 0.5
    y = 1 - 2 * i / n
    r = np.sqrt(1 - y * y)
    a = math.pi * (3 - math.sqrt(5)) * i
    x, z = r * np.cos(a), r * np.sin(a)
    az = np.arctan2(x, z)
    rib = 1 - 0.075 * (1 - np.cos(10 * (az - YAW))) / 2 * r          # ten grooves, none at the poles
    dent = 1 - 0.22 * np.clip(y, 0, 1) ** 6                          # the top sinks in around the stem
    P = np.stack([x * RX * rib, y * RY * dent, z * RX * rib], 1)
    N = np.stack([x / RX, y / RY, z / RX], 1)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    azf = np.degrees((az - YAW + math.pi) % (2 * math.pi) - math.pi)
    el = np.degrees(np.arcsin(np.clip(y, -1, 1)))
    return P, N, azf, el


def _plan(rnd: random.Random) -> dict:
    """Which beads every shot knocks out (feature by feature, a random spot each time) and when it lands – scaled so
    the run lasts `target` seconds and the shots come faster and faster."""
    face = rnd.choice(sorted(FACES))
    P, N, az, el = _shell(NB)
    owner = np.full(NB, -1)
    for f, (_, poly) in enumerate(FACES[face]):
        poly = [(x * ZOOM, y * ZOOM) for x, y in poly]
        owner[_inside(az, el, poly) & (owner < 0) & (np.abs(az) < 80)] = f
    shots = []                          # (feature, target bead, [beads knocked out])
    left = owner.copy()
    for f in range(len(FACES[face])):
        while True:
            idx = np.nonzero(left == f)[0]
            if not len(idx):
                break
            j = int(idx[rnd.randrange(len(idx))])
            d = np.linalg.norm(P[idx] - P[j], axis=1)
            take = idx[np.argsort(d)[:1 if f < 3 else 2]]
            left[take] = -1
            shots.append((f, j, [int(v) for v in take]))
    M = len(shots)
    gaps = [1 / (1.6 + 7.5 * (k / M) ** 1.7) for k in range(M)]
    target = rnd.uniform(62.0, 68.0)
    lead = 0.7
    scale = (target - lead) / sum(gaps)
    times, t = [], lead
    for g in gaps:
        times.append(t)
        t += g * scale
    return {"face": face, "owner": owner, "shots": shots, "times": times, "end": times[-1]}


class PumpkinCarve(Sim):
    kind = "pumpkin_carve"
    concept = {
        "created": "2026-10-23T04:30:00+00:00",
        "idea": "A giant pumpkin made of 4,000 glossy orange beads (3D) is carved by steel balls: every hit knocks "
                "a few beads out of its face – left eye, right eye, nose, then the mouth, faster and faster – the "
                "beads tumble onto the platform and a warm light inside grows with every hole.",
        "inspiration": "Halloween week (31 Oct): pumpkin carving and jack-o'-lantern reveals are everywhere on "
                       "TikTok/Reels, crossed with the 'what will it draw?' reveal and the @particlesflow bead look",
        "finale": "the mouth is carved in a final machine-gun burst (~9 hits/s), the last bead pops out and the "
                  "candle inside flares up: the jack-o'-lantern blazes through its carved face, sparks fly out "
                  "(slow motion) – 'IT'S ALIVE!'",
    }
    experiment = "halloween"
    titles = ["{onscreen}", "Every hit carves the pumpkin – wait for the light",
              "4,000 beads, one pumpkin – what face will it carve?"]
    questions = ["What face did you think it would carve?", "Should the next pumpkin be scary or cute?",
                 "Which feature was the most satisfying?"]
    body = ("A pumpkin made of 4,000 glossy beads. Steel balls fly in one after another – every hit plays the next "
            "note of {song} and knocks beads out of its face, eye by eye, until the jack-o'-lantern is carved and the "
            "light inside comes on. Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("halloween", "pumpkin", "jack o lantern", "3d", "satisfying", "simulation", "carving")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.3
    full_frame = True
    cta_y = 1560
    run_ranges = [(60, 66), (62, 70)]

    @classmethod
    def planned_end(cls, seed: int) -> float:
        return _plan(random.Random(seed))["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        plan = _plan(self.rnd)
        self.plan = plan
        self.shots, self.times = plan["shots"], plan["times"]
        self.M = len(self.shots)
        self.feat = FACES[plan["face"]]
        P, N, _, _ = _shell(NB)
        self.home = P + np.array([0.0, CY, 0.0])
        self.N = N
        self.br = np.full(NB, BR)
        self.P = self.home.copy()
        self.Pprev = self.P.copy()
        self.V = np.zeros_like(self.P)
        self.state = np.zeros(NB, np.int8)          # 0 in the shell, 1 knocked out
        self.owner = plan["owner"]
        self.left = [int((self.owner == f).sum()) for f in range(len(self.feat))]
        self.done = [False] * len(self.feat)
        self.carved = 0
        self.total = int((self.owner >= 0).sum())
        self.next = 0
        self.hits = 0
        self.flash = np.full(NB, -9.0)
        rnd = self.rnd
        # every shot comes from a launch point in front of the camera, low left or right
        self.launch = []
        for f, j, _ in self.shots:
            side = rnd.choice([-1, 1])
            self.launch.append(np.array([side * rnd.uniform(1.6, 2.6), FLOOR + rnd.uniform(0.0, 0.6),
                                         rnd.uniform(3.6, 4.4)]))
        self.balls: list[list] = []                  # [pos, vel, alive_until, landed]
        self.embers = np.zeros((0, 3))
        self.ember_v = np.zeros((0, 3))
        self.steps = 0
        look = self.look.rnd
        self.tint = look.choice([(14, 12, 22), (16, 12, 18), (10, 12, 20)])
        self.shades = [sim3d.lerp_col(ORANGE[0], ORANGE[1], i / (SHADES - 1)) for i in range(SHADES)]

    # ---------------------------------------------------------------- physics

    def _flight(self, k: int, t: float) -> np.ndarray:
        """Position of shot k (a ballistic arc that lands on its target bead at its planned time)."""
        p0 = self.launch[k]
        tgt = self.home[self.shots[k][1]] + self.N[self.shots[k][1]] * (RB + BR)
        v0 = (tgt - p0) / FLY + np.array([0, 0.5 * 9.81 * FLY, 0])
        x = t - (self.times[k] - FLY)
        return p0 + v0 * x - np.array([0, 0.5 * 9.81 * x * x, 0]), v0 - np.array([0, 9.81 * x, 0])

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        while self.next < self.M and self.times[self.next] <= self.t:
            self._hit(self.next)
            self.next += 1
        if self.steps % PHYS == 0:
            self._move(PHYS * dt)

    def _hit(self, k: int) -> None:
        f, j, take = self.shots[k]
        rnd = self.rnd
        self.hits += 1
        self.events.append((self.t, "bounce", k))
        pos, vel = self._flight(k, self.t)
        n = self.N[j]
        out = vel - 2 * float(vel @ n) * n                     # the ball rebounds off the shell
        self.balls.append([pos, out * 0.35 + np.array([0, 0.6, 0]), self.t + 3.0, False])
        idx = np.array(take)
        near = np.linalg.norm(self.home - self.home[j], axis=1) < 0.13
        self.flash[near & (self.state == 0)] = self.t
        self.state[idx] = 1
        d = vel / np.linalg.norm(vel)
        for i in idx:  # knocked-out beads tumble forwards and down onto the platform
            self.V[i] = self.N[i] * rnd.uniform(0.5, 1.3) + d * rnd.uniform(0.0, 0.5) + \
                np.array([rnd.uniform(-0.3, 0.3), rnd.uniform(0.2, 0.9), rnd.uniform(-0.2, 0.3)])
        self.carved += len(idx)
        self.left[f] -= len(idx)
        if self.left[f] <= 0 and not self.done[f]:
            self.done[f] = True
            if f < len(self.feat) - 1:
                self.events.append((self.t, "break", f))
        if k == self.M - 1:
            self.events.append((self.t, "break", 9))
            self.finish()
            holes = np.nonzero(self.owner >= 0)[0]
            pick = [int(holes[rnd.randrange(len(holes))]) for _ in range(160)]
            self.embers = self.home[pick] - self.N[pick] * 0.1
            self.ember_v = self.N[pick] * np.array([[rnd.uniform(1.5, 4.0)] for _ in pick]) + \
                np.array([[rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 2.0), rnd.uniform(-0.3, 0.6)] for _ in pick])

    def _move(self, h: float) -> None:
        lo = self.state == 1
        self.Pprev = self.P.copy()
        if lo.any():
            V, P = self.V, self.P
            V[lo, 1] -= 9.81 * h
            P[lo] += V[lo] * h
            on = lo & (np.abs(P[:, 0]) < SLAB) & (np.abs(P[:, 2]) < SLAB) & (P[:, 1] < FLOOR + BR) & \
                (P[:, 1] > FLOOR - 0.2)
            P[on, 1] = FLOOR + BR
            V[on, 1] = np.abs(V[on, 1]) * 0.25
            V[on, 0] *= 0.82
            V[on, 2] *= 0.82
            inside = lo & (np.hypot(P[:, 0], P[:, 2]) < RX * 0.97) & (np.abs(P[:, 1] - CY) < RY)
            P[inside] += self.N[inside] * 0.01                 # never fall back into the shell
            V[lo & (P[:, 1] < FLOOR - 3)] = 0.0
        for b in self.balls:
            if self.t > b[2]:
                continue
            b[1] = b[1] + np.array([0, -9.81 * h, 0])
            b[0] = b[0] + b[1] * h
            if abs(b[0][0]) < SLAB and abs(b[0][2]) < SLAB and FLOOR - 0.2 < b[0][1] < FLOOR + RB:
                b[0][1] = FLOOR + RB
                b[1] = b[1] * np.array([0.8, -0.35, 0.8])
        self.balls = [b for b in self.balls if self.t <= b[2]]
        if len(self.embers):
            self.ember_v[:, 1] -= 3.0 * h
            self.embers = self.embers + self.ember_v * h

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, CY - 0.18, 0), dist=6.7, yaw=YAW, pitch=0.22, fov=30, cy=H * 0.56)
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=SLAB, thick=0.16, tint=self.tint)
        self.view = self.cam.eye - np.array([0, CY, 0])
        self.view /= np.linalg.norm(self.view)
        self._spr: dict = {}
        x, y, _, s = self.cam.project(np.array([[0, CY, 0]]))
        self.cx, self.cy, self.scale = float(x[0]), float(y[0]), float(s[0])
        stem = [(0.0 + 0.03 * math.sin(k * 0.5), CY + RY * 0.8 + k * 0.05, 0.02 * k) for k in range(7)]
        self.stem = np.array(stem)

    def _sprite(self, col, r: int) -> Image.Image:
        key = (col, r)
        s = self._spr.get(key)
        if s is None:
            s = self._spr[key] = self.studio.sprite(col, r)
        return s

    def light(self) -> float:
        """How bright the candle inside is: grows with every carved bead, flares at the finale."""
        base = 0.12 + 0.55 * self.carved / max(1, self.total)
        if self.end is not None:
            base = 1.0 + 0.6 * max(0.0, 1 - (self.t - self.end) / 0.8)
        return base * (0.92 + 0.08 * math.sin(self.t * 23) * math.sin(self.t * 7.3))

    def render(self, p):
        a = (self.steps % PHYS) / PHYS
        P = self.Pprev + (self.P - self.Pprev) * a
        keep = P[:, 1] > FLOOR - 2.0
        idx = np.nonzero(keep)[0]
        balls = [b[0] for b in self.balls]
        if self.next < self.M:  # shots on their way
            for k in range(self.next, self.M):
                if self.times[k] - FLY > self.t:
                    break
                balls.append(self._flight(k, self.t)[0])
        B = np.array(balls) if balls else np.zeros((0, 3))
        pts = np.vstack([P[idx], self.stem, B])
        rad = np.concatenate([self.br[idx], np.full(len(self.stem), 0.07), np.full(len(B), RB)])
        img = self.studio.back.copy()
        img = self.studio.shadows(img, pts, rad)
        x, y, z, s = self.cam.project(pts)
        rp = np.maximum(1, np.rint(rad * s)).astype(int)
        nI, nS = len(idx), len(self.stem)
        fixed = np.zeros(len(pts), bool)
        fixed[:nI] = self.state[idx] == 0
        back = np.zeros(len(pts), bool)
        back[:nI] = fixed[:nI] & ((self.N[idx] @ self.view) < -0.05)
        lit = np.zeros(len(pts), bool)
        lit[:nI] = (self.t - self.flash[idx]) < 0.14
        u = np.clip((CY + RY - P[idx, 1]) / (2 * RY), 0, 1)
        L = self.light()
        warm = min(1.0, L)
        cols = []
        for j in range(len(pts)):
            if j < nI:
                c = self.shades[int(u[j] * (SHADES - 1) + 0.5)]
                if back[j]:  # inside of the shell: dark, warmed by the candle
                    k = 0.28 + 0.6 * warm
                    c = (int(c[0] * k), int(c[1] * k * 0.85), int(c[2] * k * 0.6))
                elif lit[j]:
                    c = (255, 236, 180)
            elif j < nI + nS:
                c = STEM
            else:
                c = STEEL
            cols.append(c)
        zc = float(np.linalg.norm(self.cam.eye - np.array([0, CY, 0])))
        order = np.argsort(-z)
        glow = self._glow(L)
        glowed = False
        for j in order:
            if not glowed and z[j] < zc:
                img = ImageChops.add(img, glow)       # the candle: seen only through the carved holes
                glowed = True
            r = int(rp[j])
            spr = self._sprite(cols[j], r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        if not glowed:
            img = ImageChops.add(img, glow)
        if self.end is not None:
            img = self._sparks(img, L)
        return img

    def _glow(self, L: float) -> Image.Image:
        q = 4
        g = Image.new("RGB", (W // q, H // q))
        d = ImageDraw.Draw(g)
        rx, ry = RX * self.scale / q * 0.95, RY * self.scale / q * 0.95
        cx, cy = self.cx / q, self.cy / q
        v = min(1.6, L)
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(int(min(255, 255 * v)), int(150 * v), int(30 * v)))
        d.ellipse((cx - rx * 0.5, cy - ry * 0.5, cx + rx * 0.5, cy + ry * 0.5),
                  fill=(255, int(min(255, 220 * v)), int(min(255, 110 * v))))
        return g.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)

    def _sparks(self, img: Image.Image, L: float) -> Image.Image:
        q = 2
        g = Image.new("RGB", (W // q, H // q))
        d = ImageDraw.Draw(g)
        x, y, z, s = self.cam.project(self.embers)
        age = self.t - self.end
        fade = max(0.0, 1 - age / 2.4)
        for xi, yi, si in zip(x, y, s):
            r = max(1.5, 0.02 * si / q)
            d.ellipse((xi / q - r, yi / q - r, xi / q + r, yi / q + r),
                      fill=(int(255 * fade), int(200 * fade), int(90 * fade)))
        # the face blazes: a soft halo in front of it
        hx, hy = self.cx / q, self.cy / q
        rr = RX * self.scale / q * 0.8
        k = min(1.0, L - 0.6) if L > 0.6 else 0.0
        d.ellipse((hx - rr, hy - rr * 0.6, hx + rr, hy + rr * 0.6), fill=(int(70 * k), int(36 * k), int(6 * k)))
        g = g.filter(ImageFilter.GaussianBlur(2)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(img, g)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.45)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["What will the hits", "carve into it?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"{self.hits} hits · {self.carved} beads carved"
        names = [n for n, _ in self.feat]
        done = sum(self.done)
        return f"{self.hits} hit{'' if self.hits == 1 else 's'} · part {done + 1}/{len(names)}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("IT'S", (255, 255, 255)), ("ALIVE!", ORANGE[0])]
