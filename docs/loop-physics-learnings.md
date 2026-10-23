# Loop Physics – what we learned

The concept designer reads this before every run and updates it at the end (newest first, at most ~20 points,
remove what is outdated). Numbers: views factor vs the channel median (`python -m ytauto concepts`).

- 2026-10-23 · **3D catches up: ×1.02 over 4 posts vs ×0.92 without** (fast ×0.91 over 3 – still neutral, keep one
  fast + one free). Standouts unchanged: escape ×2.9, stringart ×2.9, polygon ×2.7, lava_climb ×2.6 – all "one hero
  that speeds up and breaks through". Tonight's fast concept (tower_drop) is exactly that formula as a vertical fall.
- 2026-10-23 · **Experiment "series" started** (tower_drop): TOWER #N, five floors more per episode, "NEXT: TOWER #N+1"
  above the follow button. No shared-code change needed: the run length is planned exactly and fits every seed, so the
  seed search always takes the next free seed and episode = seed + 1. Reusable trick for any future series.
- 2026-10-23 · **Experiment "halloween" started** (pumpkin_carve): seasonal hook – steel balls carve a jack-o'-lantern
  out of 4,000 beads, the candle lights the face at the end. Posts right before Oct 31; compare views, and expect it
  to drop after Halloween in rotation.
- 2026-10-23 · **3D build tricks**: planned (analytic) kinematics instead of XPBD for scripted mechanics (tower fall,
  shot schedule) make length, sound and visuals exact and simulate in milliseconds; set `planned_end`. A moving
  camera works with a static gradient background (no studio slab). Cull debris flying at the lens (big projected
  radius / close depth) – otherwise blobs cover the title. A light "inside" a shell: paste far beads, add the glow,
  then paste near beads – it only shows through holes.
- 2026-10-23 · **Songs**: no outside chart for sim songs again; trends are Halloween reveal sounds (Ramalama, Spooky
  Scary Skeletons) and the Black Parade 20th anniversary (TikTok list only). Danse Macabre would be the ideal
  Halloween PD melody but no verifiable note-by-note source was found – not added (add it once a PD score/MIDI can
  be checked).
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
- 2026-10-22 · **Songs**: no outside ranking for satisfying-sim songs on the web; Halloween roundups list only pop
  and meme sounds (Ramalama, Spooky Scary Skeletons). Added Sugar Plum Fairy (Tchaikovsky, verified against a
  public-domain MIDI) for the Nov–Dec season, boost 1.5 until Jan 6 – a well-known melody for the song quiz.
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
- 2026-10-21 · **Song numbers** (22 Oct): Twinkle ×3.8 and Morning Mood ×2.3 are our best lifts (boosted 1.6 / 1.3);
  Mountain King stays neutral (own lift ×0.9) despite Halloween; Toccata 1.8 until Nov 1. Song quiz: 2 vs 4 posts
  (views ×0.93 vs ×0.98, no comments either side) – too early to judge.
- 2026-10-20 · **Song quiz started**: half of the videos hide the melody's name and ask "Can you name this song?" –
  watch the "song quiz" line (views and comments per post). Before this, titles sometimes said "Guess the song"
  while the name was on screen – fixed.
- 2026-10-20 · **Length is the biggest open question.** Trending satisfying Shorts are ~24 s long
  (trend check, 133 videos); ours run 61–86 s because TikTok's Creator Rewards need over a minute. Short videos
  earn nothing on TikTok but get watched to the end and replayed – test short-format concepts (min_video ~20 s,
  ideally a seamless loop) and compare with "experiment short".
- 2026-10-20 · **Speed-up with one clear focus wins.** stringart ×4.2 and escape ×2.6 (best video 38,476
  views) are single balls that get faster with every bounce; polygon ×1.8 is the same idea. Busy many-ball
  battles and races mostly land between ×0.65 and ×1.3.
- 2026-10-20 · **Calm drawing machines underperform**: pendulum ×0.59, harmonograph ×0.66, black_hole ×0.65.
- 2026-10-20 · **Melodies matter**: twinkle, moonlight and morning_mood lift our views ~2.2–2.6×; Für Elise
  carried the 38k escape run.
- 2026-10-20 · **Sound = picture**: melody only on the hits the viewer follows, the rest clacks; the gate checks
  dropped notes and silences (`concept-check`).
