"""Layer drop: a heavy steel ball falls onto a stack of 100 stretchy membranes made of glossy beads, each one stronger
than the one above. The first ones it punches through in a blink; then every layer stretches deeper and holds
longer before it tears – the rhythm slows down, the suspense rises: how many can it break? Some runs it breaks all
100, some runs it gets stuck on one of the last layers and bounces there until it rests.

Planned physics (like bridge_run): the ball falls under gravity, an engaged layer pushes back like a spring that
grows with the stretch (plus a little damping) and tears once it is stretched to its limit. The layer strength is
bisected per seed so the ball fails exactly on the chosen layer (or barely breaks the last), then time is scaled so
the run lands on the target length – every note and every tear is exact.

3D (ytauto/sim3d.py look): every layer is a disc of touching spheres coloured by its strength zone, deflecting
like a membrane under a point load (logarithmic dip); a torn layer throws the beads of its hole downwards and its
ring springs back.
"""
from __future__ import annotations

import math
import random

import numpy as np
from numba import njit
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

NL = 100                    # layers
D = 0.5                     # spacing between layers (m)
RL = 0.62                   # layer radius
RBD = 0.026                 # bead radius
RB = 0.12                   # ball radius
DMIN, DMAX = 0.03, 0.4      # stretch at which a layer tears: first .. last
ZONE = 10                   # layers per colour zone
HZ = 1000                   # planning rate
STEEL = (215, 222, 236)
GOLD = ((255, 222, 90), (255, 140, 30))
SHADES = 6
# strength zones, cool to hot: every 10 layers the next colour, the last 10 are gold
ZONES = [((176, 112, 255), (110, 70, 230)), ((100, 140, 255), (50, 80, 230)), ((90, 220, 255), (30, 150, 230)),
         ((80, 240, 190), (20, 170, 140)), ((150, 240, 70), (60, 180, 40)), ((220, 240, 60), (170, 190, 20)),
         ((255, 200, 60), (230, 150, 20)), ((255, 140, 50), (230, 90, 20)), ((255, 90, 90), (210, 40, 60)), GOLD]
FOG = 5


def _depth(k: int) -> float:
    return DMIN + (DMAX - DMIN) * (k / NL) ** 1.15


@njit(cache=True)
def _integrate(e, g, damp, v0, stop_after, hz, track):
    """Fall through the stack. Layer k (1-based) at y = -k·D absorbs e·g·(0.04 + (k/NL)^2.2) per unit mass before
    it tears at its stretch limit (a spring grown from the tear depth, plus damping). Returns contact and tear times
    per layer, the floor contact, where it got stuck (layer, time) and the ball's height per 1/hz s."""
    y, v, t = 0.0, -v0, 0.0
    h = 1.0 / hz
    k = 1
    contact = np.full(NL + 2, np.inf)
    tear = np.full(NL + 2, np.inf)
    ys = np.zeros(int(400 * hz) if track else 1)
    n = 0
    stuck_k, stuck_t = 0, 0.0
    while t < 399:
        yk = -k * D if k <= NL else -(NL + 1) * D
        x = yk - (y - RB)
        a = -g
        if k <= NL and x > 0:
            if contact[k] == np.inf:
                contact[k] = t
            dk = DMIN + (DMAX - DMIN) * (k / NL) ** 1.15
            E = e * g * (0.04 + (k / NL) ** 2.2)
            a += 2 * E / (dk * dk) * x - damp * v
            if x >= dk:
                tear[k] = t
                k += 1
                continue
            if stuck_k == 0 and v > 0:
                stuck_k, stuck_t = k, t
        if k > NL and x > 0:
            y, v = yk + RB, 0.0
            if contact[NL + 1] == np.inf:
                contact[NL + 1] = t
        v += a * h
        y += v * h
        t += h
        if track:
            ys[n] = y
        n += 1
        if stuck_k and t - stuck_t > stop_after:
            break
        if contact[NL + 1] < np.inf and t - contact[NL + 1] > 0.05:
            break
    return contact, tear, stuck_k, stuck_t, ys[:n], t


def _run(e, g, damp, v0, stop_after=3.0, hz=HZ, track=True) -> dict:
    c, tr, sk, st, ys, end = _integrate(e, g, damp, v0, stop_after, hz, track)
    contact = {k: float(c[k]) for k in range(1, NL + 1) if np.isfinite(c[k])}
    if np.isfinite(c[NL + 1]):
        contact["floor"] = float(c[NL + 1])
    tear = {k: float(tr[k]) for k in range(1, NL + 1) if np.isfinite(tr[k])}
    return {"contact": contact, "tear": tear, "y": ys, "end": float(end), "stuck": (int(sk), float(st)) if sk else None}


def _plan(rnd: random.Random) -> dict:
    target = rnd.uniform(61.0, 69.0)
    S = NL + 1 if rnd.random() < 0.4 else rnd.randint(84, NL)  # NL+1 = it breaks them all
    damp, v0, hz = 1.1, 1.2, 2000

    def fails_at(e: float) -> int:
        sk = _integrate(e, 1.0, damp, v0, 0.01, hz, False)[2]
        return sk if sk else NL + 1

    lo, hi = 0.001, 5.0               # stronger layers stop it earlier: find the strength at the edge of S
    for _ in range(40):
        mid = (lo + hi) / 2
        if fails_at(mid) <= min(S, NL):
            hi = mid
        else:
            lo = mid
    e = hi if S <= NL else lo          # stop: barely fails on S · all: barely breaks the last
    run = _run(e, 1.0, damp, v0, stop_after=0.01, hz=hz, track=False)
    if run["stuck"]:                   # after getting stuck it bounces on for a few seconds
        run = _run(e, 1.0, damp, v0, stop_after=3.0 * (run["end"] / target), hz=hz)
    else:
        run = _run(e, 1.0, damp, v0, hz=hz)
    sc = target / run["end"]           # stretch time (= weaker gravity) so the run lands on the target length
    run["contact"] = {k: v * sc for k, v in run["contact"].items()}
    run["tear"] = {k: v * sc for k, v in run["tear"].items()}
    if run["stuck"]:
        run["stuck"] = (run["stuck"][0], run["stuck"][1] * sc)
    n = len(run["y"])
    run["y"] = np.interp(np.arange(int(target * HZ) + 2) / HZ, np.arange(n) / hz * sc, run["y"])
    run.update(S=S, e=e, g=1 / sc ** 2, end=target)
    return run


class LayerDrop(Sim):
    kind = "layer_drop"
    concept = {
        "created": "2026-10-28T04:30:00+00:00",
        "idea": "A heavy steel ball falls onto a stack of 100 stretchy membranes made of glossy beads (3D), each "
                "stronger than the one above: the first ones it punches through in a blink, then every layer "
                "stretches deeper and holds longer before it tears – the rhythm slows down and the suspense rises. "
                "Some runs it breaks all 100, some runs it gets stuck on one of the last layers.",
        "inspiration": "the viral 'ball vs 100 layers' soft-body simulations (how many layers can it break?), "
                       "rebuilt as bead membranes in the style of @particlesflow; the opposite of our speed-ups: a "
                       "rhythm that slows into suspense (experiment 'suspense')",
        "finale": "the last layers stretch almost down to the next one and hold for seconds – then either the 100th "
                  "golden layer tears and the ball slams onto the floor ('ALL 100!') or it sinks into one, bounces "
                  "and rests ('STUCK ON LAYER 93!')",
    }
    titles = ["{onscreen}", "100 layers, each stronger than the last – how far does the ball get?",
              "Guess before it ends: how many layers will the ball break?"]
    questions = ["What was your guess?", "Which layer did you think would stop it?",
                 "Should the next ball be heavier?"]
    body = ("A heavy steel ball falls onto a stack of 100 stretchy membranes made of glossy beads, each one stronger "
            "than the one above. Every layer it touches plays the next note of {song} – the first ones tear in a "
            "blink, then every layer stretches deeper and holds longer. How many can it break? Everything is "
            "simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.93
    trend_words = ("ball", "layers", "100 layers", "3d", "simulation", "satisfying", "soft body", "how many")
    slowmo = True
    note_gap = 0.05
    finale_punch = 1.1
    full_frame = True
    experiment = "suspense"
    cta_y = 1590

    @classmethod
    def planned_end(cls, seed: int) -> float:
        return _plan(random.Random(seed))["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        plan = self.plan = _plan(self.rnd)
        self.T = plan["end"]
        self.K = NL
        self.ys = plan["y"]
        ev = []
        for k, t in plan["contact"].items():
            ev.append((t, "bounce", NL + 1 if k == "floor" else k))
        for k, t in plan["tear"].items():
            ev.append((t + 1e-6, "break" if k % ZONE == 0 else "clack", k))
            dk = _depth(k)
            tc = plan["contact"][k]
        self.creaks: dict[int, list[float]] = {}
        stuck = plan["stuck"]
        for k, tc in plan["contact"].items():
            if k == "floor":
                continue
            t = plan["tear"].get(k, stuck[1] if stuck and stuck[0] == k else None)
            if t is not None and t - tc > 0.7:              # long stretches creak: a crack flashes around the dent
                for f in (0.4, 0.62, 0.8, 0.93):
                    ev.append((tc + (t - tc) * f, "bounce", 1000 + k))
                    self.creaks.setdefault(k, []).append(tc + (t - tc) * f)
        if stuck:
            k, ts = stuck
            # the ball bounces on the layer that holds: every time it sinks back into it, a note
            y = self.ys
            n0 = int(ts * HZ)
            seg = y[n0:]
            mins = np.nonzero((seg[1:-1] < seg[:-2]) & (seg[1:-1] <= seg[2:]))[0] + 1
            for j in mins[:8]:
                ev.append(((n0 + j) / HZ, "bounce", 2000 + k))
                self.creaks.setdefault(k, []).append((n0 + j) / HZ)
        ev.sort()
        self.plan_ev = ev
        self.ei = 0
        self.broken = 0

    # ---------------------------------------------------------------- physics

    def ball_y(self, t: float) -> float:
        i = min(len(self.ys) - 1, max(0, int(t * HZ)))
        return float(self.ys[i])

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        ev = self.plan_ev
        while self.ei < len(ev) and ev[self.ei][0] <= self.t:
            t, kind, i = ev[self.ei]
            self.events.append((self.t, kind, i))
            if kind in ("clack", "break") and i <= NL:
                self.broken = i
            self.ei += 1
        if self.t >= self.T:
            self.finish()

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        look = self.look.rnd
        grads = list(sim3d.GRADIENTS)
        look.shuffle(grads)
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 18)])
        self.yaw = look.choice([-0.5, 0.5])
        n = int(2 * RL / (2 * RBD)) + 1
        g = (np.arange(n) - (n - 1) / 2) * 2 * RBD
        X, Z = np.meshgrid(g, g)
        X = X + np.where(np.arange(n)[:, None] % 2, RBD / 2, -RBD / 2)
        rho = np.hypot(X, Z)
        m = rho < RL
        self.lx, self.lz, self.rho = X[m], Z[m], rho[m]
        self.nb = len(self.lx)
        self.f = np.clip(np.log(RL / np.maximum(self.rho, 1e-6)) / math.log(RL / (RB * 0.7)), 0, 1)
        self.edge = np.clip(self.rho / RL, 0, 1)
        pal, self.zone_c = [], []
        for top, deep in ZONES:
            self.zone_c.append(len(pal))
            pal += [sim3d.lerp_col(top, deep, k / (SHADES - 1)) for k in range(SHADES)]
        self.c_steel = len(pal)
        pal.append(STEEL)
        self.c_white = len(pal)
        pal.append((255, 255, 255))
        self.pal = pal
        self.shade = np.rint(self.edge * (SHADES - 1)).astype(int)
        # every bead of every layer: where it flies when the layer tears (visual randomness from self.look)
        vr = np.random.default_rng(look.randrange(1 << 30))
        self.kick = vr.normal(0, 1, (NL + 1, self.nb, 3)) * 0.35
        self.kick[..., 1] = -np.abs(self.kick[..., 1])          # torn beads go down, never float up
        self.hole = vr.uniform(0.45, 0.62, NL + 1) * RL
        self.bg = self._background()
        self._spr: dict = {}

    def _background(self) -> Image.Image:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
        glow = np.exp(-(((xx - W / 8) / (W / 4 * 0.7)) ** 2 + ((yy - H / 4 * 0.5) / (H / 4 * 0.35)) ** 2))
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
            spr = self._spr[key] = sim3d._sphere(c, r)
        return spr

    def _cam(self, t: float) -> sim3d.Camera:
        y = self.ball_y(min(t, self.T))
        return sim3d.Camera(target=(0, y - 0.25, 0), dist=4.6, yaw=self.yaw, pitch=0.6, fov=40, cy=H * 0.53)

    def _layer(self, k: int, t: float, by: float):
        """Bead positions, colours of layer k at time t (None when it is out of the picture)."""
        pl = self.plan
        yk = -k * D
        tc = pl["contact"].get(k)
        tt = pl["tear"].get(k)
        cid = self.zone_c[min((k - 1) // ZONE, len(self.zone_c) - 1)] + self.shade
        Y = np.full(self.nb, yk)
        stuck = pl["stuck"]
        if stuck and stuck[0] == k and tc is not None and t >= tc:
            tt = None
        if tc is not None and t >= tc and (tt is None or t < tt):
            x = max(0.0, yk - (by - RB))
            Y = yk - x * self.f
            hot = x / _depth(k)
            if hot > 0.8:
                cid = np.where(self.rho < RB * 2.5, self.c_white, cid)
            for tk in self.creaks.get(k, ()):
                if 0 <= t - tk < 0.09:
                    ring = (self.rho > RB * 1.6 + x * 0.6) & (self.rho < RB * 2.6 + x * 0.9)
                    cid = np.where(ring, self.c_white, cid)
            pts = np.stack([self.lx, Y, self.lz], 1)
            # creak pops: beads at the rim of the dent fly off at the creak moments
            return pts, cid, None
        if tt is not None and t >= tt:
            tau = t - tt
            xt = _depth(k)
            hole = self.hole[k]
            inner = self.rho < hole
            ring_y = yk - xt * self.f * math.exp(-5 * tau) * math.cos(14 * tau)
            g = pl["g"] * 9.81 * 0.35
            v = -0.6 * math.sqrt(pl["g"])
            ky = self.kick[k]
            dbx = self.lx * (1 + 1.6 * tau) + ky[:, 0] * tau
            dbz = self.lz * (1 + 1.6 * tau) + ky[:, 2] * tau
            dby = (yk - xt * self.f) + (v + ky[:, 1]) * tau - g / 2 * tau * tau
            floor = -(k + 1) * D + RBD                       # debris rests on the next layer (until it tears)
            nt = pl["tear"].get(k + 1)
            if k < NL and (nt is None or t < nt):
                dby = np.maximum(dby, floor)
            elif k == NL:
                dby = np.maximum(dby, -(NL + 1) * D + RBD)
            elif dby.min() < by - 4:
                pass
            X = np.where(inner, dbx, self.lx)
            Yv = np.where(inner, dby, ring_y)
            Z = np.where(inner, dbz, self.lz)
            pts = np.stack([X, Yv, Z], 1)
            if k < NL and nt is not None and t > nt + 0.4:   # the debris went down with the next layer
                pts, cid = pts[~inner], cid[~inner]
            return pts, cid, None
        return np.stack([self.lx, Y, self.lz], 1), cid, None

    def render(self, p):
        t = self.t
        pl = self.plan
        by = self.ball_y(min(t, self.T))
        cam = self._cam(t)
        img = self.bg.copy()
        kc = int(round(-by / D))
        pts, cids = [], []
        for k in range(max(1, kc - 3), min(NL, kc + 6) + 1):
            P, c, _ = self._layer(k, t, by)
            pts.append(P)
            cids.append(c if np.ndim(c) else np.full(len(P), c))
        # the floor under the stack: a plate of steel beads
        if kc > NL - 6:
            fl = np.stack([self.lx, np.full(self.nb, -(NL + 1) * D - RBD), self.lz], 1)
            pts.append(fl)
            cids.append(np.full(self.nb, self.c_steel))
        P = np.vstack(pts)
        Cc = np.concatenate(cids).astype(int)
        Rr = np.full(len(P), RBD)
        # posts of the tower
        d = ImageDraw.Draw(img)
        for a in np.arange(4) * math.pi / 2 + math.pi / 4:
            top = cam.point((math.cos(a) * (RL + 0.05), by + 3, math.sin(a) * (RL + 0.05)))
            bot = cam.point((math.cos(a) * (RL + 0.05), max(by - 6, -(NL + 1) * D), math.sin(a) * (RL + 0.05)))
            d.line([top, bot], fill=(52, 54, 66), width=7)
        x, y, z, s = cam.project(P)
        rp = np.maximum(1, np.rint(Rr * s)).astype(int)
        keep = (y > 440) & (y < H + 40) & (x > -40) & (x < W + 40) & (z > 0.5)
        fog = np.rint(np.clip((z - 3.0) / 4.0, 0, 0.8) * FOG).astype(int)
        B = np.array([[0.0, by, 0.0]])
        bx_, by_, bz_, bs = cam.project(B)
        br = max(2, int(round(RB * float(bs[0]))))
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        hot = self._heat(t)
        gr = br * (1.6 + 1.4 * hot) / 4
        gd.ellipse((bx_[0] / 4 - gr, by_[0] / 4 - gr, bx_[0] / 4 + gr, by_[0] / 4 + gr),
                   fill=(int(40 + 160 * hot), int(40 + 90 * hot), int(60 - 20 * hot)))
        if self.end is not None and t >= self.end and pl["stuck"] is None:
            k = max(0.0, 1 - (t - self.end) / 1.0)
            gd.ellipse((bx_[0] / 4 - 70, by_[0] / 4 - 30, bx_[0] / 4 + 70, by_[0] / 4 + 30),
                       fill=(int(255 * k), int(220 * k), int(120 * k)))
        glow = glow.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        ball_done = False
        for j in np.argsort(-z):
            if not ball_done and z[j] < float(bz_[0]):
                self._ball(img, bx_[0], by_[0], br)
                ball_done = True
            if not keep[j]:
                continue
            r = int(rp[j])
            spr = self._sprite(int(Cc[j]), int(fog[j]), r)
            img.paste(spr, (int(x[j]) - r - 1, int(y[j]) - r - 1), spr)
        if not ball_done:
            self._ball(img, bx_[0], by_[0], br)
        return ImageChops.add(img, glow)

    def _ball(self, img, x, y, r) -> None:
        key = ("ball", r)
        spr = self._spr.get(key)
        if spr is None:
            spr = self._spr[key] = sim3d._sphere(STEEL, r)
        img.paste(spr, (int(x) - r - 1, int(y) - r - 1), spr)

    def _heat(self, t: float) -> float:
        k = self.engaged(t)
        if not k:
            return 0.0
        by = self.ball_y(t)
        return float(np.clip((-k * D - (by - RB)) / _depth(k), 0, 1))

    def engaged(self, t: float) -> int:
        pl = self.plan
        by = self.ball_y(t)
        k = int(math.floor(-(by - RB) / D))
        if 1 <= k <= NL and pl["contact"].get(k, 1e9) <= t < pl["tear"].get(k, 1e9):
            return k
        return 0

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.35 if i % ZONE == 0 and i < NL else 0.2)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        t = self.t
        by = self.ball_y(min(t, self.T))
        cam = self._cam(t)
        kc = int(math.floor(-(by - RB) / D))
        side = 1 if self.yaw < 0 else -1
        for k in range(max(1, kc), min(NL, kc + 4) + 1):    # the number of every layer next to its rim
            if self.plan["tear"].get(k, 1e9) <= t:
                continue
            x, y = cam.point((side * (RL + 0.16), -k * D, 0.0))
            if 470 < y < 1450:
                col = (255, 255, 255) if k == self.engaged(t) else (150, 150, 175)
                d.text((x, y), str(k), font=p.f_count, fill=col, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
        if self.end is None or self.t < self.end:
            super().draw_text(p, d)
            return
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["How many layers", "can the ball break?"]

    def counter(self) -> str:
        if self.end is not None:
            return f"{self.broken} of {NL} layers broken"
        k = self.engaged(self.t)
        if k and self.t - self.plan["contact"][k] > 0.5:
            return f"layer {k} is holding… {self.broken} broken"
        return f"{self.broken} of {NL} layers broken"

    def finale(self) -> list[tuple[str, tuple]]:
        st = self.plan["stuck"]
        if st is None:
            return [(f"ALL {NL}!", GOLD[0]), ("NOTHING STOPS IT", (255, 255, 255))]
        return [("STUCK ON", (255, 255, 255)), (f"LAYER {st[0]}!", GOLD[0])]
