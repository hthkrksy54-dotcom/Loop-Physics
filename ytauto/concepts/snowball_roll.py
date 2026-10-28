"""Snowball roll: a tiny ball rolls down a long slope covered in a carpet of glossy beads and picks up every bead it
rolls over – it grows layer by layer (every colour band of the carpet becomes a new layer of the ball), carves a
bare track through the carpet and gets faster all the way down. Christmas ornaments lie on its path: every one it
swallows plays the next note of the melody. At the bottom stands a wall of ice beads. Can it smash it?

Planned kinematics (like bridge_run): the speed profile is fixed per seed, the ball's radius follows from the beads
it really picks up (R³ = R0³ + K · beads), the pick-up of every bead is computed once up front, so the run length,
every note and the finale are exact. Picked beads stick to the ball where they touched it and roll with it; only the
outer layer is drawn on top of a solid core.

3D (ytauto/sim3d.py look): a carpet of touching spheres coloured by depth in bands, a dark slope under it, the ball
seen from behind by a camera that pulls back as it grows.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

RBD = 0.03                  # carpet bead radius
SP = 2 * RBD                # bead spacing across a row
ROW = SP * 0.866            # row spacing (hex packing)
NXC = 34                    # beads per row
HALF = NXC * RBD            # half width of the carpet
SLOPE = 0.13                # the slope drops this much per metre
R0 = 0.08                   # starting radius of the ball
KV = 0.8e-5                 # R³ grows by this per bead
DELTA = 0.045               # stuck beads stay visible until the ball grew this much past them
HZ = 120                    # planning rate
BANDS = 6                   # colour bands = layers of the ball
OR_R = 0.05                 # ornament radius
WR = 0.04                   # wall bead radius
G = 9.81
WHITE = (250, 250, 255)
ORN = [(235, 40, 50), (255, 200, 60), (210, 214, 230), (40, 200, 110), (60, 140, 255)]
ICE = ((225, 248, 255), (90, 170, 255))
SHADES = 7
FOG = 6


def ground(s):
    return -np.asarray(s) * SLOPE


def _plan(rnd, look) -> dict:
    """The whole run: speed profile, the sway of the path, every bead and ornament the ball picks up and when."""
    T = rnd.uniform(60.5, 69.5)
    v0, v1 = rnd.uniform(1.45, 1.6), rnd.uniform(4.6, 5.0)
    amp, lam, ph = rnd.uniform(0.25, 0.38), rnd.uniform(7.0, 10.0), rnd.uniform(0, 2 * math.pi)
    ts = np.arange(0, T + 1e-9, 1 / HZ)
    v = v0 + (v1 - v0) * (ts / T) ** 1.25
    s = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 / HZ)])
    L = float(s[-1])

    def path_x(q):
        return amp * np.sin(2 * math.pi * np.asarray(q) / lam + ph) * np.clip(np.asarray(q) / 3, 0, 1)

    x = path_x(s)
    # the carpet: rows from s = -3 to past the wall
    rows = int((L + 4.5) / ROW)
    rs = -3.0 + np.arange(rows) * ROW
    bx = (np.arange(NXC) - (NXC - 1) / 2) * SP
    BX = np.tile(bx, (rows, 1)) + np.where(np.arange(rows) % 2, SP / 4, -SP / 4)[:, None]
    band = np.clip((rs / (L + 0.5) * BANDS).astype(int), 0, BANDS - 1)
    # ornaments along the path, getting a little further apart (the ball is faster)
    orn_s, q = [], 1.2
    while q < L - 0.4:
        orn_s.append(q)
        q += (0.34 + 0.16 * q / L) * rnd.uniform(0.8, 1.2)
    orn_s = np.array(orn_s)
    orn_x = path_x(orn_s) + np.array([rnd.uniform(-0.5, 0.5) for _ in orn_s]) * R0
    orn_c = [rnd.randrange(len(ORN)) for _ in orn_s]
    # simulate the pick-up
    pick = np.full((rows, NXC), np.inf)
    R = np.empty(len(ts))
    N = np.empty(len(ts), int)
    n, r = 0, R0
    opick = np.full(len(orn_s), np.inf)
    oi = 0
    for i in range(len(ts)):
        si, xi = s[i], x[i]
        reach = 0.82 * r
        a = max(0, int((si - reach + 3.0) / ROW))
        b = min(rows, int((si + reach + 3.0) / ROW) + 2)
        if b > a:
            dz = rs[a:b, None] - si
            dx = BX[a:b] - xi
            hit = (dx * dx + dz * dz < reach * reach) & np.isinf(pick[a:b])
            k = int(hit.sum())
            if k:
                pick[a:b][hit] = ts[i]
                n += k
        while oi < len(orn_s) and orn_s[oi] - si < 0.8 * r:
            opick[oi] = ts[i]
            n += 6
            oi += 1
        r = (R0 ** 3 + KV * n) ** (1 / 3)
        R[i], N[i] = r, n
    phi = np.concatenate([[0.0], np.cumsum(v[1:] / R[1:] / HZ)])
    wall_s = L + R[-1]
    return dict(T=T, ts=ts, s=s, x=x, v=v, R=R, N=N, phi=phi, L=L, rows=rows, rs=rs, BX=BX, band=band, pick=pick,
                orn_s=orn_s, orn_x=orn_x, orn_c=orn_c, opick=opick, wall_s=wall_s, amp=amp, lam=lam, ph=ph)


def _rot(phi):
    """Local -> world rotation of the rolling ball (it rolls towards -z: the top goes forward)."""
    c, s = math.cos(phi), math.sin(phi)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])


class SnowballRoll(Sim):
    kind = "snowball_roll"
    concept = {
        "created": "2026-10-28T03:30:00+00:00",
        "idea": "A tiny ball rolls down a long slope covered in a carpet of ~80,000 glossy beads (3D) and picks up "
                "every bead it rolls over: it grows layer by layer (each colour band of the carpet becomes a layer "
                "of the ball), carves a bare track and gets faster; every Christmas ornament it swallows plays the "
                "next note (~4 → 10 per second). At the bottom waits a wall of ice beads.",
        "inspiration": "the viral 'snowball effect' / katamari 'it picks up everything' clips and the seasonal "
                       "snowball memes of early winter, rebuilt as a bead material in the style of @particlesflow; "
                       "the shape of our standouts (tower_drop, lava_climb): one hero, a goal that gets closer, "
                       "hits speeding up",
        "finale": "FINAL SPRINT: the giant layered snowball (~7× its start size) slams into the ice wall at full "
                  "speed – wall and ball burst into thousands of beads (slow motion), 'SMASHED!'",
    }
    titles = ["{onscreen}", "It picks up every bead it rolls over – can it smash the wall?",
              "A tiny ball, a slope of 80,000 beads and an ice wall at the bottom"]
    questions = ["How big would it get on a slope twice as long?", "Did you think it would break the wall?",
                 "Which layer colour was the best?"]
    body = ("A tiny ball rolls down a slope covered in a carpet of glossy beads and picks up every bead it rolls over "
            "– it grows layer by layer and gets faster all the way down. Every Christmas ornament it swallows plays "
            "the next note of {song}. At the bottom waits a wall of ice beads. Everything is simulated in 3D, "
            "nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.985
    trend_words = ("ball", "snowball", "grow", "3d", "simulation", "satisfying", "faster", "christmas", "beads")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.3
    full_frame = True
    tempo = "fast"
    cta_y = 1590

    @classmethod
    def planned_end(cls, seed: int) -> float:
        import random
        return random.Random(seed).uniform(60.5, 69.5)

    def __init__(self, seed: int):
        super().__init__(seed)
        plan = self.plan = _plan(self.rnd, self.look)
        self.T = plan["T"]
        self.K = int(plan["rows"] * NXC / 1000) * 1000
        self.oorder = np.argsort(plan["opick"])
        self.oi = 0
        self.band_now = 0
        self.wall_n = 0

    # ---------------------------------------------------------------- physics

    def at(self, t: float, key: str) -> float:
        pl = self.plan
        return float(np.interp(t, pl["ts"], pl[key]))

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        pl = self.plan
        op = pl["opick"]
        while self.oi < len(op) and op[self.oorder[self.oi]] <= self.t:
            self.events.append((self.t, "bounce", int(self.oorder[self.oi])))
            self.oi += 1
        b = min(BANDS - 1, int(self.at(self.t, "s") / (pl["L"] + 0.5) * BANDS))
        if b > self.band_now:
            self.band_now = b
            self.events.append((self.t, "break", b))
        if self.t >= self.T:
            self.events.append((self.t, "break", 99))
            self.finish()

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        pl = self.plan
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 18)])
        self.yaw = look.choice([-0.14, 0.14])
        # colour palette: index = band * SHADES + shade, then ornaments, white, ice
        pal = []
        for b in range(BANDS):
            top, deep = grads[b % len(grads)]
            pal += [sim3d.lerp_col(top, deep, k / (SHADES - 1)) for k in range(SHADES)]
        self.c_orn = len(pal)
        pal += ORN
        self.c_white = len(pal)
        pal.append(WHITE)
        self.c_ice = len(pal)
        pal += [sim3d.lerp_col(ICE[0], ICE[1], k / (SHADES - 1)) for k in range(SHADES)]
        self.pal = pal
        self.bandcol = [pal[b * SHADES + 2] for b in range(BANDS)]
        rows = pl["rows"]
        shade = np.rint(np.abs(pl["BX"]) / HALF * (SHADES - 1)).astype(int)
        self.carpet_c = (pl["band"][:, None] * SHADES + shade).astype(int)
        # everything the ball picks up, in pick order: carpet beads, ornaments and a first coat of white beads
        ri, ci = np.nonzero(np.isfinite(pl["pick"]))
        pt = pl["pick"][ri, ci]
        gp = np.stack([pl["BX"][ri, ci], ground(pl["rs"][ri]) + RBD, -pl["rs"][ri]], 1)
        cols = self.carpet_c[ri, ci]
        rad = np.full(len(pt), RBD)
        om = np.isfinite(pl["opick"])
        opt = pl["opick"][om]
        ogp = np.stack([pl["orn_x"][om], ground(pl["orn_s"][om]) + OR_R, -pl["orn_s"][om]], 1)
        ocol = self.c_orn + np.array(pl["orn_c"])[om]
        n0 = 70
        u = np.array([[look.gauss(0, 1) for _ in range(3)] for _ in range(n0)])
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        pt = np.concatenate([np.full(n0, -1.0), pt, opt])
        gp = np.concatenate([np.zeros((n0, 3)), gp, ogp])
        cols = np.concatenate([np.full(n0, self.c_white), cols, ocol])
        rad = np.concatenate([np.full(n0, RBD), rad, np.full(len(opt), OR_R * 0.9)])
        order = np.argsort(pt, kind="stable")
        self.st_t, self.st_g, self.st_c, self.st_r = pt[order], gp[order], cols[order], rad[order]
        # where on the ball each one sticks (local frame): the direction from the centre at the moment of pick-up
        loc = np.zeros((len(pt), 3))
        Rp = np.interp(self.st_t, pl["ts"], pl["R"])
        for j in range(len(pt)):
            t = self.st_t[j]
            if t < 0:
                loc[j] = u[j]
                continue
            c = self._centre(t)
            d = self.st_g[j] - c
            d /= np.linalg.norm(d) or 1
            sx = max(-0.995, min(0.995, d[0] / 0.8))     # pressed in, it spreads over the whole ball (no bare caps)
            yz = d[1:] / (np.linalg.norm(d[1:]) or 1)
            d = np.array([sx, *(yz * math.sqrt(1 - sx * sx))])
            loc[j] = _rot(self.at(t, "phi")).T @ d
        self.st_l, self.st_R = loc, Rp
        self.st_R[self.st_t < 0] = R0
        # the ice wall
        ws = pl["wall_s"]
        nx, ny, nz = int(2 * (HALF + 0.25) / (2 * WR)), int(1.55 / (2 * WR)), 3
        X, Y, Z = np.meshgrid((np.arange(nx) - (nx - 1) / 2) * 2 * WR, np.arange(ny) * 2 * WR, np.arange(nz) * 2 * WR)
        X = X + np.where((Y / (2 * WR)).astype(int) % 2, WR / 2, -WR / 2)
        self.wall = np.stack([X.ravel(), ground(ws) + WR + Y.ravel(), -(ws + WR + Z.ravel())], 1)
        self.wall_c = self.c_ice + np.rint(Y.ravel() / Y.max() * (SHADES - 1)).astype(int)
        self.wall_n = len(self.wall)
        # the burst at the finale: wall beads and the outer layer of the ball fly off
        T = self.T
        C = self._centre(T)
        dw = self.wall - C
        dist = np.linalg.norm(dw, axis=1, keepdims=True)
        vr = look.random
        jit = np.array([[vr() - 0.5, vr() - 0.3, vr() - 0.5] for _ in range(len(dw))])
        sp = 7.5 / (1 + 1.6 * dist)
        self.wall_v = dw / dist * sp + jit * 2.2 + np.array([0, 1.2, -1.5])
        self.wall_v[:, 2] -= 2.5 * np.exp(-dist[:, 0])
        vis = self._visible(T)
        P = self._stuck_pos(T, vis)
        dc = P - C
        dc /= np.linalg.norm(dc, axis=1, keepdims=True)
        self.burst_p, self.burst_c, self.burst_r = P, self.st_c[vis], self.st_r[vis]
        jit = np.array([[vr() - 0.5, vr() - 0.5, vr() - 0.5] for _ in range(len(P))])
        self.burst_v = dc * (3.0 + 2.5 * np.array([vr() for _ in range(len(P))]))[:, None] + jit * 1.5 \
            + np.array([0, 1.5, 1.2])
        self.bg = self._background()
        self._spr: dict = {}

    def _centre(self, t: float) -> np.ndarray:
        s, r = self.at(t, "s"), self.at(t, "R")
        return np.array([self.at(t, "x"), float(ground(s)) + r, -s])

    def _visible(self, t: float) -> np.ndarray:
        """Indices of the stuck beads that form the outer layer at time t."""
        r = self.at(t, "R")
        a = np.searchsorted(self.st_R, r - DELTA)       # st_R grows with pick order
        rev = 2 * math.pi * r / self.at(t, "v") * 1.1   # at least one full turn, or the layer has a bare side
        a = min(a, np.searchsorted(self.st_t, t - rev))
        b = np.searchsorted(self.st_t, t - 0.1, side="right")
        return np.arange(min(a, b), b)

    def _stuck_pos(self, t: float, idx: np.ndarray) -> np.ndarray:
        r = self.at(t, "R")
        Rm = _rot(self.at(t, "phi"))
        return self._centre(t) + (self.st_l[idx] @ Rm.T) * (r - self.st_r[idx] * 0.35)[:, None]

    def _background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        glow = np.exp(-(((xx - W / 8) / (W / 4 * 0.75)) ** 2 + ((yy - H / 4 * 0.45) / (H / 4 * 0.33)) ** 2))
        arr = np.array(self.tint, np.float32)[None, None, :] * (0.5 + 1.15 * glow)[..., None]
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)

    def _sprite(self, cid: int, fq: int, r: int) -> Image.Image:
        key = (cid, fq, r)
        spr = self._spr.get(key)
        if spr is None:
            c = self.pal[cid]
            if fq:
                q = fq / FOG
                c = tuple(int(a + (b * 1.5 - a) * q) for a, b in zip(c, self.tint))
            spr = self._spr[key] = sim3d._sphere(c, r, ss=3 if r < 40 else 1)
        return spr

    def _cam(self, t: float) -> sim3d.Camera:
        te = min(t, self.T)
        c = self._centre(te)
        r = self.at(te, "R")
        return sim3d.Camera(target=(c[0] * 0.6, c[1] - 0.2 - 0.4 * r, c[2] - 0.9 - 1.2 * r), dist=3.4 + 6.4 * r,
                            yaw=self.yaw, pitch=0.55, fov=36, cy=H * 0.52)

    def render(self, p):
        pl = self.plan
        t = self.t
        cam = self._cam(t)
        img = self.bg.copy()
        te = min(t, self.T)
        s, r = self.at(te, "s"), self.at(te, "R")
        done = self.end is not None and t >= self.end
        tau = t - self.T if done else 0.0
        # the slope under the carpet
        d = ImageDraw.Draw(img)
        q0, q1 = s - 3.0 - 2 * r, min(s + 16.0, pl["wall_s"] + 0.2)
        qs = np.linspace(q0, q1, 24)
        left = np.stack([np.full(24, -HALF - 0.04), ground(qs), -qs], 1)
        right = np.stack([np.full(24, HALF + 0.04), ground(qs), -qs], 1)
        lx, ly, lz, _ = cam.project(left)
        rx, ry, rz, _ = cam.project(right)
        ok = (lz > 0.4) & (rz > 0.4)
        poly = [(float(a), float(b)) for a, b in zip(lx[ok], ly[ok])] + \
               [(float(a), float(b)) for a, b in zip(rx[ok][::-1], ry[ok][::-1])]
        if len(poly) > 3:
            d.polygon(poly, fill=(36, 38, 48))
            d.line([(float(a), float(b)) for a, b in zip(lx[ok], ly[ok])], fill=(70, 72, 86), width=3)
            d.line([(float(a), float(b)) for a, b in zip(rx[ok], ry[ok])], fill=(70, 72, 86), width=3)
        pts, rads, cids = [], [], []
        # carpet beads that are still lying there
        a = max(0, int((s - 2.2 - 2 * r + 3.0) / ROW))
        b = min(pl["rows"], int((s + 13.0 + 3.0) / ROW))
        if b > a:
            lying = pl["pick"][a:b] > t
            rr, cc = np.nonzero(lying)
            rr = rr + a
            pts.append(np.stack([pl["BX"][rr, cc], ground(pl["rs"][rr]) + RBD, -pl["rs"][rr]], 1))
            rads.append(np.full(len(rr), RBD))
            cids.append(self.carpet_c[rr, cc])
        # ornaments still lying there
        om = (pl["opick"] > t) & (pl["orn_s"] > s - 3) & (pl["orn_s"] < s + 13)
        if om.any():
            pts.append(np.stack([pl["orn_x"][om], ground(pl["orn_s"][om]) + OR_R, -pl["orn_s"][om]], 1))
            rads.append(np.full(int(om.sum()), OR_R))
            cids.append(self.c_orn + np.array(pl["orn_c"])[om])
        C = self._centre(te)
        if not done:
            # beads flying up onto the ball
            fa = np.searchsorted(self.st_t, t - 0.1, side="right")
            fb = np.searchsorted(self.st_t, t, side="right")
            if fb > fa:
                idx = np.arange(fa, fb)
                u = ((t - self.st_t[idx]) / 0.1)[:, None]
                dest = self._stuck_pos(t, idx)
                lift = np.sin(np.pi * u) * 0.25 * r * np.array([0, 1, 0])
                pts.append(self.st_g[idx] * (1 - u) + dest * u + lift)
                rads.append(self.st_r[idx])
                cids.append(self.st_c[idx])
            # the outer layer of the ball (only the half facing the camera)
            vis = self._visible(t)
            P = self._stuck_pos(t, vis)
            face = (P - C) @ (cam.eye - C) / np.linalg.norm(cam.eye - C) > -0.15 * r
            pts.append(P[face])
            rads.append(self.st_r[vis][face])
            cids.append(self.st_c[vis][face])
            # the ice wall
            if pl["wall_s"] - s < 16:
                pts.append(self.wall)
                rads.append(np.full(self.wall_n, WR))
                cids.append(self.wall_c)
        else:
            for P0, V0, rr0, cc0 in ((self.wall, self.wall_v, np.full(self.wall_n, WR), self.wall_c),
                                     (self.burst_p, self.burst_v, self.burst_r, self.burst_c)):
                P = P0 + V0 * tau
                P[:, 1] -= G / 2 * tau * tau
                gr = ground(-P[:, 2]) + rr0
                P[:, 1] = np.maximum(P[:, 1], gr)
                pts.append(P)
                rads.append(rr0)
                cids.append(cc0)
        P = np.vstack(pts)
        Rr = np.concatenate(rads)
        Cc = np.concatenate(cids).astype(int)
        x, y, z, sc = cam.project(P)
        rp = np.maximum(1, np.rint(Rr * sc)).astype(int)
        keep = (y > 430) & (y < H + 40) & (x > -40) & (x < W + 40) & (z > 0.5) & (rp < 70)
        fog = np.rint(np.clip((z - cam_dist(cam, C) - 1.0) / 10.0, 0, 0.85) * FOG).astype(int)
        # soft shadow and glow of the ball
        glow = Image.new("RGB", (W // 4, H // 4))
        if not done:
            sx, sy = cam.point((C[0], float(ground(s)), C[2]))
            _, _, _, s1 = cam.project(np.array([C]))
            rs_ = r * float(s1[0])
            dd = ImageDraw.Draw(img, "RGBA")
            dd.ellipse((sx - rs_ * 1.1, sy - rs_ * 0.38, sx + rs_ * 1.1, sy + rs_ * 0.38), fill=(0, 0, 0, 110))
            gd = ImageDraw.Draw(glow)
            cx, cy = cam.point(C)
            gr_ = rs_ * 1.25 / 4
            col = self.bandcol[self.band_now]
            gd.ellipse((cx / 4 - gr_, cy / 4 - gr_, cx / 4 + gr_, cy / 4 + gr_), fill=tuple(int(c * 0.28) for c in col))
        else:
            cx, cy = cam.point(C)
            k = max(0.0, 1 - tau / 1.2)
            gd = ImageDraw.Draw(glow)
            gr_ = 60 + 240 * min(1.0, tau * 3)
            gd.ellipse((cx / 4 - gr_ / 4, cy / 4 - gr_ / 4, cx / 4 + gr_ / 4, cy / 4 + gr_ / 4),
                       fill=(int(255 * k), int(230 * k), int(200 * k)))
        glow = glow.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        core_z = None
        if not done:
            _, _, cz, cs = cam.project(np.array([C]))
            core_z = float(cz[0])
            core_r = max(2, int(round((r - RBD * 0.9) * float(cs[0]) / 3) * 3))
        order = np.argsort(-z)
        for j in order:
            if core_z is not None and z[j] < core_z:      # the core goes behind the beads in front of the centre
                self._paste_core(img, cam, C, core_r)
                core_z = None
            if not keep[j]:
                continue
            ri = int(rp[j])
            spr = self._sprite(int(Cc[j]), int(fog[j]), ri)
            img.paste(spr, (int(x[j]) - ri - 1, int(y[j]) - ri - 1), spr)
        if core_z is not None:
            self._paste_core(img, cam, C, core_r)
        return ImageChops.add(img, glow)

    def _paste_core(self, img, cam, C, r: int) -> None:
        col = tuple(int(c * 0.55) for c in self.bandcol[self.band_now])
        key = ("core", col, r)
        spr = self._spr.get(key)
        if spr is None:
            spr = self._spr[key] = sim3d._sphere(col, r, ss=1)
        cx, cy = cam.point(C)
        img.paste(spr, (int(cx) - r - 1, int(cy) - r - 1), spr)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break" and i < 99:
            p.punch(0.4)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            super().draw_text(p, d)
            return
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["Can the snowball", "smash the ice wall?"]

    def beads(self) -> int:
        return int(self.at(min(self.t, self.T), "N"))

    def counter(self) -> str:
        if self.end is not None:
            return f"{self.beads():,} beads · size ×{self.at(self.T, 'R') / R0:.1f}"
        left = self.plan["L"] - self.at(self.t, "s")
        if self.T - self.t < 9:
            return f"FINAL SPRINT · wall in {left:.0f} m"
        return f"{self.beads():,} beads · wall in {left:.0f} m"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("SMASHED!", (255, 255, 255)), (f"{self.beads():,} BEADS", ICE[0])]


def cam_dist(cam, C) -> float:
    return float(np.linalg.norm(cam.eye - C))
