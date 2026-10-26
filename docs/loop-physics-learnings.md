# Loop Physics – what we learned

The concept designer reads this before every run and updates it at the end (newest first, at most ~20 points,
remove what is outdated). Numbers: views factor vs the channel median (`python -m ytauto concepts`).

- 2026-10-26 · **Numbers**: series ×0.95 (3) vs ×0.89 – tower_drop (×8.9) carries it, hole_eater/gate_rush pull it to
  neutral; still under 4, keep one series per night (new: press_drill). 3d ×0.95 (11) vs ×0.89 and fast ×0.98 (6) vs
  ×0.76 – **fast is ×1.29 the rest with 6 concepts → rule ≥1.2×: from now on both nightly concepts are fast** (both
  were tonight). short/loop ×0.66 (2), softness ×0.51 (1), halloween ×0.56 (1): weak, nothing new
  in those. Followers: Instagram 19 (+5 in 2 d), YouTube 62 (+15 in 2 d).
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
- 2026-10-26 · **Songs**: song quiz reached 10 vs 12 posts – views ×1.11 vs ×0.92 (1.21×), comments equal → share 0.8.
  Twinkle (×2.38) and Carol of the Bells (×2.28) → 1.7; new PD melody We Wish You a Merry Christmas (1.3 until Jan 6).
  Web still has no ranking for sim songs.
- 2026-10-25 · **Series is the standout format: ×5.18 over 2 concepts** (tower_drop ×9.8, hole_eater) vs ×0.95 without
  – still under 4 concepts, but strong enough to keep one series per night. Third series started: gate_rush (RUN #N,
  goal +500 balls per episode). 3d ×1.02 (8) vs ×0.90, fast ×1.02 (5) vs ×0.91 – neutral (0.8–1.2), keep one fast +
  one free. Followers: Instagram 17, YouTube 56 (+9 in a day).
- 2026-10-25 · **Short/loop**: chladni_plate + bead_picture (~21 s loops) – ×0.66 over 2 so far. Decide at 4.
- 2026-10-25 · **3D build tricks**: thousands of free balls are cheap in numba with a spatial *hash* (fixed 2^15 table,
  linked lists) – 5,000 balls with peg rods, walls and ball contacts simulate a 70 s run in ~4 s. Rods that touch the
  walls stop balls wedging between rod and wall (they stuck forever otherwise). Gates planned on the fly from the
  *expected* count (per-ball cumulative product of the gates still ahead, realised averages once 30 balls passed)
  steer an honest random process to its goal; the last gate stays "×?" until the front is close, then its number is
  set from the real swarm – exact goal and a reveal moment. A narrow tall box makes "filling to the goal line" readable.
  Clones inherit colour from where they fell through → rainbow stripes in the pile instead of one colour.
- 2026-10-24 · **Experiment "softness" started** (softness_scale): the viral "0% vs 100% softness" format – the same net
  in 11 rounds, only XPBD compliance changes, 100% tears. Watch whether a comparison format pulls comments ("which % was
  best?").
- 2026-10-24 · **3D build tricks**: XPBD stiffness is capped by iterations (12 iters: anything under ~1e-5.3
  compliance sags the same) – map softness on a log scale from ~10^-5.25 upwards so every round looks different;
  above ~10^-3.3 links open gaps and balls slip through. Hole/clipping look: draw beads below the floor onto a copy and
  composite it through the projected hole ellipse. Big sprites in ~6 % radius steps cut paint time from ~200 to
  ~140 ms/frame with many beads near the camera. A city of ~190 objects along an inward spiral gives ~3 melody
  notes/s by construction (planned swallow times).
- 2026-10-23 · **Experiment "series" started** (tower_drop): TOWER #N, five floors more per episode, "NEXT: TOWER #N+1"
  above the follow button. No shared-code change needed: the run length is planned exactly and fits every seed, so the
  seed search always takes the next free seed and episode = seed + 1. Reusable trick for any future series.
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
- 2026-10-20 · **Calm drawing machines underperform**: pendulum ×0.59, harmonograph ×0.66, black_hole ×0.65.
- 2026-10-20 · **Sound = picture**: melody only on the hits the viewer follows, the rest clacks; the gate checks
  dropped notes and silences (`concept-check`).
