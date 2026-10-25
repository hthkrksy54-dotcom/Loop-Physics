"""Bead picture: a colourful heap of a few hundred glossy beads lies in front of an empty pegboard. One by one –
then faster and faster, up to ~150 a second – the beads hop off the heap in arcs and click into the board, row by
row from the top, until a pixel picture appears. What is it building? The name is never shown: the guesses go into
the comments. Then the board lets go, every bead rains back into its own spot in the heap – exactly the first frame
again (a seamless loop, short format).

3D (ytauto/sim3d.py look): glossy spheres on the studio platform, fixed camera. Every hop is planned exactly
(ballistic arcs, launch rate growing exponentially), so length, sound and the loop are always in sync: every bead
that lands plays the next note (up to ~10 a second), the rest click.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import ImageDraw

from .. import sim3d
from ..sims import H, Sim

ARTS = {
"duck": """
................
.....yyyy.......
....yyyyyy......
....yykyyy......
..ooyyyyyy......
.oooyyyyyy......
.....yyyy.......
...yyyyyyyy...y.
..yyyyyyyyyyyyy.
..yyywyyyyyyyyy.
..yyyywwyyyyyyy.
..yyyyyyyyyyyy..
...yyyyyyyyyy...
....yyyyyyyy....
""",
"ice_cream": """
.......rr.......
........r.......
.....pppppp.....
....pppppppp....
...ppwwppppppp..
...pwpppppppppp.
...ppppppppppp..
..oooooooooooo..
...olololololo..
....lololololo..
....olololol....
.....lololo.....
......olol......
.......lo.......
""",
"rocket": """
.......ww.......
......wwww......
.....wwwwww.....
.....wwbbww.....
.....wbccbw.....
.....wbccbw.....
.....wwbbww.....
.....wwwwww.....
....rwwwwwwr....
...rrwwwwwwrr...
...rr.wwww.rr...
......oyyo......
.......oo.......
.......o........
""",
"cat": """
.o............o.
.oo..........oo.
.opo........opo.
.oooooooooooooo.
.oooooooooooooo.
.oogkoooooogkoo.
.oogkoooooogkoo.
.oooooooooooooo.
.oooooooppooooo.
wwooooooooooooww
.ooooookkoooooo.
..oooooooooooo..
...oooooooooo...
....oooooooo....
""",
"diamond": """
................
....cccccccc....
...cwccwwccwc...
..ccwcwccwcwcc..
.cccccccccccccc.
..bccccbbccccb..
...bccbccbccb...
....bccbbccb....
.....bcbbcb.....
......bbbb......
.......bb.......
................
................
................
""",
"heart": """
................
..rrr......rrr..
.rrrrr....rrrrr.
rrwwrrr..rrrrrrr
rrwrrrrrrrrrrrrr
rrrrrrrrrrrrrrrr
rrrrrrrrrrrrrrrr
.rrrrrrrrrrrrrr.
..rrrrrrrrrrrr..
...rrrrrrrrrr...
....rrrrrrrr....
.....rrrrrr.....
......rrrr......
.......rr.......
""",
}


COLS = {"y": (255, 214, 64), "o": (255, 140, 40), "k": (52, 52, 66), "w": (242, 242, 250), "r": (240, 58, 72),
        "p": (255, 130, 190), "l": (245, 196, 128), "b": (70, 110, 255), "c": (90, 220, 255), "g": (110, 230, 90)}
ORDER = ["duck", "rocket", "cat", "ice_cream", "diamond", "heart"]
RB = 0.022           # bead radius
S = 0.046            # board pitch
ZB = -0.45           # the board plane
Y0 = 0.16            # bottom row of the board above the platform
G = 9.81
HOLD = 1.4           # the finished picture is held this long
BACK = 2.55          # the rain back into the heap takes this long (inside the 2.6 s outro)
GOLD = (255, 214, 64)


def _art(name: str):
    rows = ARTS[name].strip("\n").split("\n")
    out = []                                            # (row from top, column, colour) – every pixel is 2×2 beads
    for i, row in enumerate(rows):
        for j, ch in enumerate(row):
            if ch != ".":
                for a in range(2):
                    for b in range(2):
                        out.append((2 * i + a, 2 * j + b, COLS[ch]))
    return out, 2 * len(rows)


def _heap(n: int, rnd: random.Random) -> np.ndarray:
    """Slots of a mound: hex layers that get smaller towards the top, bottom layer first."""
    pts, L = [], 0
    while len(pts) < n:
        R = 0.3 - 0.03 * L
        d = 2 * RB * 1.01
        off = (d / 2, d * 0.289) if L % 2 else (0.0, 0.0)
        layer = []
        for r in range(-30, 31):
            for c in range(-30, 31):
                x = c * d + (d / 2 if r % 2 else 0) + off[0]
                z = r * d * 0.866 + off[1]
                if x * x + z * z < R * R:
                    layer.append((x, RB + L * RB * 1.63, 0.32 + z))
        rnd.shuffle(layer)
        layer.sort(key=lambda p: math.hypot(p[0], p[2] - 0.32))   # the inner part of a layer first (a mound)
        pts += layer
        L += 1
    return np.array(pts[:n])


def _plan(seed: int) -> dict:
    rnd = random.Random(seed)
    name = ORDER[seed % len(ORDER)]
    px, rows = _art(name)
    n = len(px)
    # board slots, launch order: top row first, snaking left/right
    px.sort(key=lambda q: (q[0], q[1] if q[0] % 2 == 0 else -q[1]))
    tgt = np.array([((c - 15.5) * S, Y0 + (rows - 1 - r) * S, ZB) for r, c, _ in px])
    cols = [c for _, _, c in px]
    heap = _heap(n, rnd)[::-1]                          # the top of the heap leaves first
    # launch times: the rate grows exponentially from r0 to ~150/s over T seconds
    T, r0 = rnd.uniform(14.8, 16.2), 2.2
    lo, hi = 1e-3, 2.0
    for _ in range(60):
        k = (lo + hi) / 2
        if r0 / k * (math.exp(k * T) - 1) < n:
            lo = k
        else:
            hi = k
    i = np.arange(n)
    launch = 0.12 + np.log1p(i * k / r0) / k
    dist = np.linalg.norm(tgt - heap, axis=1)
    fly = 0.36 + 0.24 * dist
    land = launch + fly
    done = float(land.max())
    end = done + HOLD
    # the way back: bottom heap slots first, each from its board slot in a short drop
    rank = np.empty(n, int)
    rank[np.argsort(heap[:, 1] + 1e-3 * np.hypot(heap[:, 0], heap[:, 2] - 0.32))] = i
    back_land = end + 0.6 + (BACK - 0.6) * rank / max(1, n - 1)
    back_fly = 0.55
    return {"name": name, "n": n, "tgt": tgt, "cols": cols, "heap": heap, "launch": launch, "fly": fly, "land": land,
            "done": done, "end": end, "back_land": back_land, "back_fly": back_fly}


class BeadPicture(Sim):
    kind = "bead_picture"
    concept = {
        "created": "2026-10-25T02:50:00+00:00",
        "idea": "A colourful heap of a few hundred glossy beads (3D) lies in front of an empty pegboard; one by one, "
                "then faster and faster (up to ~150 a second), the beads hop off the heap and click into the board row "
                "by row until a pixel picture appears – the name is never shown, so the guesses land in the comments. "
                "Then every bead rains back into its own spot in the heap: the first frame again (seamless loop, "
                "~21 s).",
        "inspiration": "the viral 'satisfying pixel art / bead sorting' and 'guess what it builds' clips, rebuilt as a "
                       "3D bead simulation in the style of @particlesflow – second short-format loop after "
                       "chladni_plate, so the 'short'/'loop' experiment gets more than one data point",
        "finale": "the last rows fly in at ~150 beads a second, the finished picture flashes, 'DID YOU GUESS IT?' – "
                  "then the board lets go and all beads rain back into the heap, exactly where the video began",
    }
    titles = ["{onscreen}", "{k} beads, one picture – what is it?", "Guess the picture before the last bead lands"]
    questions = ["What did you see first?", "At which row did you know what it was?",
                 "What should the beads build next?"]
    body = ("{k} glossy beads hop off a heap onto a pegboard – faster and faster, row by row – until a picture "
            "appears. Every bead that lands plays the next note of {song}. What is it? Then they all rain back into "
            "the heap and it starts over. Everything is simulated in 3D, nothing is animated.")
    playlist = ("3D simulations", "Everything simulated, not animated.")
    cover_at = 0.55
    trend_words = ("guess", "pixel", "beads", "3d", "simulation", "satisfying", "loop", "picture")
    slowmo = False
    note_gap = 0.06
    finale_punch = 0.5
    full_frame = True
    experiment = "loop"
    min_video = 20
    run_ranges = [(16.5, 19.5), (17, 20)]
    cta_y = 1640

    @staticmethod
    def planned_end(seed: int) -> float:
        return _plan(seed)["end"]

    def __init__(self, seed: int):
        super().__init__(seed)
        pl = self.pl = _plan(seed)
        self.K = self.n = pl["n"]
        self.order = np.argsort(pl["land"])
        self.li = 0
        self.placed = 0
        self.last_note = -9.0
        self.done = False

    def step(self, dt: float) -> None:
        self.t += dt
        if self.end is not None:
            return
        pl = self.pl
        while self.li < self.n and pl["land"][self.order[self.li]] <= self.t:
            j = int(self.order[self.li])
            self.li += 1
            self.placed += 1
            if self.t - self.last_note >= 0.1:
                self.last_note = self.t
                self.events.append((self.t, "land", j))
            else:
                self.events.append((self.t, "clack", j))
        if not self.done and self.placed == self.n:
            self.done = True
            self.events.append((self.t, "break", 0))
        if self.t >= pl["end"]:
            self.events.append((self.t, "break", 1))
            self.finish()

    # ---------------------------------------------------------------- picture

    def positions(self, t: float) -> np.ndarray:
        pl = self.pl
        heap, tgt = pl["heap"], pl["tgt"]
        P = heap.copy()
        a = (t - pl["launch"]) / pl["fly"]
        fly = (a > 0) & (a < 1)
        on = a >= 1
        b = (t - (pl["back_land"] - pl["back_fly"])) / pl["back_fly"]
        back = (b > 0) & (b < 1)
        home = b >= 1
        P[on] = tgt[on]
        if fly.any():
            T = pl["fly"][fly]
            s = (t - pl["launch"][fly])[:, None]
            v = (tgt[fly] - heap[fly]) / T[:, None]
            v[:, 1] += G * T / 2
            P[fly] = heap[fly] + v * s
            P[fly, 1] -= G * s[:, 0] ** 2 / 2
        if back.any():
            T = pl["back_fly"]
            s = (t - (pl["back_land"][back] - T))[:, None]
            v = (heap[back] - tgt[back]) / T
            v[:, 1] += G * T / 2
            P[back] = tgt[back] + v * s
            P[back, 1] -= G * s[:, 0] ** 2 / 2
        P[home] = heap[home]
        return P

    def prepare(self, p) -> None:
        look = self.look.rnd
        self.tint = look.choice([(14, 15, 24), (10, 14, 22), (18, 14, 24), (12, 16, 18)])
        self.cam = sim3d.Camera(target=(0, 0.62, 0.0), dist=5.4, yaw=0.16, pitch=0.2, fov=32, cy=H * 0.5)
        self.studio = sim3d.Studio(self.cam, 0.0, slab=1.0, thick=0.16, tint=self.tint)
        back = self.studio.back.copy()
        d = ImageDraw.Draw(back)
        rows = int(round((self.pl["tgt"][:, 1].max() - Y0) / S)) + 1
        x0, x1 = -16 * S - 0.02, 16 * S + 0.02
        y0, y1 = Y0 - S / 2 - 0.02, Y0 + (rows - 0.5) * S + 0.02
        q = [self.cam.point(pp) for pp in [(x0, y0, ZB - RB), (x1, y0, ZB - RB), (x1, y1, ZB - RB), (x0, y1, ZB - RB)]]
        d.polygon(q, fill=(24, 26, 36))
        for (a, b) in zip(q, q[1:] + q[:1]):
            d.line([a, b], fill=(82, 86, 104), width=5)
        for (a, b) in ((x0 + 0.03, x0 + 0.03), (x1 - 0.03, x1 - 0.03)):   # two legs down to the platform
            d.line([self.cam.point((a, 0.0, ZB - RB)), self.cam.point((b, y0, ZB - RB))], fill=(70, 74, 90), width=8)
        for r in range(rows):                                                 # the empty holes
            for c in range(32):
                hx, hy = self.cam.point(((c - 15.5) * S, Y0 + r * S, ZB - RB * 0.5))
                d.ellipse((hx - 3, hy - 3, hx + 3, hy + 3), fill=(10, 10, 16))
        self.back = back

    def render(self, p):
        t = self.t
        pl = self.pl
        P = self.positions(t)
        cols = list(pl["cols"])
        lit = (t - pl["land"] >= 0) & (t - pl["land"] < 0.09)
        for j in np.flatnonzero(lit):
            cols[j] = (255, 255, 255)
        if self.done and pl["done"] <= t < pl["done"] + 0.5:      # the finished picture flashes
            u = 1 - (t - pl["done"]) / 0.5
            cols = [tuple(int(c + (255 - c) * 0.6 * u) for c in col) for col in cols]
            cols = [(c[0] // 8 * 8, c[1] // 8 * 8, c[2] // 8 * 8) for c in cols]
        img = self.back.copy()
        low = P[:, 2] > ZB + 0.05                                  # board beads cast no floor shadow
        img = self.studio.shadows(img, P[low], np.full(int(low.sum()), RB), 0.5)
        self.studio.spheres(img, P, np.full(len(P), RB), cols)
        return img

    def on_event(self, p, kind: str, i: int) -> None:
        if kind == "break":
            p.punch(0.45 if i == 0 else 0.25)

    def draw(self, p) -> None:  # the picture comes from render()
        pass

    def draw_text(self, p, d) -> None:
        if self.end is None or self.t < self.end:
            return super().draw_text(p, d)
        p.big_text(d, self.finale(), self.t - self.end, cy=330)

    def title(self) -> list[str]:
        return ["What are the beads", "building?"]

    def counter(self) -> str:
        if self.done:
            return "COMPLETE – what is it?"
        return f"{self.placed} of {self.n} beads"

    def finale(self) -> list[tuple[str, tuple]]:
        return [("DID YOU", (255, 255, 255)), ("GUESS IT?", GOLD)]
