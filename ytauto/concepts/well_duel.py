"""Well duel: two heavy balls – red and blue – sink into a stretchy membrane of 2,000 glossy beads, each making its
own gravity well. Marbles roll in from the rim, orbit, and spiral into one of the two wells: every marble a well
swallows makes its ball heavier and its well deeper and wider, so it catches more (rich get richer). Meanwhile the
two wells circle each other closer and faster – an inspiral like two black holes – until they merge: the heavier
ball swallows the other and the membrane tears under the giant.

Experiment "versus": viewers pick a side (red or blue) – the question that is meant to pull comments.

3D (ytauto/sim3d.py look): the membrane is a pinned grid of touching spheres whose height is the sum of the two
wells, coloured by depth in the colour of the well it belongs to. The marbles roll on that exact surface (slope
force + rolling drag), so the orbits, the captures and the sound all come from the same physics.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import sim3d
from ..sims import H, W, Sim

N = 46                       # beads per side of the membrane
A = 1.3                      # half size of the membrane (m)
RS = A / (N - 1)             # bead radius (touching beads)
RM = 0.042                   # marble radius
FLOOR = -1.05
SPAWN_R = 1.12               # marbles roll in from this circle
PHYS = 3                     # physics every 3rd step (240 Hz)
CAP = 520
TEAMS = [("RED", (255, 66, 72)), ("BLUE", (60, 140, 255))]
TOP = (168, 170, 196)
SHADES = 12
MARBLES = [(255, 255, 255), (255, 214, 90), (140, 255, 170), (255, 150, 220), (170, 230, 255), (255, 180, 120)]


def _depth(m):
    return 0.1 + 0.03 * np.sqrt(m)


def _sigma(m):
    return 0.15 + 0.011 * np.sqrt(m)


def _radius(m):
    return 0.075 + 0.0105 * np.sqrt(m)


class WellDuel(Sim):
    kind = "well_duel"
    concept = {
        "created": "2026-10-27T04:40:00+00:00",
        "idea": "Two heavy balls, red and blue, sink into a stretchy membrane of ~2,000 glossy beads (3D), each a "
                "gravity well. Hundreds of marbles roll in from the rim, orbit and spiral into one of the wells – "
                "every catch makes that ball heavier and its well deeper, so it catches more. The two wells circle "
                "each other closer and faster until they merge: the heavier one swallows the other.",
        "inspiration": "the viral 'spacetime fabric' gravity-well demos (a heavy ball on stretched lycra with marbles "
                       "orbiting into it) and black-hole merger animations, rebuilt as a 3D bead membrane in the style "
                       "of @particlesflow, with a red-vs-blue duel so viewers pick a side",
        "finale": "the wells spiral together faster and faster (catches race up to ~10/s), the heavier ball "
                  "swallows the lighter one, the merged well gets so deep that the membrane tears – beads burst "
                  "outwards and the giant ball drops through onto the platform (slow motion)",
    }
    titles = ["{onscreen}", "Red or blue – which gravity well swallows the other?",
              "Two gravity wells, hundreds of marbles – which one wins?"]
    questions = ["Red or blue – which one did you pick?", "When did you know who would win?",
                 "Should the next duel have three wells?"]
    body = ("Two heavy balls sink into a stretchy membrane of glossy beads – two gravity wells. Marbles roll in, "
            "orbit and fall into one of them; every catch makes that well heavier and deeper and plays the next note "
            "of {song}. The two wells circle each other closer and faster until they merge – the heavier one "
            "swallows the other and the membrane tears. Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.9
    trend_words = ("gravity", "black hole", "red vs blue", "3d", "simulation", "satisfying", "marbles", "which wins")
    slowmo = True
    note_gap = 0.06
    finale_punch = 1.3
    full_frame = True
    tempo = "fast"
    experiment = "versus"
    cta_y = 1600

    def __init__(self, seed: int):
        super().__init__(seed)
        rnd = self.rnd
        self.target = rnd.uniform(60.0, 80.0)        # the wells would touch at this time
        self.s0 = rnd.uniform(0.95, 1.05)            # separation of the wells at the start
        self.phase = rnd.uniform(0, 2 * math.pi)
        self.spin = rnd.choice([-1, 1])              # the marbles orbit with the wells
        self.m = np.array([12.0, 12.0])
        self.ang = self.phase
        self.sep = self.s0
        self.wp = self._wells()
        # marbles: position, velocity, state (0 waiting, 1 rolling, 2 swallowed, 3 falling after the tear)
        self.p = np.zeros((CAP, 2))
        self.v = np.zeros((CAP, 2))
        self.state = np.zeros(CAP, np.int8)
        self.prev = np.zeros((CAP, 2))
        self.n = 0
        self.next_spawn = 0.0
        self.steps = 0
        self.flash = np.array([-9.0, -9.0])
        self.merge_t = None           # the smaller ball slides into the bigger one
        self.tear_t = None
        self.winner = 0
        self.mf = None                # merged ball: (x, z, mass)
        self.last_note = -9.0
        for k in range(34):           # marbles already rolling at the start, the first ones about to fall in
            self._spawn(rnd.uniform(0.62, 1.05) if k >= 14 else None, near=k if k < 14 else None)

    # ---------------------------------------------------------------- physics

    def _wells(self) -> np.ndarray:
        c, s = math.cos(self.ang), math.sin(self.ang)
        h = self.sep / 2
        return np.array([[c * h, s * h], [-c * h, -s * h]])

    def height(self, x: np.ndarray, z: np.ndarray, t: float | None = None) -> np.ndarray:
        """Membrane height at (x, z): the sum of the wells, held flat by the frame at the border."""
        t = self.t if t is None else t
        hgt = np.zeros(np.broadcast(x, z).shape)
        if self.mf is not None and t >= self.merge_t:
            wells = [(self.mf[0], self.mf[1], self.mf[2])]
        else:
            wells = [(self.wp[i, 0], self.wp[i, 1], self.m[i]) for i in range(2)]
        for wx, wz, m in wells:
            D, s = _depth(m), _sigma(m)
            if self.tear_t is not None and t >= self.tear_t:   # torn: the membrane springs back and rings
                tau = t - self.tear_t
                D = D * math.exp(-4.5 * tau)
            hgt = hgt - D * s * s / ((x - wx) ** 2 + (z - wz) ** 2 + s * s)
        if self.tear_t is not None and t >= self.tear_t:
            tau = t - self.tear_t
            r = np.hypot(x - self.mf[0], z - self.mf[1])
            hgt = hgt + 0.06 * np.sin(9 * r - 14 * tau) * math.exp(-1.6 * tau) * np.exp(-r)
        taper = (1 - (np.clip(np.abs(x) / A, 0, 1)) ** 6) * (1 - (np.clip(np.abs(z) / A, 0, 1)) ** 6)
        return hgt * taper

    def _spawn(self, r: float | None = None, near: int | None = None) -> None:
        if self.n >= CAP:
            return
        rnd = self.rnd
        i = self.n
        self.n += 1
        if near is not None:          # spiralling into well (near % 2), one after the other
            w = self.wp[near % 2]
            a = rnd.uniform(0, 2 * math.pi)
            d = 0.16 + 0.05 * near
            self.p[i] = (w[0] + d * math.cos(a), w[1] + d * math.sin(a))
            tv = 0.11 * near * self.spin      # the farther ones still orbit a little before they drop in
            self.v[i] = (-math.cos(a) * 0.3 - math.sin(a) * tv, -math.sin(a) * 0.3 + math.cos(a) * tv)
            self.prev[i] = self.p[i]
            self.state[i] = 1
            return
        a = rnd.uniform(0, 2 * math.pi)
        r = SPAWN_R if r is None else r
        self.p[i] = (r * math.cos(a), r * math.sin(a))
        sp = rnd.uniform(0.95, 1.35) * (1.0 if r > 1 else 1.15)
        tx, tz = -math.sin(a) * self.spin, math.cos(a) * self.spin
        self.v[i] = (tx * sp - math.cos(a) * 0.15, tz * sp - math.sin(a) * 0.15)
        self.prev[i] = self.p[i]
        self.state[i] = 1

    def step(self, dt: float) -> None:
        self.t += dt
        self.steps += 1
        if self.steps % PHYS:
            return
        h = dt * PHYS
        t = self.t
        if self.merge_t is None:
            u = min(1.0, t / self.target)
            self.sep = self.s0 - (self.s0 - 0.28) * u ** 3
            self.ang += self.spin * 0.42 * (self.s0 / self.sep) ** 1.5 * h
            self.wp = self._wells()
            rate = 3.4 + 8.5 * u ** 2                 # marbles per second
            while self.next_spawn <= t and self.end is None:
                self._spawn()
                self.next_spawn += 1.0 / rate
            if self.sep < 0.85 * (_radius(self.m[0]) + _radius(self.m[1])):
                self._merge()
        elif self.tear_t is None and t >= self.merge_t + 0.55:
            self.tear_t = t
            self.events.append((t, "break", 1))
            self.finish()
        live = np.nonzero(self.state == 1)[0]
        self.prev[live] = self.p[live]
        if len(live):
            P = self.p[live]
            e = 1e-3
            gx = (self.height(P[:, 0] + e, P[:, 1]) - self.height(P[:, 0] - e, P[:, 1])) / (2 * e)
            gz = (self.height(P[:, 0], P[:, 1] + e) - self.height(P[:, 0], P[:, 1] - e)) / (2 * e)
            k = 9.81 / (1 + gx * gx + gz * gz)
            drag = 0.22 + 0.25 * min(1.0, t / self.target)
            self.v[live, 0] += (-gx * k) * h
            self.v[live, 1] += (-gz * k) * h
            self.v[live] *= math.exp(-drag * h)
            self.p[live] += self.v[live] * h
            r = np.hypot(self.p[live, 0], self.p[live, 1])
            out = r > SPAWN_R + 0.04                  # the frame keeps them on the membrane
            if out.any():
                j = live[out]
                nrm = self.p[j] / r[out, None]
                self.p[j] = nrm * (SPAWN_R + 0.04)
                vn = np.sum(self.v[j] * nrm, 1)
                self.v[j] -= (1.6 * np.maximum(vn, 0))[:, None] * nrm
            self._capture(live)

    def _capture(self, live: np.ndarray) -> None:
        if self.mf is not None and self.t >= self.merge_t:
            wells = [(self.mf[0], self.mf[1], self.mf[2], self.winner)]
        else:
            wells = [(self.wp[i, 0], self.wp[i, 1], self.m[i], i) for i in range(2)]
        for wx, wz, m, w in wells:
            d = np.hypot(self.p[live, 0] - wx, self.p[live, 1] - wz)
            got = live[(d < _radius(m) + RM * 0.6) & (self.state[live] == 1)]
            for j in got:
                if self.tear_t is not None:
                    self.state[j] = 3                 # falls through the hole
                    continue
                self.state[j] = 2
                if self.mf is not None:
                    self.mf = (self.mf[0], self.mf[1], self.mf[2] + 1)
                else:
                    self.m[w] += 1
                self.flash[w] = self.t
                melody = self.t - self.last_note >= self.note_gap  # a catch right after the last note clacks
                self.events.append((self.t, "bounce" if melody else "clack", w))
                if melody:
                    self.last_note = self.t

    def _merge(self) -> None:
        m = self.m
        self.winner = 0 if m[0] > m[1] or (m[0] == m[1] and self.rnd.random() < 0.5) else 1
        w = self.winner
        self.merge_t = self.t
        self.mf = (float(self.wp[w, 0]), float(self.wp[w, 1]), float(m[0] + m[1]))
        self.events.append((self.t, "break", 0))

    # ---------------------------------------------------------------- picture

    def prepare(self, p) -> None:
        self.cam = sim3d.Camera(target=(0, -0.3, 0.05), dist=9.4, yaw=0.5, pitch=0.82, fov=30, cy=H * 0.585)
        look = self.look.rnd
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24)])
        self.studio = sim3d.Studio(self.cam, FLOOR, slab=1.45, thick=0.16, tint=self.tint,
                                   posts=[(-A, -A), (A, -A), (A, A), (-A, A)], post_top=0.0, frame_y=0.0,
                                   frame_half=A + RS)
        self.mcol = [MARBLES[look.randrange(len(MARBLES))] for _ in range(CAP)]
        self.shades = [[sim3d.lerp_col(TOP, col, (u / (SHADES - 1)) ** 0.8) for u in range(SHADES)]
                       for _, col in TEAMS]
        g = np.linspace(-A, A, N)
        self.gx, self.gz = np.meshgrid(g, g)
        rr = np.random.default_rng(7)
        self.tear_v = np.stack([rr.uniform(0.6, 1.9, N * N), rr.uniform(-0.6, 0.9, N * N)], 1)

    def _ball_pos(self, i: int):
        """World centre and radius of heavy ball i (the loser slides into the winner during the merge)."""
        t = self.t
        if self.merge_t is not None and t >= self.merge_t:
            mx, mz, mm = self.mf
            R = _radius(mm)
            if i != self.winner:
                u = min(1.0, (t - self.merge_t) / 0.5)
                x0, z0 = self.wp[i]
                x, z = x0 + (mx - x0) * u, z0 + (mz - z0) * u
                r = _radius(self.m[i]) * (1 - u)
                return x, float(self.height(np.array(x), np.array(z))) + r * 0.7, z, r
            R = _radius(self.m[self.winner] + (mm - self.m[self.winner]) * min(1.0, (t - self.merge_t) / 0.5))
            y = float(self.height(np.array(mx), np.array(mz), min(t, self.tear_t or t))) + R * 0.7
            if self.tear_t is not None and t > self.tear_t:  # drops through onto the platform
                tau = t - self.tear_t
                y0 = y
                y = max(FLOOR + R, y0 - 4.9 * tau * tau)
            return mx, y, mz, R
        x, z = self.wp[i]
        R = _radius(self.m[i])
        return x, float(self.height(np.array(x), np.array(z))) + R * 0.7, z, R

    def render(self, p):
        t = self.t
        X, Z = self.gx.ravel(), self.gz.ravel()
        Y = self.height(X, Z)
        pts = np.stack([X, Y, Z], 1)
        keep = np.ones(len(X), bool)
        if self.tear_t is not None and t >= self.tear_t:      # beads around the hole burst outwards
            tau = t - self.tear_t
            mx, mz, mm = self.mf
            dx, dz = X - mx, Z - mz
            r = np.hypot(dx, dz)
            hole = r < 0.2 + 1.4 * _radius(mm)
            rr = np.maximum(r, 1e-6)
            sp = self.tear_v[:, 0]
            pts[hole, 0] = X[hole] + dx[hole] / rr[hole] * sp[hole] * tau
            pts[hole, 2] = Z[hole] + dz[hole] / rr[hole] * sp[hole] * tau
            y0 = -_depth(mm) * 0.8
            fly = y0 + self.tear_v[hole, 1] * tau - 4.9 * tau * tau
            on_slab = (np.abs(pts[hole, 0]) < 1.45) & (np.abs(pts[hole, 2]) < 1.45)
            pts[hole, 1] = np.where(on_slab, np.maximum(FLOOR + RS, fly), fly)   # off the platform they keep falling
        # colour by depth, in the colour of the nearer well
        if self.mf is not None and t >= self.merge_t:
            team = np.full(len(X), self.winner)
        else:
            d0 = np.hypot(X - self.wp[0, 0], Z - self.wp[0, 1])
            d1 = np.hypot(X - self.wp[1, 0], Z - self.wp[1, 1])
            team = (d1 < d0).astype(int)
        u = np.clip(-Y / 0.55, 0, 1)
        q = (u * (SHADES - 1) + 0.5).astype(int)
        cols = [self.shades[a][b] for a, b in zip(team, q)]
        rad = [np.full(len(X), RS)]
        allp = [pts[keep]]
        # marbles
        a = (self.steps % PHYS) / PHYS
        idx = np.nonzero(self.state == 1)[0]   # marbles that drop through the torn hole vanish into it
        if len(idx):
            M = self.prev[idx] + (self.p[idx] - self.prev[idx]) * a
            my = self.height(M[:, 0], M[:, 1]) + RM + RS * 0.5
            allp.append(np.stack([M[:, 0], my, M[:, 1]], 1))
            rad.append(np.full(len(idx), RM))
            cols += [self.mcol[i] for i in idx]
        heavy = []
        for i in range(2):
            x, y, z, R = self._ball_pos(i)
            if R < 0.01:
                continue
            col = TEAMS[i][1]
            if t - self.flash[i] < 0.08 and self.end is None:
                col = sim3d.lerp_col(col, (255, 255, 255), 0.55)
            allp.append(np.array([[x, y, z]]))
            rad.append(np.array([R]))
            cols.append(col)
            heavy.append((x, y, z, R, i))
        P = np.vstack(allp)
        Rr = np.concatenate(rad)
        img = self.studio.back.copy()
        if self.tear_t is not None:
            img = self.studio.shadows(img, P[-len(heavy):], Rr[-len(heavy):])
        self.studio.spheres(img, P, Rr, cols)
        img.paste(self.studio.front, (0, 0), self.studio.front)
        # a soft glow around the heavy balls, brighter on every catch
        glow = Image.new("RGB", (W // 4, H // 4))
        gd = ImageDraw.Draw(glow)
        for x, y, z, R, i in heavy:
            sx, sy = self.cam.point((x, y, z))
            _, _, _, s = self.cam.project(np.array([[x, y, z]]))
            f = max(0.0, 1 - (t - self.flash[i]) / 0.25)
            rr = R * float(s[0]) / 4 * (1.8 + 0.6 * f)
            c = TEAMS[i][1]
            k = 0.22 + 0.35 * f
            gd.ellipse((sx / 4 - rr, sy / 4 - rr, sx / 4 + rr, sy / 4 + rr), fill=tuple(int(v * k) for v in c))
        glow = glow.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(img, glow)

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.5 if i == 0 else 1.0)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["Which gravity well", "swallows the other?"]

    def counter(self) -> str:
        a, b = int(self.m[0]), int(self.m[1])
        if self.merge_t is not None:
            w = self.winner
            return f"{TEAMS[w][0]} SWALLOWS {TEAMS[1 - w][0]} · {a} : {b}"
        lead = "" if self.sep > 0.6 else "FINAL SPIRAL · "
        return f"{lead}RED {a} : {b} BLUE"

    @property
    def counter_color(self):
        if self.merge_t is not None:
            return TEAMS[self.winner][1]
        if self.m[0] == self.m[1]:
            return (255, 214, 120)
        return sim3d.lerp_col(TEAMS[0 if self.m[0] > self.m[1] else 1][1], (255, 255, 255), 0.25)

    def finale(self) -> list[tuple[str, tuple]]:
        w = self.winner
        return [(f"{TEAMS[w][0]} WINS!", TEAMS[w][1]), (f"{int(self.m[w])} : {int(self.m[1 - w])}", (255, 255, 255))]
