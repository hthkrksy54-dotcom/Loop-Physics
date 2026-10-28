# Loop Physics – what we learned

- 2026-10-28 · **Numbers**: fast ×0.93 (7) vs ×0.90 = 1.03× – the 1.3× lead of the last two nights is gone, fast is
  back to neutral → **one fast + one free per night again** (snowball_roll fast 7.4 hits/s, layer_drop normal 3.6).
  series ×0.90 (4) vs ×0.92 – neutral at 4 concepts (tower_drop carries it alone); no new series tonight, keep the
  running ones. 3d ×0.93 (12) vs ×0.86. Song quiz 14 vs 12: views ×1.08 vs ×0.92 (1.17×), comments 0.2 vs 0.1 →
  share stays 0.8. Followers up: Instagram 27 (+13 in 4 d), YouTube 68 (+21 in 4 d) – the best 4 days so far.
  New experiment **"suspense"** (layer_drop): the opposite of a speed-up – a rhythm that *slows* as every layer
  holds longer, and an outcome that changes per post (stuck on layer 84–100 or all 100) to pull guesses.
- 2026-10-28 · **3D build tricks**: accretion (a ball that picks up what it rolls over) is cheap when planned: one
  120 Hz pass over the carpet rows near the ball decides every pick-up time (R³ = R0³ + K·beads, 0.15 s for 70,000
  beads); stuck beads keep a local direction and roll with the ball; draw only the outer layer (picked within the
  last ΔR *and* the last full turn – otherwise one side stays bare) over a solid core sprite, and spread the stick
  points over the whole sphere (x / 0.8) or the poles show the core. A razor-edge outcome ("fails exactly on layer
  S") must be bisected with the same integrator *and step* as the final run – then rescale time, never re-integrate
  with scaled gravity (the discrete steps flip the outcome by one layer). Membrane dent = logarithmic profile
  (point load), no XPBD needed; layer numbers next to the rim (projected text in draw_text) make a stack readable.
  Sound for slow phases: put the melody on visible creaks (a white crack ring flashing around the dent) and on every
  rebound of a stuck ball – silence otherwise exceeds 3.5 s.
- 2026-10-28 · **Research**: still no reliable web ranking for sim shorts or songs this week; the recurring 3D
  formats remain "ball vs N layers", softness comparisons and snowball/grow clips; seasonal pivot from Nov 1 to
  Christmas. Own lift: Morning Mood ×2.02 (4 posts) → 1.6, Mountain King ×0.87 (4) → 0.9. New PD melody Joy to the
  World (Mason 1839, 1.3 until Jan 6).
The concept designer reads this before every run and updates it at the end (newest first, at most ~20 points,
remove what is outdated). Numbers: views factor vs the channel median (`python -m ytauto concepts`).

- 2026-10-27 · **Numbers**: fast ×1.02 (6) vs ×0.78 = 1.31× → stays the rule, both concepts tonight are fast (bridge_run
  10.5 hits/s, well_duel 5.1). series ×0.99 (3) vs ×0.91 – still neutral and under 4 with numbers; fourth series started
  (bridge_run). 3d ×0.99 (11) vs ×0.91. Song quiz now 12 vs 12 posts: views ×0.95 both, comments equal → share stays 0.8.
  Followers unchanged (Instagram 19, YouTube 62). New experiment **"versus"** (well_duel): red vs blue with a score
  line and "RED WINS!" – battles have landed ×1.2–1.3 (zombie_tag, blade_duel, battle); does picking a side pull comments?
- 2026-10-27 · **3D build tricks**: rigid pieces need no physics state – a snapped plank half is centre ballistic +
  rotation matrix of (spin × τ), computed at render time from its snap time, so falling debris costs nothing in
  simulate(). A chase is easy to plan: front(t) = ball progress − lag(t) (lag shrinking to ~1), then
  searchsorted the snap time of every plank. Membranes as an analytic height field (sum of Lorentzian wells × border
  taper) with marbles rolling on its finite-difference slope give orbits, captures and the inspiral in ~6 s for 400
  marbles – no XPBD needed when nothing has to tear physically. Pre-spawn a few marbles already falling into the wells
  with staggered tangential speed, or the first 2–3 s are silent. A camera behind a hero moving into the screen needs
  yaw ≤ 0.2, or the hero drifts to the frame edge; never cull the hero by sprite size (it vanished at r ≥ 60 px).
  Status lines in the counter (y 420), never near y 1500 – the melody credit sits there.
- 2026-10-26 · **Standouts share one shape**: tower_drop ×8.9, escape/polygon/lava_climb ×2.6, split_trampoline ×2.1 –
  one hero, a visible goal that gets closer (floors, rings, lava, walls), hits speeding up to ~10/s. press_drill copies
  that shape with a new mechanic (closing press vs. drilling); critical_mass tests the opposite (no single hero, an
  exponential chain story told in rounds – experiment "rounds").
- 2026-10-26 · **3D build tricks**: event-driven kinematics (solve the next wall hit with Newton on a smooth press curve,
  bisect the press speed for the target length) makes a fully planned 60–70 s run in ~0.05 s – the series trick
  (episode = seed + 1) works for any planned mechanic. Precompute when each bead is knocked out (searchsorted of the
  needed depth into the per-hit depth list) instead of testing beads every frame. Draw only exposed beads of a solid
  block (6-neighbour test on the occupancy grid): ~3,000-bead walls paint at ~70 ms/frame. Steep pitch (~0.9 rad) with
  the moving axis pointing into the screen keeps a long scene inside the 9:16 frame. Pulled rods slide out sideways –
  anything that rises crosses the title. Chain reactions: give the melody to a split only if note_gap has passed, else
  clack – the gate stays green at hundreds of splits.
- 2026-10-25 · **Short/loop**: chladni_plate + bead_picture (~21 s loops) – ×0.66 over 2 so far. Decide at 4.
- 2026-10-25 · **3D build tricks**: thousands of free balls are cheap in numba with a spatial *hash* (fixed 2^15 table,
  linked lists) – 5,000 balls with peg rods, walls and ball contacts simulate a 70 s run in ~4 s. Rods that touch the
  walls stop balls wedging between rod and wall (they stuck forever otherwise). Gates planned on the fly from the
  *expected* count (per-ball cumulative product of the gates still ahead, realised averages once 30 balls passed)
  steer an honest random process to its goal; the last gate stays "×?" until the front is close, then its number is
  set from the real swarm – exact goal and a reveal moment. A narrow tall box makes "filling to the goal line" readable.
  Clones inherit colour from where they fell through → rainbow stripes in the pile instead of one colour.
- 2026-10-24 · **3D build tricks**: XPBD stiffness is capped by iterations (12 iters: anything under ~1e-5.3
  compliance sags the same) – map softness on a log scale from ~10^-5.25 upwards so every round looks different;
  above ~10^-3.3 links open gaps and balls slip through. Hole/clipping look: draw beads below the floor onto a copy and
  composite it through the projected hole ellipse. Big sprites in ~6 % radius steps cut paint time from ~200 to
  ~140 ms/frame with many beads near the camera. A city of ~190 objects along an inward spiral gives ~3 melody
  notes/s by construction (planned swallow times).
- 2026-10-23 · **3D build tricks**: planned (analytic) kinematics instead of XPBD for scripted mechanics (tower fall,
  shot schedule) make length, sound and visuals exact and simulate in milliseconds; set `planned_end`. A moving
  camera works with a static gradient background (no studio slab). Cull debris flying at the lens (big projected
  radius / close depth) – otherwise blobs cover the title. A light "inside" a shell: paste far beads, add the glow,
  then paste near beads – it only shows through holes.
- 2026-10-22 · **Followers are the bottleneck, not views**: Instagram 125,000 views → 13 followers, 12 shares,
  2 comments. Changed: the end button says "FOLLOW FOR MORE" (was "LIKE & SUBSCRIBE"), Instagram captions ask to
  send the clip on, daily follower counts in the "followers" line. Next: the `series` experiment (numbered episodes
  that get harder, teaser of the next one) – section "Follow reasons" in the designer brief.
- 2026-10-22 · **Experiments "short" + "loop" started** (chladni_plate, ~22 s): cymatics figures – every note thumps
  a plate, beads gather on the silent lines; one big thump scatters them back to the first frame (seamless loop).
  First short-format concept; watch "experiment short" and "experiment loop".
- 2026-10-22 · **3D build tricks**: nested shells stay readable when outer shells are glass (front half alpha ~70,
  back half dimmed) and the active shell's front half is ~60 % opaque – otherwise the hero vanishes. Chladni figures
  need alternating ± mode combinations (the − combination always has a node on the diagonal, which traps every
  bead), a "shake-apart" thump at each new pattern and a little jitter so lines stay thick. Analytic physics in
  numpy (no XPBD) is enough when nothing has to tear: both concepts simulate in 1–5 s.
- 2026-10-21 · **Experiment "guess" started** (hidden_shape): invisible shapes push up a sheet, the name appears
  only after a pause, the last one is never named – meant to pull guesses into the comments. Watch "experiment
  guess" (views and comments). Research: "guess the hidden object" and "0% vs 100% softness" soft-body shorts are
  the recurring 3D formats this month; no reliable view rankings found on the web.
- 2026-10-21 · **3D build tricks that worked**: a pinned sheet lying *on* the platform with compliance ~1e-3 hugs
  hidden spheres tightly enough to read shapes (stiffer sheets tent into blobs); colour the flat sheet cool grey and
  only the bumps hot, so the relief pops. In a crowd, give the hero a heavier mass, an instant relaunch and a soft
  halo – otherwise it disappears among 100+ balls. Pinned-net popcorn with 150 balls simulates in ~10 s.
- 2026-10-21 · **Melody on the hero, enforced**: brick_core only passed once the melody went to the lead ball/core
  *and* a hit closer than note_gap to the last note became a clack – a simple, reusable pattern for swarms (used
  again for the territory sound fix and orb_escape on 22 Oct).
- 2026-10-20 · **Length is the biggest open question.** Trending satisfying Shorts are ~24 s long
  (trend check, 133 videos); ours run 61–86 s because TikTok's Creator Rewards need over a minute. Short videos
  earn nothing on TikTok but get watched to the end and replayed – test short-format concepts (min_video ~20 s,
  ideally a seamless loop) and compare with "experiment short".
- 2026-10-20 · **Speed-up with one clear focus wins.** stringart ×4.2 and escape ×2.6 (best video 38,476
  views) are single balls that get faster with every bounce; polygon ×1.8 is the same idea. Busy many-ball
  battles and races mostly land between ×0.65 and ×1.3.
- 2026-10-20 · **Sound = picture**: melody only on the hits the viewer follows, the rest clacks; the gate checks
  dropped notes and silences (`concept-check`).
