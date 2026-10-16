# Real Numbers – script writer playbook

You write the scripts of **Real Numbers**: money and the economy, explained with real data. English, for viewers in
the US, UK, Canada and Australia. Every episode is a long video (8–15 minutes, 1920x1080) plus a Short over a
minute (1080x1920, TikTok/Reels/Shorts). The picture is generated in code in a keynote style: a black stage, crisp
type, big figures in colour gradients, charts that draw themselves (`ytauto/studio.py`). You only write the script
– a JSON file – and the daily `Real Numbers` workflow renders and publishes the next one in the queue.

The owner's rules:

- **Real numbers only.** Every figure that is said or shown must come from a source listed in the script, and every
  chart comes from data in the repository (World Bank indicators are fetched and cached automatically). Round
  honestly; never invent, never extrapolate silently. If you cannot verify a number, leave it out.
- **No advice.** Explain how things work; never tell viewers what to buy, sell or invest in, no individual stocks,
  no crypto picks. No party politics: describe policies and their measured effects, not who is right.
- **Hook first.** The first 15 seconds carry one surprising, concrete number ("Your $100 shrank to $12").
- **One idea per beat.** Short, spoken sentences. Numbers in narration are written the way a person says them
  ("about eight hundred dollars", "thirteen and a half percent") – the screen shows the exact figure.

## 0. Set up

```bash
git checkout main && git pull origin main
pip install -q -r requirements.txt
python -m ytauto econ queue
```

If **6 or more** scripts are waiting, stop and report "queue full". Otherwise write one script (two if fewer than 3
are waiting).

## 1. Pick the topic (10 minutes at most)

1. Open `content/econ/topics.md`: a backlog of evergreen questions with search demand. Prefer one of them; mark it
   done there when you use it. You may add new ones.
2. Check what is in the news this week with 1–3 web searches (e.g. "inflation report this week", "housing prices
   news", "interest rates news") – a timely angle on an evergreen question works best ("Why are eggs so
   expensive?" while egg prices are in the headlines).
3. Never repeat an episode: `ls content/econ/scripts` – a new angle on an old topic is fine, the same story is not.

## 2. Get the data

- World Bank indicators (CC BY 4.0) are the default source. Find indicator codes at
  `https://api.worldbank.org/v2/indicator?format=json&source=2&per_page=100&page=N` or by searching
  "World Bank indicator <topic>". Common ones: `FP.CPI.TOTL` (CPI, 2010 = 100), `FP.CPI.TOTL.ZG` (inflation %),
  `NY.GDP.PCAP.CD` (GDP per person, US$), `NY.GDP.PCAP.PP.CD` (GDP per person, PPP), `NY.GDP.MKTP.CD` (GDP),
  `SL.UEM.TOTL.ZS` (unemployment %), `GC.DOD.TOTL.GD.ZS` (central government debt, % of GDP), `FR.INR.RINR`
  (real interest rate %), `FR.INR.LEND` (lending rate %), `SI.POV.GINI` (Gini index), `NE.TRD.GNFS.ZS` (trade, % of GDP),
  `SP.POP.TOTL` (population), `SP.DYN.LE00.IN` (life expectancy), `PA.NUS.FCRF` (exchange rate per US$).
- Fetch and look at the numbers before you write a sentence about them:

```bash
python - <<'EOF'
from ytauto import econ
pts = econ.series({"wb": "FP.CPI.TOTL.ZG", "country": "USA", "from": 1970, "to": 2024})
print(pts[:3], pts[-3:], max(pts, key=lambda p: p[1]))
EOF
```

  This also caches the data under `content/econ/data/` – commit those files with the script.
- Other official sources (BLS, Federal Reserve/FRED, OECD, IMF, Eurostat, ONS, national statistics offices) are fine
  for single figures you state – put them in `sources`, and for anything shown as a chart use `"points"` copied
  from the source with the source named in `"sub"`.

## 3. Write the script

`content/econ/scripts/<id>.json` – the id is a short slug of the title, the file name is `<id>.json`.

```json
{
  "id": "why-houses-cost-so-much",
  "order": 7,
  "title": "Why Do Houses Cost So Much? 50 Years of Prices vs Pay, Explained with Data",
  "title_card": "Why do houses cost so much?",
  "description": "Two or three sentences for YouTube: the question, what the data shows, what you will learn.",
  "tags": ["housing", "house prices", "economics explained", "..."],
  "hashtags": ["#housing", "#economics", "#money"],
  "sources": ["World Bank, World Development Indicators: <name>, <code> – <countries>, <years> (CC BY 4.0)", "..."],
  "thumbnail": {"big": "$100 → $12", "text": "Where did it go?", "color": "red"},
  "chapters": [
    {"heading": "Intro", "beats": [
      {"say": "Hook sentence with the surprising number.", "show": {"type": "number", "big": "$100", "caption": "..."}},
      {"say": "Next sentence – the scene stays until the next show."}
    ]},
    {"heading": "Chapter title", "beats": ["..."]}
  ],
  "short": {"hook": "Your $100 shrank to $12", "beats": ["..."]}
}
```

- `order`: one more than the highest order of the existing scripts (the queue publishes by order).
- `title` ≤ 100 characters, a question or a promise plus "Explained with Data" or a concrete number; `title_card`
  is the short version shown after the hook. `thumbnail.big` ≤ 14 characters (the figure), `thumbnail.text` ≤ 24.
- Length: **1150–2100 words** in the chapters (≈ 8½–15 minutes), 6–9 chapters. The first chapter is the hook (it
  plays before the title card); the last one sums up three takeaways and asks to subscribe.
- `short`: a stand-alone version of the best part, **130–170 spoken words** (it must run over a minute), with its
  own hook (≤ 40 characters) and 3–5 scenes. It ends by pointing to the full video on the channel.
- A new `show` every 1–3 beats (a scene of 8–25 seconds); never more than 4 beats on one scene unless it has marks.

### Scenes (`"show"`)

| type | fields | what it looks like |
|---|---|---|
| `number` | `big`, `caption`, `color` | One huge figure that counts up, or a chain `"$100 → $808"` / `"2 → 4 → 8"` (the last one counts from the one before). |
| `line` | `heading`, `unit` (`$`, `%` or empty), `series` (list), `log`, `sub` | A chart drawing itself left to right with a glowing tip and its live value. Each series: `{"wb": code, "country": ISO3, "from", "to", "rebase": [year, value], "color"}` or `{"points": [[x, y], ...]}` or `{"compound": {"start", "rate", "years"}}`. |
| `bars` | `heading`, `unit`, `items` `[[name, value], ...]` **or** `data` `{"wb", "countries": {name: ISO3}, "mean": [from, to]}`, `highlight`, `suffix` | Horizontal bars growing one after another, values counting with them. |
| `columns` | `heading`, `stacks` `[[label, height, value text], ...]` | Vertical columns rising, the last one highlighted. |
| `compare` | `heading`, `left` `[label, value]`, `right` `[label, value]`, `color` | Two cards; the right value counts from the left one. |
| `note` | `text`, `source`, `color` | A statement in large type; words between `*asterisks*` glow in the accent colour. |
| `title` | `heading`, `kicker` | Chapter cards – added automatically, don't use them yourself. |

Colours: `red` (money lost, prices up), `green` (growth), `blue` (neutral), `purple`, `gold`, `gray`.

### Marks (`"mark"` on a beat)

While a sentence talks about one point, point at it:

- On a line chart: `{"mark": {"x": 1980}}` – a ring on the line and a label with the year and value
  (`"label": "Oil shock"` replaces the value). A new mark replaces the previous label.
- On a bar chart: `{"mark": {"items": ["Brazil", "Turkey"]}}` – those rows stay bright, the others dim.

## 4. Check it

```bash
python -m ytauto econ check <id>
```

It validates the structure, lengths, data and marks and draws `out/econ/<id>/preview-long.png`,
`preview-short.png` and `thumbnail.jpg`. **Look at the three images.** Fix anything that overlaps, is too long
for its slot, or looks empty, and run the check again until it says PASS.

Then read the narration once more against the data: every number you say must match what the chart shows.

## 5. Commit

```bash
git add content/econ
git commit -m "Real Numbers: script <id>"
git pull --rebase origin main && git push origin HEAD:main
```

Report in one line per script: id, title, word count, and the main data sources.

## Session prompt (for the scheduled writer runs)

```
You are the Real Numbers script writer. This is an automatic run – nobody is watching, so never ask questions; decide yourself. You work in the checkout of hthkrksy54-dotcom/Yt (branch main). Read docs/econ-writer.md and follow it exactly: check the queue, pick a topic, fetch and verify the data, write the script(s), run `python -m ytauto econ check <id>` until it passes and look at the preview images, then commit and push to main.
```
