"""3D toolkit for Loop Physics concepts: sheets and piles of glossy spheres, simulated and rendered in 3D.

The style: thousands of touching spheres that behave like one soft material (a net, a cloth, a membrane), coloured
by depth, on a clean platform in a dark studio, seen from a fixed oblique camera – everything simulated, nothing
animated by hand.

- `Camera`: perspective projection (world y points up, 1 unit ≈ 1 m).
- `Sheet`: an n×n net of spheres (position based dynamics): links between neighbours that stretch and can tear,
  pinned points, collisions with `Balls` and the platform.
- `Balls`: free heavy spheres that collide with the sheet, each other and the platform; reports hits for the sound.
- `Studio`: background, floor grid, platform slab, frame posts (rendered once, supersampled), soft shadows and
  depth-sorted shaded sphere sprites.

A 3D concept sets `full_frame = True` and paints the whole 1080×1920 picture in `render(p)`; the Painter puts the
title, counter, credit and finale text on top (see concepts/giant_net.py).
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit
from PIL import Image, ImageDraw, ImageFilter

from .sims import H, W

LIGHT = np.array([-0.42, -0.72, 0.55])  # screen space: x right, y down, z towards the viewer
LIGHT = LIGHT / np.linalg.norm(LIGHT)

# (top colour, deep colour) of the depth gradient – sheets read like a height map
GRADIENTS = [
    ((255, 214, 64), (255, 92, 28)),     # gold -> orange
    ((176, 112, 255), (64, 92, 255)),    # violet -> blue
    ((150, 240, 70), (20, 170, 120)),    # lime -> teal
    ((255, 120, 200), (255, 140, 40)),   # pink -> orange
    ((90, 230, 255), (150, 70, 255)),    # cyan -> purple
    ((255, 80, 80), (255, 190, 60)),     # red -> amber
]


def lerp_col(a, b, u: float) -> tuple[int, int, int]:
    return tuple(int(round(x + (y - x) * u)) for x, y in zip(a, b))


class Camera:
    """Fixed oblique camera looking at `target` from `dist`, turned by `yaw` around the vertical axis and tilted
    down by `pitch` (radians); `fov` is the vertical field of view in degrees; (cx, cy) is the screen centre."""

    def __init__(self, target=(0.0, 0.0, 0.0), dist=5.0, yaw=0.6, pitch=0.6, fov=30.0, cx=W / 2, cy=H * 0.55):
        self.target = np.array(target, float)
        self.eye = self.target + dist * np.array([math.cos(pitch) * math.sin(yaw), math.sin(pitch),
                                                  math.cos(pitch) * math.cos(yaw)])
        f = self.target - self.eye
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, [0.0, 1.0, 0.0])
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.focal = (H / 2) / math.tan(math.radians(fov) / 2)
        self.cx, self.cy = cx, cy

    def project(self, P: np.ndarray):
        """World points (…,3) -> screen x, screen y, depth (distance along the view) and pixels per world unit."""
        d = np.asarray(P, float) - self.eye
        z = np.maximum(d @ self.f, 1e-6)
        s = self.focal / z
        return self.cx + (d @ self.r) * s, self.cy - (d @ self.u) * s, z, s

    def point(self, p) -> tuple[float, float]:
        x, y, _, _ = self.project(np.array([p], float))
        return float(x[0]), float(y[0])


# ---------------------------------------------------------------- physics


class Balls:
    """Free spheres: position, velocity, radius, inverse mass; `on` = already dropped into the scene."""

    def __init__(self, cap: int) -> None:
        self.p = np.zeros((cap, 3))
        self.v = np.zeros((cap, 3))
        self.r = np.ones(cap) * 0.1
        self.w = np.ones(cap)
        self.on = np.zeros(cap, bool)
        self.touch = np.zeros(cap, np.int8)    # last physics step: 1 = touched the sheet, 2 = another ball
        self.col = [(255, 255, 255)] * cap
        self.n = 0

    def add(self, p, v, r: float, mass: float, col) -> int:
        """Drop a ball into the scene; mass = math.inf makes a fixed obstacle (a dome, a post, a big sphere)."""
        i = self.n
        self.p[i], self.v[i], self.r[i], self.w[i], self.col[i] = p, v, r, 1.0 / mass, col
        self.on[i] = True
        self.n += 1
        return i


class Sheet:
    """An n×n net of touching spheres spanning `size` × `size` at height y0, centred on the origin.

    Extended position based dynamics (XPBD, compiled with numba): every physics step predicts positions under
    gravity, then `iters` times pulls linked neighbours (straight and diagonal) towards their rest distance with
    the given `compliance` (0 = rigid links, larger = stretchier net that bounces like a trampoline), pushes spheres
    out of the balls and the platform, and derives the velocities from the moves. A link breaks when it is stretched
    beyond `tear` × its rest length (per sphere in `tear`, so a weak spot can be made). Pinned spheres hold it."""

    def __init__(self, n: int, size: float, y0: float = 0.0, iters: int = 10, compliance: float = 2e-5,
                 tear: float = 9.0) -> None:
        self.n, self.size, self.iters, self.compliance = n, size, iters, compliance
        self.s = size / (n - 1)
        self.r = self.s * 0.5
        g = np.linspace(-size / 2, size / 2, n)
        self.P = np.zeros((n, n, 3))
        self.P[..., 0], self.P[..., 2] = g[None, :], g[:, None]
        self.P[..., 1] = y0
        self.prev = self.P.copy()               # for smooth in-between frames
        self.V = np.zeros_like(self.P)
        self.w = np.ones(n * n)                 # inverse mass per sphere (0 = pinned)
        k = np.arange(n * n).reshape(n, n)
        pairs = [(k[:, :-1], k[:, 1:], 1.0), (k[:-1, :], k[1:, :], 1.0),
                 (k[:-1, :-1], k[1:, 1:], math.sqrt(2)), (k[:-1, 1:], k[1:, :-1], math.sqrt(2))]
        self.la = np.concatenate([a.ravel() for a, _, _ in pairs]).astype(np.int64)
        self.lb = np.concatenate([b.ravel() for _, b, _ in pairs]).astype(np.int64)
        self.rest = np.concatenate([np.full(a.size, f * self.s) for a, _, f in pairs])
        self.alive = np.ones(len(self.la), np.int8)
        self.tear = np.full(n * n, tear)        # per sphere: its links snap beyond this stretch
        self.broken = 0

    def pin_border(self) -> None:
        w = self.w.reshape(self.n, self.n)
        w[0, :] = w[-1, :] = w[:, 0] = w[:, -1] = 0.0

    def step(self, h: float, balls: Balls, floor: float, g: float = -9.81, damp: float = 0.996) -> int:
        """One physics step of h seconds for the sheet and the balls; returns the number of links that broke."""
        self.prev = self.P.copy()
        tear2 = (np.minimum(self.tear[self.la], self.tear[self.lb]) * self.rest) ** 2
        broke = _xpbd(self.P.reshape(-1, 3), self.V.reshape(-1, 3), self.w, self.la, self.lb, self.rest, self.alive,
                      tear2, self.compliance / (h * h), self.n, self.s, self.size / 2, self.r,
                      balls.p, balls.v, balls.r, balls.w, balls.on, balls.touch, floor, h, g, self.iters, damp)
        self.broken += broke
        return broke

    def lerp(self, a: float) -> np.ndarray:
        return self.prev + (self.P - self.prev) * a


@njit(cache=True)
def _xpbd(P, V, w, la, lb, rest, alive, tear2, alpha, n, s, half, r, bp, bv, br, bw, bon, touch, floor, h, g, iters,
          damp):  # compiled: plain loops are fast here
    N = P.shape[0]
    X = P.copy()
    for i in range(N):
        if w[i] > 0:
            V[i, 1] += g * h
            for c in range(3):
                X[i, c] = P[i, c] + V[i, c] * h
    m = bp.shape[0]
    B0 = bp.copy()
    for k in range(m):
        touch[k] = 0
        if bon[k] and bw[k] > 0:
            bv[k, 1] += g * h
            for c in range(3):
                bp[k, c] += bv[k, c] * h
    lam = np.zeros(la.shape[0])
    for it in range(iters):
        for e in range(la.shape[0]):
            if alive[e] == 0:
                continue
            a, b = la[e], lb[e]
            ws = w[a] + w[b]
            if ws == 0:
                continue
            dx, dy, dz = X[b, 0] - X[a, 0], X[b, 1] - X[a, 1], X[b, 2] - X[a, 2]
            L = math.sqrt(dx * dx + dy * dy + dz * dz)
            if L < 1e-12:
                continue
            dl = (-(L - rest[e]) - alpha * lam[e]) / (ws + alpha)
            lam[e] += dl
            f = dl / L
            X[a, 0] -= dx * f * w[a]
            X[a, 1] -= dy * f * w[a]
            X[a, 2] -= dz * f * w[a]
            X[b, 0] += dx * f * w[b]
            X[b, 1] += dy * f * w[b]
            X[b, 2] += dz * f * w[b]
        for k in range(m):  # balls push the spheres of the net in their grid window
            if not bon[k]:
                continue
            reach = br[k] + r
            K = int(reach / s) + 2
            j0 = int(round((bp[k, 0] + half) / s))
            i0 = int(round((bp[k, 2] + half) / s))
            for i in range(max(0, i0 - K), min(n, i0 + K + 1)):
                for j in range(max(0, j0 - K), min(n, j0 + K + 1)):
                    q = i * n + j
                    dx, dy, dz = X[q, 0] - bp[k, 0], X[q, 1] - bp[k, 1], X[q, 2] - bp[k, 2]
                    d = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if d >= reach or d < 1e-12:
                        continue
                    if w[q] + bw[k] == 0:
                        continue
                    f = (reach - d) / d / (w[q] + bw[k])
                    X[q, 0] += dx * f * w[q]
                    X[q, 1] += dy * f * w[q]
                    X[q, 2] += dz * f * w[q]
                    bp[k, 0] -= dx * f * bw[k]
                    bp[k, 1] -= dy * f * bw[k]
                    bp[k, 2] -= dz * f * bw[k]
                    touch[k] |= 1
        for k in range(m):  # balls push each other apart
            if not bon[k]:
                continue
            for l in range(k + 1, m):
                if not bon[l]:
                    continue
                dx, dy, dz = bp[l, 0] - bp[k, 0], bp[l, 1] - bp[k, 1], bp[l, 2] - bp[k, 2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                reach = br[k] + br[l]
                if d >= reach or d < 1e-12 or bw[k] + bw[l] == 0:
                    continue
                f = (reach - d) / d / (bw[k] + bw[l])
                bp[k, 0] -= dx * f * bw[k]
                bp[k, 1] -= dy * f * bw[k]
                bp[k, 2] -= dz * f * bw[k]
                bp[l, 0] += dx * f * bw[l]
                bp[l, 1] += dy * f * bw[l]
                bp[l, 2] += dz * f * bw[l]
                touch[k] |= 2
                touch[l] |= 2
        for i in range(N):
            if X[i, 1] < floor + r:
                X[i, 1] = floor + r
        for k in range(m):
            if bon[k] and bw[k] > 0 and bp[k, 1] < floor + br[k]:
                bp[k, 1] = floor + br[k]
    broke = 0
    for e in range(la.shape[0]):  # links stretched beyond their limit snap
        if alive[e] == 0:
            continue
        a, b = la[e], lb[e]
        dx, dy, dz = X[b, 0] - X[a, 0], X[b, 1] - X[a, 1], X[b, 2] - X[a, 2]
        if dx * dx + dy * dy + dz * dz > tear2[e]:
            alive[e] = 0
            broke += 1
    for i in range(N):
        if w[i] > 0:
            for c in range(3):
                V[i, c] = (X[i, c] - P[i, c]) / h * damp
                P[i, c] = X[i, c]
    for k in range(m):
        if bon[k]:
            for c in range(3):
                bv[k, c] = (bp[k, c] - B0[k, c]) / h * damp
            if bp[k, 1] <= floor + br[k] + 1e-6:  # rolling on the platform: a little friction
                bv[k, 0] *= 0.985
                bv[k, 2] *= 0.985
    return broke


# ---------------------------------------------------------------- picture


class Studio:
    """Everything that does not move is rendered once (supersampled): background, floor grid, platform, posts.
    Per frame: soft contact shadows on the platform and the depth-sorted sphere sprites."""

    def __init__(self, cam: Camera, floor_y: float, slab: float = 1.25, thick: float = 0.16, grid: bool = True,
                 tint=(14, 15, 24), posts: list | None = None, post_top: float = 0.0, frame_y: float | None = None,
                 frame_half: float = 1.0) -> None:
        self.cam, self.floor_y, self.slab = cam, floor_y, slab
        self._sprites: dict[tuple, Image.Image] = {}
        ss = 2
        big = Image.new("RGB", (W * ss, H * ss))
        self._background(big, ss, tint, grid)
        d = ImageDraw.Draw(big)
        self._slab(d, ss, slab, thick)
        front = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        fd = ImageDraw.Draw(front)
        if posts:
            ex, ez = self.cam.eye[0], self.cam.eye[2]
            for (x, z) in posts:  # posts nearer to the camera than the centre go in front of the spheres
                near = x * ex + z * ez > 0
                self._post(fd if near else d, ss, x, z, floor_y, post_top)
        if frame_y is not None:
            self._frame(d, fd, ss, frame_y, frame_half)
        self.back = big.resize((W, H), Image.BOX)
        self.front = front.resize((W, H), Image.BOX)

    def _background(self, img: Image.Image, ss: int, tint, grid: bool) -> None:
        w, h = img.size
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = self.cam.point((0.0, self.floor_y, 0.0))
        glow = np.exp(-(((xx - cx * ss) / (w * 0.55)) ** 2 + ((yy - cy * ss) / (h * 0.33)) ** 2))
        shade = 0.55 + 0.9 * glow
        arr = np.array(tint, np.float32)[None, None, :] * shade[..., None]
        if grid:  # floor grid lines, fading with distance
            gy = self.floor_y - 0.0
            lines = np.zeros((h, w), np.float32)
            gimg = Image.new("L", (w, h))
            gd = ImageDraw.Draw(gimg)
            for k in np.arange(-6, 6.01, 0.5):
                for a, b in (((k, gy, -6), (k, gy, 6)), ((-6, gy, k), (6, gy, k))):
                    pts = np.linspace(a, b, 40)
                    x, y, z, _ = self.cam.project(pts)
                    seg = [(float(x[i]) * ss, float(y[i]) * ss) for i in range(len(x)) if z[i] > 0.5]
                    if len(seg) > 1:
                        gd.line(seg, fill=255, width=2 * ss // 2 + 1)
            lines = np.asarray(gimg, np.float32) / 255 * (0.25 + 0.75 * glow)
            arr += lines[..., None] * np.array([60, 70, 110], np.float32) * 0.55
        img.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)))

    def _quad(self, d, ss, pts3, col, light: float) -> None:
        pts = [tuple(c * ss for c in self.cam.point(p)) for p in pts3]
        d.polygon(pts, fill=tuple(int(c * light) for c in col))

    def _slab(self, d, ss, a: float, t: float) -> None:
        y1, y0 = self.floor_y, self.floor_y - t
        col = (58, 60, 70)
        ex, ez = self.cam.eye[0], self.cam.eye[2]
        sides = [((a, -a), (a, a), 0.62 if ex > 0 else None), ((-a, a), (-a, -a), 0.62 if ex < 0 else None),
                 ((-a, a), (a, a), 0.46 if ez > 0 else None), ((a, -a), (-a, -a), 0.46 if ez < 0 else None)]
        for (x0, z0), (x1, z1), lit in sides:
            if lit:
                self._quad(d, ss, [(x0, y1, z0), (x1, y1, z1), (x1, y0, z1), (x0, y0, z0)], col, lit)
        self._quad(d, ss, [(-a, y1, -a), (a, y1, -a), (a, y1, a), (-a, y1, a)], col, 1.0)
        # a thin bright edge on the top face reads as a bevel
        top = [self.cam.point(p) for p in [(-a, y1, -a), (a, y1, -a), (a, y1, a), (-a, y1, a), (-a, y1, -a)]]
        d.line([(x * ss, y * ss) for x, y in top], fill=(96, 98, 112), width=2 * ss)

    def _post(self, d, ss, x: float, z: float, y0: float, y1: float, rad: float = 0.025) -> None:
        a, b = self.cam.point((x, y0, z)), self.cam.point((x, y1, z))
        _, _, _, s = self.cam.project(np.array([[x, (y0 + y1) / 2, z]]))
        w = max(2, int(rad * 2 * float(s[0]) * ss))
        d.line([(a[0] * ss, a[1] * ss), (b[0] * ss, b[1] * ss)], fill=(70, 72, 84, 255), width=w)
        d.line([(a[0] * ss - w * 0.2, a[1] * ss), (b[0] * ss - w * 0.2, b[1] * ss)], fill=(120, 122, 136, 255),
               width=max(1, w // 4))

    def _frame(self, d, fd, ss, y: float, a: float) -> None:
        ex, ez = self.cam.eye[0], self.cam.eye[2]
        bars = [((-a, -a), (a, -a)), ((a, -a), (a, a)), ((a, a), (-a, a)), ((-a, a), (-a, -a))]
        for (x0, z0), (x1, z1) in bars:
            mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
            near = mx * ex + mz * ez > 0
            p0, p1 = self.cam.point((x0, y, z0)), self.cam.point((x1, y, z1))
            _, _, _, s = self.cam.project(np.array([[mx, y, mz]]))
            w = max(3, int(0.05 * float(s[0]) * ss))
            (fd if near else d).line([(p0[0] * ss, p0[1] * ss), (p1[0] * ss, p1[1] * ss)], fill=(64, 66, 78, 255),
                                     width=w)

    def sprite(self, col: tuple, r: int) -> Image.Image:
        key = (col, r)
        spr = self._sprites.get(key)
        if spr is None:
            spr = self._sprites[key] = _sphere(col, r)
        return spr

    def shadows(self, img: Image.Image, pts: np.ndarray, radii: np.ndarray, strength: float = 0.55) -> Image.Image:
        """Soft shadows straight below the given world points onto the platform top (light from above)."""
        q = 4
        mask = Image.new("L", (W // q, H // q))
        md = ImageDraw.Draw(mask)
        a = self.slab
        keep = (np.abs(pts[:, 0]) < a) & (np.abs(pts[:, 2]) < a)
        if keep.any():
            S = pts[keep].copy()
            hgt = np.clip(S[:, 1] - self.floor_y, 0, 3)
            S[:, 1] = self.floor_y
            x, y, _, s = self.cam.project(S)
            rr = radii[keep] * s * (1.1 + 0.5 * hgt) / q
            v = (255 * strength / (1 + 2.2 * hgt)).astype(int)
            for xi, yi, ri, vi in zip(x / q, y / q, rr, v):
                md.ellipse((xi - ri, yi - ri * 0.55, xi + ri, yi + ri * 0.55), fill=int(vi))
        mask = mask.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
        return Image.composite(Image.new("RGB", (W, H), (4, 4, 8)), img, mask)

    def spheres(self, img: Image.Image, pts: np.ndarray, radii: np.ndarray, cols: list) -> None:
        """Paint spheres (world centres, world radii, colours) back to front."""
        x, y, z, s = self.cam.project(pts)
        rp = np.maximum(1, np.rint(radii * s)).astype(int)
        for k in np.argsort(-z):
            r = int(rp[k])
            spr = self.sprite(cols[k], r)
            img.paste(spr, (int(x[k]) - r - 1, int(y[k]) - r - 1), spr)


def _sphere(col, r: int, ss: int = 3) -> Image.Image:
    """A glossy shaded sphere (key light top left, specular highlight, soft rim, bounce light from below)."""
    R = r * ss
    size = (2 * r + 2) * ss
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = size / 2
    x, y = (xx - c) / R, (yy - c) / R
    rr = x * x + y * y
    z = np.sqrt(np.clip(1 - rr, 0, 1))
    nl = np.clip(x * LIGHT[0] + y * LIGHT[1] + z * LIGHT[2], 0, 1)
    hx, hy, hz = LIGHT[0], LIGHT[1], LIGHT[2] + 1
    hn = math.sqrt(hx * hx + hy * hy + hz * hz)
    spec = np.clip((x * hx + y * hy + z * hz) / hn, 0, 1) ** 60
    base = np.array(col, np.float32)
    rgb = base[None, None, :] * (0.2 + 0.85 * nl)[..., None]
    rgb += base[None, None, :] * (0.18 * np.clip(y, 0, 1) * (1 - z))[..., None]   # bounce light from below
    rgb *= (0.72 + 0.28 * z)[..., None]                                            # soft rim
    rgb += 255 * 0.75 * spec[..., None]
    alpha = np.clip((1 - np.sqrt(rr)) * R + 0.5, 0, 1) * 255
    arr = np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA").resize((2 * r + 2, 2 * r + 2), Image.BOX)
