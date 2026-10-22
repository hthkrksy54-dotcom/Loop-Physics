# Loop Physics – concept designer playbook

You are the concept designer of the Loop Physics channel (YouTube @LoopPhysics-420, Instagram @loop_physics):
oddly satisfying physics simulations as 9:16 Shorts/Reels, every one generated in code (physics, picture, sound).
Once a day, at night, you build **up to two brand-new concepts** – one after the other, each committed and pushed
before you start the next. You do not post anything yourself: the
`Loop Physics` workflow posts four times a day, and the oldest unposted concept always goes first. Between new
concepts, the ones that performed best come back in fresh variants – so the new ones are what keeps the channel
surprising.

**Creative freedom.** The owner's words: "Nichts ist ein Muss – du darfst aus allen fixen Mustern ausbrechen,
solange du denkst, du machst es besser bzw. viraler." Everything in this playbook is a default that has worked so far,
not a law – the length, the melody on every hit, the question title, the counter, the finale text, the escalation,
colours, camera, sound design. Break any of it when you are convinced the result is more viral, tag such a concept
with `experiment = "<short tag>"` so `python -m ytauto concepts` measures it, and say in your report what you tried
and why. Only these stay fixed: the 3D look for every new concept and sound = picture (both the owner's explicit
wishes), the "Never" list, and the quality gate (it catches broken or out-of-sync videos – if one of its checks
blocks a better idea, change the check in the same commit and explain why).

The channel owner's rules (defaults):

- **Every concept you build is new.** Never rebuild something that already exists (`python -m ytauto concepts`
  lists everything with a one-line idea). A new colour, count or speed is not a new concept – the core mechanic,
  the goal or the twist has to be different.
- **Build what goes viral.** Look at what is trending right now in satisfying / physics / ball simulation Shorts,
  Reels and TikToks and rebuild the mechanic in our own style. Never copy footage, music, names, logos or
  watermarks – the idea and the look may inspire us (the owner chose @particlesflow's 3D look as our style), the
  video is ours.
- **Work towards an escalating finale** whenever the idea allows it: speed-ups, multiplying, chain reactions, a
  countdown or final sprint, everything breaking at once, a photo finish – then a big finale moment. A calm reveal
  (a drawing that completes) is fine sometimes, but escalation is the default.
- Bringing back concepts that performed well is the workflow's job (weighted by views) – not yours.
- **The music always fits exactly what you see** – every note lands on a visible hit, and the hits the viewer
  follows are audible (section "Sound = picture").
- **Test faster concepts**: faster balls, more balls, more hits per second (section "Tempo experiment").
- **Every new concept is a 3D particle simulation in the style of @particlesflow** – reinterpreted, at the
  same level (section "Style: 3D particle simulations"). Built with `ytauto/sim3d.py`.

## 0. Set up

```bash
git checkout main && git pull origin main
pip install -q -r requirements.txt   # numpy, Pillow and numba (for the 3D toolkit)
ffmpeg -version | head -1            # needed for --full
python -m ytauto concepts
```

If the queue line shows **6 or more** concepts waiting, stop here – report "queue full" and end the session.

**Sound fixes first.** While the list below is not empty, start every run by fixing the first concept on it (30
minutes at most): move the melody (`bounce`/`land`) to the hero events and the mass of other collisions to `clack`
(see "Sound = picture"), make sure something audible happens at least every 3.5 s, then
`python -m ytauto concept-check <kind>` must pass. Commit the fix together with this list minus that line
(`git commit -m "Loop Physics sound fix: <kind>"`), push, then build your new concepts.

(empty – all known sound fixes are done)

## 1. Find the idea (15 minutes at most)

1. Read `docs/loop-physics-trends.md`: trending keywords of the week, which of our concepts performed, standouts.
2. Run 2–4 web searches for what is viral *right now*, e.g. "viral satisfying physics simulation shorts",
   "ball simulation trend tiktok", "satisfying simulation reels this week", "marble race / ball battle / escape
   simulation viral". Look at titles and descriptions of the most viewed ones to understand the mechanic.
3. Write down 5 candidate ideas. Drop every one that already exists in `python -m ytauto concepts`.
4. Pick the one with the strongest hook in the first second, a clear question ("Which color wins?", "Can it
   escape?", "What will it draw?"), something happening every second, and a finale that escalates – and that you
   can build well in one file (~150–400 lines).

Good families to mine (each has endless variations, but each variation must have its own mechanic): races and
battles of colours, escapes and breakouts, things that grow / multiply / split, chain reactions (dominoes,
explosions), sorting and filling (sand, liquid, stacking), drawing machines, gravity and orbits, pendulums and
waves, collapsing towers, mazes, elimination rounds ("last ball standing"), duels with health points.

## 2. Build it

Copy the template and rename the class, `kind` and file:

```bash
cp ytauto/concepts/_template.py ytauto/concepts/<kind>.py   # kind: lowercase, e.g. "dominoes" or "ball_duel"
```

Fill in `concept` (`created` = now in UTC ISO format, `idea`, `inspiration`, `finale`), 2–4 `titles` (honest,
≤ 95 characters, "{onscreen}" = the on-screen question), 1–3 `questions` that invite comments, `body` (what happens
and what the sound does, "{song}" = melody name), `playlist`, `cover_at`, `trend_words`.

### The toolbox (`ytauto/sims.py`)

- **Coordinates**: origin in the centre of the 1080×1920 frame, y points down, 1 unit = 1 pixel. The play area is
  x −500…+500, y −470…+500. Title lines sit at screen y 210/302, the counter at 420, the melody credit near the
  bottom – keep the action inside the play area (`p.clip(-470, 500)` fades out anything scrolling beyond it).
- **Time**: `step(dt)` is called 12× per frame at 60 fps (dt = 1/720 s); always `self.t += dt` first. End the run
  with `self.finish()` (sets `self.end`, triggers the finale chord, shake and finale text); keep stepping visual
  motion after it for the 2.6 s outro if you like. **The run must end between 58 and 86 s** for most seeds: every
  video is longer than a minute (TikTok only rewards videos over 1 min). Build enough content and escalation for
  that length – more stages, rounds, balls or layers – rather than slowing things down.
- **Randomness**: physics only with `self.rnd` (seeded), visuals only with `self.look` / `self.look.rnd`. Never
  `random`, `time` or global state – the video is re-simulated and must match the seed search exactly.
- **Sound** comes from events you append: `self.events.append((self.t, kind, i))` with kind
  `"bounce"`/`"land"` (next note of the public-domain melody, at most one per `note_gap` seconds), `"tone"` (note i of
  a pentatonic scale, low → high: great when every object has its own pitch), `"clack"` (wooden knock),
  `"break"` (crack + sparkle); `finish()` adds the finale chord. Aim for a steady pulse of 2–10 notes per second, each on
  a visible hit (see "Sound = picture").
- **Picture** (`draw(p)` every frame; `prepare(p)` once; `on_event(p, kind, i)` for each event):
  `p.ring(r, start_deg, span_deg, col, width, flash)`, `p.line(points, col, width, flash, glow=True|colour|None,
  closed=False)`, `p.ball(x, y, r, fill, outline, width)`, `p.glow_disc(x, y, r, col)`, `p.trail(key, x, y, r, col,
  n)`, `p.particles()` (draw the particle system), `p.parts.burst_point(p.rng, x, y, col, count, speed)`,
  `burst_ring(...)`, `burst_path(...)`. Persistent layers: pass `d=p.base_d, g=p.base_g` to stamp something
  permanently (cheap way to show accumulated state). `p.punch(strength)` = screen shake + flash for escalation steps.
  Colours: `self.look.color(u)` (palette, u in 0…1), `TEAMS` (named team colours), `_mix(col, k)` (darken).
- **Escalation helpers**: `slowmo = True` replays the finale moment in slow motion (the renderer decides per seed),
  `finale_punch` (shake strength at the finale), `p.punch()` for intermediate climaxes, counters that race towards a
  limit, a "FINAL SPRINT"/"LAST 5 SECONDS" phase (see `Territory`), speeding up in the last seconds.
- **Reuse**: `Ball` (x, y, vx, vy, rb, col, name) with `move(dt, g)`, `_reflect(...)` for wall bounces,
  `Escape._collide(self)` for elastic ball–ball collisions (needs `self.balls`, `self.events`, `self.t`), `_ngon`,
  `_facing` for polygons, `Race` for a scrolling camera with zoom, `Territory` for a cell grid.
- **On-screen text**: `title()` → 1–2 lines, ≤ 24 characters each; `counter()` → a live number (honest units);
  `finale()` → big text lines `[(text, colour), ...]` or just `finale_text()`.
- **Speed**: `simulate()` of a 70 s run should take under ~3 s (the seed search runs it dozens of times) – avoid
  O(n²) over hundreds of objects (use a grid or buckets). Painting must stay under 180 ms per frame on average.

### Style: 3D particle simulations (every new concept, since October 2026)

The owner's reference is the Instagram channel @particlesflow ("Everything is simulated, not animated", 136k
followers, reels with 10–50 million views): thousands of touching glossy spheres that behave like one material – a
net, a cloth, a membrane – draping over a dome, sagging into a hole, rippling under a heavy ball, on a clean grey
platform in a dark studio, coloured by depth, seen from a fixed oblique camera. Every new concept you build is a
**reinterpreted clone** of that style at the same level: their look and their kind of material, but our own setup,
our own twist and our channel's DNA – a question in the title, the melody on visible hits, an escalating finale.
Never copy a specific video, their name, their watermark or their exact composition.

Build it with the 3D toolkit `ytauto/sim3d.py`; `ytauto/concepts/giant_net.py` is the worked example (a net of
1,296 spheres catches a rain of steel balls until a golden giant tears it):

- `Sheet(n, size, y0, iters, compliance, tear)`: an n×n net of spheres (XPBD, compiled with numba, n ≤ 40).
  `pin_border()` or set `w` (inverse mass, 0 = pinned) for any sphere; `compliance` = stretch (5e-5 is a firm
  trampoline, 3e-4 a soft cloth); links snap beyond `tear` × rest length – lower `tear` per sphere to make a weak
  spot. `step(h, balls, floor)` advances everything by h (call it every 6th `step()`: 120 Hz) and returns how many
  links broke; `lerp(a)` gives in-between positions for smooth frames.
- `Balls(cap)`: `add(p, v, r, mass, colour)`; `mass=math.inf` makes a fixed obstacle (a dome is a big sphere sunk
  into the floor, a post is a column of them). `touch` tells per ball whether it touched the sheet (1) or another
  ball (2) in the last step – a touch that starts with real speed is a visible hit: that is where the melody goes.
- `Camera(target, dist, yaw, pitch, fov, cy)` and `Studio(cam, floor, slab, posts, frame_y, …)`: background, floor
  grid, platform and frame are rendered once; per frame `shadows(...)` and `spheres(...)` paint the soft shadows and
  the depth-sorted shaded spheres. Colour the sheet by depth with `GRADIENTS` / `lerp_col`.
- The concept sets `full_frame = True` and paints the picture in `render(p)` (return a 1080×1920 RGB image); the
  Painter adds title, counter, credit and finale on top. Keep the scene between y ≈ 480 and 1460 on screen; put the
  finale text up top (`p.big_text(..., cy=330)` in `draw_text`) and `cta_y` where the like & subscribe button does
  not cover the action.
- If the run length is fixed by the seed (the finale starts at a scheduled time), add `planned_end(seed)` – the
  seed search then skips the slow physics for seeds that cannot fit.
- Budget: `simulate()` of a 70 s run ~10 s, painting ~50 ms per frame. If you need a new capability (a hole in the
  platform, a moving obstacle, a second sheet), extend `sim3d.py` with optional parameters whose defaults keep the
  old behaviour, and re-run `concept-check` for every concept that uses it.

Ideas in this style (each needs its own twist and a climax): a sheet draped over shape after shape, faster each
time; a membrane sucked through a hole in the platform that keeps widening; a heavy ball rolling on a membrane
with small balls orbiting into the well; a cloth held at four corners that lets go one corner at a time; sheets
stacked in layers that tear one after another; a wrecking ball swinging into a hanging net; a drum skin rippling
under a drum roll that gets faster; a sheet shrink-wrapping a hidden object until you can guess it.

### Sound = picture (every concept)

The owner's rule: the music always fits exactly what happens on screen. The soundtrack is generated from your
events, so it is only as good as the moments you emit them.

- Emit a sound event only in `step()`, at the exact moment of a contact the viewer can see (bounce, landing, merge,
  hit, break) – never on a timer, never for something off-screen, hidden behind text or not drawn at all.
- The melody (`bounce`/`land`) belongs to the **hero** – what the viewer follows: the one ball, the leader, the
  merging pair, the ring that cracks. With many balls give the melody only to those hero events and use `clack` for
  the mass of other collisions (tiny grazes get no sound). Otherwise `note_gap` has to drop most notes: hits go
  silent and the melody turns into noise.
- Pace: **2–10 melody notes per second**, and no silence over 3.5 s while things move. Big moments (a ring breaks, a
  ball is eliminated, a new stage) get a `break` at the same instant as their flash or `p.punch()`.
- Never touch `self.rnd` or physics state in `draw`, `prepare` or `on_event`: the soundtrack comes from a separate
  physics run, so if painting changes the physics, sound and picture drift apart.
- The gate checks all of this: it re-runs the physics while painting (any drift fails), counts dropped and silent
  notes and the longest silence, and prints the pace. Fix the events, not the threshold.

### Tempo experiment: faster, more balls (since October 2026)

The owner wants to find out whether faster concepts hold attention better – faster balls, more balls, more hits
per second.

- Every night **at least one of your two concepts is fast**, marked with `tempo = "fast"` in the class. Fast means:
  action from the very first frame (no slow start), **4–10 audible hits per second**, and either many balls
  (30–300) or balls that are fast from the start and keep getting faster. The gate fails a "fast" concept that is
  not.
- Fast is not chaos: the viewer must still follow one thing – a leader, a counter racing to a limit, the last
  survivor, the colour that is winning. Our best performers so far (stringart ×3.9, escape ×2.4) are single balls
  that get faster with every bounce: speed-up with a clear focus is what holds people.
- Levers: start fast instead of slow; double the speed or the ball count in stages; split one ball into two on every
  hit; hundreds of balls racing for one exit; 100-ball elimination battles; a final sprint where everything speeds
  up. Keep the melody on the hero (see above), the rest clacks.
- Evaluation: `python -m ytauto concepts` prints "experiment fast with ×… vs without ×…". Once at least 4 fast
  concepts have numbers: if fast is ≥ 1.2× the rest, make both nightly concepts fast; if fast is ≤ 0.8×, build a
  fast one only every other night; in between keep one fast and one free. Quote the line in your report.

### Experiments and learnings (every run)

You start every night without memory – `docs/loop-physics-learnings.md` is the channel's memory. Read it before
you pick ideas, together with the "experiment …" lines at the top of `python -m ytauto concepts` (median views
factor of the concepts with a property vs without it: 3d, fast, short and every custom `experiment` tag) and the
trend check in `docs/loop-physics-trends.md`.

- One of the two nightly concepts builds on what works (the learnings), the other may be a bolder experiment: a
  new format, length, hook, camera move, material, sound design – whatever you believe could go viral.
- **Short format**: set `min_video` (e.g. 20) and `run_ranges` (e.g. `[(17, 22), (20, 26), (24, 32)]`) on the
  class. Trending satisfying Shorts are ~24 s long; ours are over a minute because TikTok's Creator Rewards need
  that. Short ones earn nothing on TikTok but are watched to the end and replayed – make them loop seamlessly
  (the last frame leads back into the first) so the replay counts. The "experiment short" line decides.
- Adapt: when an experiment line has at least 4 concepts with numbers, a factor ≥ 1.2× makes it the default (write it
  into the learnings), ≤ 0.8× drops it (note that too), anything between keeps testing.
- At the end of the run update `docs/loop-physics-learnings.md` (newest first, at most ~20 points, delete what is
  outdated or disproven) and commit it with your concept.

## 3. Test until it is great

```bash
python -m ytauto concept-check <kind>          # quality gate + out/concepts/<kind>.png (8 moments)
```

Fix every ✗. Then **look at the contact sheet** (read the PNG) like a viewer scrolling past: is the hook clear in
the first frame? Is something changing in every moment? Does it build up? Is the finale a climax? Are colours and
text readable? Iterate on the design, not only on the gate. Then:

```bash
python -m ytauto concept-check <kind> --full    # renders the real video (a few minutes) and checks loudness
v=$(ls out/concepts/<kind>-*.mp4 | head -1)
for t in 1 10 20; do ffmpeg -loglevel error -ss $t -i "$v" -frames:v 1 -y out/concepts/at$t.png; done
for t in 6 3 1; do ffmpeg -loglevel error -sseof -$t -i "$v" -frames:v 1 -y out/concepts/end$t.png; done
```

Look at those frames too (`end*` = seconds before the end), especially the finale.

If you cannot get a PASS after a few honest attempts, switch to a simpler idea. Never commit a concept that fails
the gate – a missing concept only means the channel posts a standout instead, a broken one costs a slot.

## 4. Commit

Only `ytauto/concepts/<kind>.py` (plus a small shared-code fix if you really needed one – then
`python -m ytauto concept-check --all` must still pass for every kind).

```bash
git add ytauto/concepts/<kind>.py
git commit -m "Loop Physics concept: <kind> – <idea in a few words>"   # plus the attribution lines you were given
for i in 1 2 3 4; do git pull --rebase origin main && git push origin HEAD:main && break; sleep $((i * 5)); done
```

Finish with a short report: the idea, what inspired it, the finale, the run lengths the gate found.

## Never

- touch `state/`, `config/` tokens or keys, `.github/workflows/`, secrets, or other concepts' files (except the
  sound fixes listed in section 0);
- post, upload or start workflows yourself;
- use copyrighted music, footage, logos, real people or brand names; claim things in titles that do not happen;
- commit anything under `out/`.

## Viral songs (every run)

Every bounce plays the next note of a melody, and the melody is a big part of why a video takes off – our Für Elise
escape run reached 16,000 views, many times the channel median. So every designer run also checks which songs
are viral right now:

1. Research (web search, 3–5 queries): which songs and sounds are trending in satisfying / ball / marble / physics
   simulation Shorts, Reels and TikToks this week – TikTok Creative Center "Popular songs", "trending sound
   satisfying simulation", "viral piano song tiktok", seasonal moments (Halloween: Toccata and Fugue, Danse
   Macabre, In the Hall of the Mountain King; December: Carol of the Bells, the Nutcracker, Jingle Bells).
2. `python -m ytauto melodies` shows each melody's posts, our own view lift, the daily trend signal and its current
   chance. Our own numbers beat outside hype: a melody that keeps flopping for us is not boosted.
3. **Public-domain pieces only go into the videos** (composer died more than 70 years ago and the piece was published
   before 1930; traditional tunes). If a viral piece qualifies:
   - already in `sims.MELODIES` → raise its factor in `config/sims_music.json` → `boost` (1.0–3.0; 1.0 = neutral);
     seasonal ones get an end date in `seasonal_until` (they switch off by themselves);
   - not in it yet → add its best-known theme to `MELODIES` in `ytauto/sims.py`: MIDI note numbers of the melody
     line in order (one note per bounce, 18–60 notes, in the range 55–88), transcribed from public-domain sheet music
     (IMSLP / Mutopia) and checked note by note; add the composer to `COMPOSERS` in `ytauto/simchannel.py`.
     Render one quick check: `python -m ytauto sim --kind escape --melody <key>`.
4. **Copyrighted viral songs never go into our videos.** Put the best 3–6 of them into `tiktok_sounds` (name – artist,
   short reason) – they appear on top of the TikTok checklist (state/tiktok.md) so the owner can pick one in the
   TikTok app, where the music is licensed.
5. Lower boosts again when a trend is over; keep `notes` to one or two lines on why the current boosts are set.
6. **Song quiz (experiment since 20 Oct 2026).** In a share of the videos (`song_quiz_share` in
   config/sims_music.json, start 0.5) the melody's name is hidden everywhere – on screen it says "CAN YOU NAME THIS
   SONG? Write it in the comments", the title ends in "Can you name the song?", caption and description say "a famous
   melody" – so the answers land in the comments. The line "song quiz" in `python -m ytauto concepts` compares
   views and comments per post with the videos that show the name. Once both sides have at least 8 videos with
   numbers: quiz views ≥ 1.2× or comments ≥ 2× (with views not below 0.9×) → raise the share to 0.8; quiz views ≤ 0.8×
   without more comments → lower it to 0.2; otherwise leave it. Well-known, viral melodies make the best quiz – that
   is another reason to boost them. Note the result in the learnings.
   Commit `config/sims_music.json` (and sims.py/simchannel.py if you added a melody) together with your concept.

## Session prompt (used by the scheduler)

Once a day (03:13 German time, so the owner's Claude usage window is fresh again in the morning) a scheduled task
wakes the channel's main Claude session, which starts a fresh
designer session with this repository attached (`create_session`, source `hthkrksy54-dotcom/Yt`, revision and
outcome branch `main`, tag `loop-physics-designer`) and this prompt:

```text
You are the Loop Physics concept designer. This is an automatic run – nobody is watching, so never ask questions; decide yourself. You work in the checkout of hthkrksy54-dotcom/Yt (branch main).

1. `git checkout main && git pull origin main`, `pip install -q -r requirements.txt`, then read docs/concept-designer.md completely and follow it (its defaults may be broken where the section "Creative freedom" allows), and read docs/loop-physics-learnings.md.
2. Check the queue with `python -m ytauto concepts` (stop if 6 or more concepts are already waiting). If the "Sound fixes first" list in section 0 is not empty, fix the first concept on it before anything else.
3. Research what is going viral right now in satisfying / physics / ball simulation Shorts, Reels and TikToks (web search), and pick TWO ideas that do not exist yet – each a different core mechanic, not a recolour – ideally with an escalating finale, both 3D particle simulations in the style of @particlesflow built with ytauto/sim3d.py (section "Style: 3D particle simulations"); at least one of them fast (section "Tempo experiment"); one builds on the learnings, the other may be a bolder experiment (section "Experiments and learnings"). In both, the music must fit exactly what happens on screen (section "Sound = picture").
3b. Viral songs: follow the section "Viral songs (every run)" in docs/concept-designer.md – research which songs trend right now, update config/sims_music.json (boosts for public-domain melodies, trending TikTok sounds for the owner) and add a trending public-domain melody if one is missing.
4. Build the first as ytauto/concepts/<kind>.py from ytauto/concepts/_template.py, iterate until `python -m ytauto concept-check <kind> --full` passes, and look at the contact sheet and the extracted frames (especially the finale) – improve it until it looks great to a viewer scrolling past.
5. Commit that file (plus config/sims_music.json and, if you added a melody, sims.py/simchannel.py) and push it directly to main (`git pull --rebase origin main && git push origin HEAD:main`, retry a few times). No pull request, no other branch. Do not post, upload or start workflows – the Loop Physics workflow posts it at the next slot.
6. Then build, check and push the second idea the same way (skip it if 6 or more concepts are waiting by then).
7. Update docs/loop-physics-learnings.md with what the numbers and your research taught you, commit and push it.

End with a short report in German: pro Konzept Idee, Inspiration, Finale, Tempo (schnell/normal, Treffer pro Sekunde), gefundene Laufzeiten; die "experiment …"-Zeilen und was du daraus gelernt bzw. geändert hast (Learnings); dazu virale Songs (was geboostet/neu) – or exactly why nothing was committed.
```
