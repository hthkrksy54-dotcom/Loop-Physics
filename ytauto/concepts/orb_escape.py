"""Orb escape: a ball is trapped inside nested glass orbs made of glossy spheres – every hit makes it faster and
knocks beads out of the orb, until the orb shatters and the next, bigger one begins.

3D (ytauto/sim3d.py look): every orb is a shell of touching spheres that dents and wobbles under each hit (soft
springs) and loses the beads around the impact; the loose beads rain down onto the platform and pile up. Our best
performers (escape, stringart) are one ball that speeds up with every bounce and breaks out ring by ring – this is
that idea as a 3D material. The outer orbs are drawn as glass (front half faint), so the active orb stays visible.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

FLOOR = -1.2               # platform top (m)
SLAB = 1.25
PHYS = 6                   # beads and wobble every 6th step(): 120 Hz (the ball moves every step)
RB = 0.05                  # hero ball radius
WHITE = (250, 250, 255)
GOLD = ((255, 214, 64), (255, 92, 28))
OTHERS = [((176, 112, 255), (64, 92, 255)), ((150, 240, 70), (20, 170, 120)), ((255, 120, 200), (255, 140, 40)),
          ((90, 230, 255), (150, 70, 255)), ((255, 80, 80), (255, 190, 60))]
SHADES = 16


def _fib(n: int, rnd) -> np.ndarray:
    """n points spread evenly over the unit sphere (Fibonacci lattice), randomly turned."""
    i = np.arange(n) + 0.5
    y = 1 - 2 * i / n
    r = np.sqrt(1 - y * y)
    a = math.pi * (3 - math.sqrt(5)) * i + rnd.uniform(0, 2 * math.pi)
    return np.stack([r * np.cos(a), y, r * np.sin(a)], 1)


class OrbEscape(Sim):
    kind = "orb_escape"
    concept = {
        "created": "2026-10-22T03:30:00+00:00",
        "idea": "A ball is trapped inside 5–6 nested glass orbs, each made of hundreds of touching spheres (3D). "
                "Every hit makes it faster, dents the orb and knocks beads out, which rain onto the platform – after "
                "enough hits (or through a hole) the orb shatters and the next, bigger one begins.",
        "inspiration": "the viral 'will the ball escape' ring shorts (our best performer) rebuilt as a 3D particle "
                       "material in the style of @particlesflow",
        "finale": "the golden outer orb shatters at top speed: every bead bursts outwards and rains onto the "
                  "platform while the ball flies free (slow motion)",
    }
    titles = ["{onscreen}", "Every hit makes it faster – can it break out of all the orbs?",
              "One ball, {k} orbs of glass beads – wait for the golden one"]
    questions = ["Which orb did you think would hold it?", "How fast was it at the end?"]
    body = ("A ball trapped inside nested orbs made of glossy beads. Every hit makes it faster, plays the next note "
            "of {song} and knocks beads out of the orb – until it shatters and the next one begins. Everything is "
            "simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.93
    trend_words = ("escape", "ball escape", "3d", "orb", "faster", "simulation", "satisfying")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.2
    full_frame = True
    tempo = "fast"
    cta_y = 1540

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.K = K = rnd.choice([5, 6, 6])
        self.R = [0.3 + 0.7 * k / (K - 1) for k in range(K)]
        base = rnd.uniform(32, 36) * (6 / K) ** 1.4  # the first orb breaks fast (hook), the golden one lasts
        self.hp = [int(round(base * (0.45 + 0.75 * k))) for k in range(K)]
        self.hp0 = list(self.hp)
        unit, rad, shell = [], [], []
        for k, R in enumerate(self.R):
            n = int(200 + 330 * k / (K - 1))
            unit.append(_fib(n, rnd))
            rad.append(np.full(n, 0.47 * math.sqrt(4 * math.pi * R * R / n)))
            shell.append(np.full(n, k))
        self.U = np.vstack(unit)               # rest direction of every bead
        self.br = np.concatenate(rad)          # bead radius
        self.shell = np.concatenate(shell)
        self.Rb = np.array(self.R)[self.shell]
        self.dr = np.zeros(len(self.U))        # radial dent (soft spring) and its speed
        self.dv = np.zeros(len(self.U))
        self.state = np.zeros(len(self.U), np.int8)   # 0 in the orb, 1 loose
        self.P = self.U * self.Rb[:, None]
        self.V = np.zeros_like(self.P)
        self.Pprev = self.P.copy()
        a = rnd.uniform(0, 2 * math.pi)
        e = rnd.uniform(-0.5, 0.5)
        self.v0 = rnd.uniform(1.7, 2.0)
        self.acc = rnd.uniform(1.0045, 1.0055)
        self.top = 7.5
        d = np.array([math.cos(a) * math.cos(e), math.sin(e), math.sin(a) * math.cos(e)])
        self.bp = np.zeros(3)
        self.bv = d * self.v0
        self.bprev = self.bp.copy()
        self.k = 0                  # active orb
        self.n = 0                  # step counter
        self.hits = 0
        self.last_note = -1.0
        self.flash = np.full(len(self.U), -9.0)
        self.broke_at = [-9.0] * K
        look = self.look.rnd
        grads = list(OTHERS)
        look.shuffle(grads)
        self.grads = [grads[k % len(grads)] for k in range(K - 1)] + [GOLD]
        self.shades = [[sim3d.lerp_col(top, deep, i / (SHADES - 1)) for i in range(SHADES)] for top, deep in self.grads]
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 16)])

    def speed(self) -> float:
        return float(np.linalg.norm(self.bv))

    def step(self, dt: float) -> None:
        self.t += dt
        self.n += 1
        self.bprev = self.bp.copy()
        self.bp = self.bp + self.bv * dt
        if self.end is None:
            self._ball(dt)
        if self.n % PHYS == 0:
            self._beads(PHYS * dt)

    def _ball(self, dt: float) -> None:
        k = self.k
        R = self.R[k] - float(self.br[self.shell == k][0]) * 0.8
        d = float(np.linalg.norm(self.bp))
        if d + RB < R:
            return
        nrm = self.bp / d
        if float(self.bv @ nrm) <= 0:
            return
        idx = np.nonzero((self.shell == k) & (self.state == 0))[0]
        cosang = self.U[idx] @ nrm
        near = idx[np.argsort(-cosang)[:4]]
        gap = self.R[k] * math.acos(min(1.0, float(cosang.max()))) if len(idx) else 9.0
        spacing = 2 * float(self.br[idx[0]]) / 0.94 if len(idx) else 0.0
        if gap > max(spacing * 2.1, RB * 2.4):  # it found a hole: out it goes
            self._shatter(k, nrm)
            return
        self.bp = nrm * (R - RB)
        v = self.bv - 2 * float(self.bv @ nrm) * nrm
        rnd = self.rnd
        v = v + np.array([rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)]) * 0.18 * float(np.linalg.norm(v))
        v -= max(0.0, float(v @ nrm)) * nrm * 1.2  # still pointing back inside
        sp = min(self.top, self.speed() * self.acc)
        self.bv = v / np.linalg.norm(v) * sp
        self.hits += 1
        self.hp[k] -= 1
        # the dent: beads around the impact are pushed outwards and spring back
        sel = (self.shell == k) & (self.state == 0)
        c = self.U[sel] @ nrm
        self.dv[sel] += np.clip((c - 0.82) / 0.18, 0, 1) * sp * 0.22
        self.flash[sel & (self.U @ nrm > 0.9)] = self.t
        if self.hp[k] <= 0:
            self._shatter(k, nrm)
            return
        if self.t - self.last_note >= self.note_gap:  # the melody where it can sound, the rest clacks
            self.last_note = self.t
            self.events.append((self.t, "bounce", self.hits))
        else:
            self.events.append((self.t, "clack", self.hits))
        chip = near[:1 + (self.hits % 2)]   # the beads right at the impact break loose
        self._loose(chip, sp * 0.18)

    def _loose(self, idx: np.ndarray, kick: float) -> None:
        rnd = self.rnd
        self.state[idx] = 1
        for i in idx:
            out = self.U[i] * (kick + rnd.uniform(0.1, 0.5))
            self.V[i] = out + np.array([rnd.uniform(-0.3, 0.3), rnd.uniform(0, 0.6), rnd.uniform(-0.3, 0.3)])

    def _shatter(self, k: int, nrm: np.ndarray) -> None:
        idx = np.nonzero((self.shell == k) & (self.state == 0))[0]
        self._loose(idx, 0.6 + 0.25 * self.speed())
        self.broke_at[k] = self.t
        self.events.append((self.t, "break", k))
        self.k += 1
        if self.k >= self.K:
            self.finish()
            self.bv = self.bv / self.speed() * 3.0

    def _beads(self, h: float) -> None:
        w = 2 * math.pi * 5.0  # wobble of the orb skin
        a = -w * w * self.dr - 2 * 0.18 * w * self.dv
        self.dv += a * h
        self.dr += self.dv * h
        self.Pprev = self.P.copy()
        fix = self.state == 0
        self.P[fix] = self.U[fix] * (self.Rb[fix] + self.dr[fix])[:, None]
        lo = ~fix
        if lo.any():
            V, P = self.V, self.P
            V[lo, 1] -= 9.81 * h
            P[lo] += V[lo] * h
            on_slab = lo & (np.abs(P[:, 0]) < SLAB) & (np.abs(P[:, 2]) < SLAB)
            hit = on_slab & (P[:, 1] < FLOOR + self.br) & (P[:, 1] > FLOOR - 0.2)
            P[hit, 1] = FLOOR + self.br[hit]
            V[hit, 1] = np.abs(V[hit, 1]) * 0.3
            V[hit, 0] *= 0.8
            V[hit, 2] *= 0.8
            gone = lo & (P[:, 1] < FLOOR - 2.5)
            V[gone] = 0.0

    def good(self) -> bool:
        return self.end is not None

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.25, 0), dist=11.2, yaw=0.62, pitch=0.36, fov=28, cy=H * 0.52)
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=SLAB, thick=0.16, tint=self.tint)
        self._spr: dict = {}
        self.view = self.cam.eye / np.linalg.norm(self.cam.eye)

    def _sprite(self, col, r: int, alpha: int) -> Image.Image:
        key = (col, r, alpha)
        s = self._spr.get(key)
        if s is None:
            s = self.studio.sprite(col, r)
            if alpha < 255:
                s = s.copy()
                s.putalpha(s.getchannel("A").point(lambda v: v * alpha // 255))
            self._spr[key] = s
        return s

    def render(self, p):
        a = (self.n % PHYS) / PHYS
        P = self.Pprev + (self.P - self.Pprev) * a
        keep = P[:, 1] > FLOOR - 2.0
        B = self.bprev + (self.bp - self.bprev) * 1.0
        img = self.studio.back.copy()
        idx = np.nonzero(keep)[0]
        pts = np.vstack([P[idx], B[None, :]])
        rad = np.concatenate([self.br[idx], [RB]])
        img = self.studio.shadows(img, pts, rad)
        x, y, z, s = self.cam.project(pts)
        rp = np.maximum(1, np.rint(rad * s)).astype(int)
        fixed = self.state[idx] == 0
        sh = self.shell[idx]
        front = (self.U[idx] @ self.view) > 0.05
        u = np.clip((self.Rb[idx] - P[idx, 1]) / (2 * self.Rb[idx]), 0, 1)
        lit = (self.t - self.flash[idx]) < 0.16
        for j in np.argsort(-z):
            r = int(rp[j])
            if j == len(idx):
                spr = self._sprite(WHITE, r, 255)
            else:
                k = int(sh[j])
                col = WHITE if lit[j] and fixed[j] else self.shades[k][int(u[j] * (SHADES - 1) + 0.5)]
                if fixed[j] and k > self.k:  # outer orbs are glass: the active one stays in view
                    alpha = 70 if front[j] else 200
                    if not front[j]:
                        col = tuple(int(c * 0.75) for c in col)
                elif fixed[j] and front[j]:  # the active orb's front half lets the ball show through
                    alpha = 150
                else:
                    alpha = 255
                spr = self._sprite(col, r, alpha)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        # a warm halo, so the eye always finds the ball
        bx, by = float(x[-1]), float(y[-1])
        rr = float(RB * s[-1]) * (2.2 + 0.25 * self.speed())
        halo = Image.new("RGB", (W // 4, H // 4))
        heat = min(1.0, self.speed() / self.top)
        ImageDraw.Draw(halo).ellipse(((bx - rr) / 4, (by - rr) / 4, (bx + rr) / 4, (by + rr) / 4),
                                     fill=(int(70 + 60 * heat), int(60 - 20 * heat), int(40 - 30 * heat)))
        halo = halo.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(img, halo)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.5)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["Can the ball escape", f"{self.K} orbs of glass?"]

    def counter(self) -> str:
        k = min(self.k, self.K - 1)
        tag = "GOLDEN ORB" if k == self.K - 1 else f"orb {k + 1}/{self.K}"
        return f"{tag} · speed ×{self.speed() / self.v0:.1f}" if self.end is None else f"speed ×{self.top / self.v0:.1f}"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("IT BROKE", (255, 255, 255)), ("FREE!", GOLD[0])]
