"""Daily trend check for Loop Physics: what is going viral in satisfying Shorts, what works on our own
Instagram, and a tuning file (config/sims_tuning.json) that steers formats, lengths, titles and hashtags.

YouTube data is only aggregated in memory (themes, keywords, lengths, hashtags) – no third-party titles or
statistics are stored, per the YouTube API Services policies. Our own Instagram numbers are kept in state.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import statistics
from collections import Counter

import requests

from . import generate, instagram, simchannel

YT = "https://www.googleapis.com/youtube/v3"
QUERIES = ["satisfying simulation", "satisfying physics", "bouncing ball simulation", "oddly satisfying balls",
           "marble race", "ball escape rings"]
KIND_WORDS = {
    "escape": ["escape", "ring", "rings", "circle", "break out", "spinning", "gap"],
    "polygon": ["hexagon", "polygon", "square", "triangle", "octagon", "pentagon", "shape"],
    "battle": ["color", "colour", "race", "battle", "wins", "team", "country", "countries", "vs", "versus"],
    "grow": ["grow", "grows", "bigger", "size", "fills"],
    "multiply": ["multiply", "duplicate", "clone", "adds", "spawn", "1000", "more balls"],
    "plinko": ["plinko", "galton", "bell curve", "pegs", "probability"],
    "stringart": ["string", "pattern", "draw", "draws", "lines", "art"],
    "pendulum": ["pendulum", "pendulums", "wave", "sync"],
}
STOP = set("the a an and or of to in on at for with is are this that it its you your my me i we be will can how "
           "what why when who which every each one all just new video videos shorts short satisfying oddly".split())
JUNK_TAGS = {"shorts", "short", "viral", "fyp", "foryou", "foryoupage", "trending", "youtube", "subscribe", "like",
             "tiktok", "reels", "reel", "explore", "youtubeshorts", "shortsfeed", "shortvideo", "trend", "funny"}
HOOK_SYSTEM = ("You write short, honest YouTube Shorts / Instagram Reels titles for an oddly satisfying physics "
               "simulation channel. No clickbait lies, no ALL CAPS, at most one emoji. Return only JSON.")


def _views(rec: dict) -> int:
    return (rec.get("stats") or {}).get("views", 0)


def own_stats(cfg: dict, state: dict, limit: int = 72) -> list[dict]:
    """Refresh views/reach/likes/saves/shares of our latest Reels (stored in state)."""
    token = instagram.fresh_token(cfg)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    recs = [v for v in state.get("videos", []) if v.get("instagram_id")][-limit:]
    for rec in recs:
        r = requests.get(f"{instagram.GRAPH}/{rec['instagram_id']}/insights",
                         params={"metric": "views,reach,saved,shares", "access_token": token}, timeout=30)
        m = requests.get(f"{instagram.GRAPH}/{rec['instagram_id']}",
                         params={"fields": "like_count,comments_count", "access_token": token}, timeout=30)
        if r.ok and m.ok:
            rec["stats"] = {d["name"]: d["values"][0]["value"] for d in r.json().get("data", [])}
            rec["stats"].update(likes=m.json().get("like_count", 0), comments=m.json().get("comments_count", 0), at=now)
    return recs


def youtube_trends(token: str, days: int = 7) -> list[dict]:
    """Most viewed satisfying Shorts of the last days (kept in memory only)."""
    h = {"Authorization": f"Bearer {token}"}
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in QUERIES:
        r = requests.get(f"{YT}/search", headers=h, timeout=30, params={
            "part": "id", "q": q, "type": "video", "videoDuration": "short", "order": "viewCount",
            "publishedAfter": since, "maxResults": 25, "relevanceLanguage": "en", "safeSearch": "moderate"})
        if r.ok:
            ids += [i["id"]["videoId"] for i in r.json().get("items", []) if i["id"].get("videoId")]
    ids = list(dict.fromkeys(ids))
    out = []
    for k in range(0, len(ids), 50):
        r = requests.get(f"{YT}/videos", headers=h, timeout=30,
                         params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[k:k + 50])})
        for v in r.json().get("items", []) if r.ok else []:
            m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"].get("duration", ""))
            out.append({"text": (v["snippet"]["title"] + " " + " ".join(v["snippet"].get("tags", []))).casefold(),
                        "title": v["snippet"]["title"].casefold(), "tags": v["snippet"].get("tags", []),
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "seconds": (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0})
    return sorted(out, key=lambda v: -v["views"])


def _classify(text: str) -> list[str]:
    return [k for k, words in KIND_WORDS.items() if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)]


def run() -> dict:
    cfg, state = simchannel.load(simchannel.CONFIG, {}), simchannel.load(simchannel.STATE, {"videos": []})
    old = simchannel.load(simchannel.TUNING, {})
    kinds = [k for k in cfg["kinds"]]
    now = dt.datetime.now(dt.timezone.utc)

    # 1) our own Instagram numbers
    recs = own_stats(cfg, state) if instagram.configured(cfg) else []
    simchannel.save(simchannel.STATE, state)
    aged = [r for r in recs if r.get("stats") and now - dt.datetime.fromisoformat(r["date"]) > dt.timedelta(hours=6)]
    overall = statistics.median([_views(r) for r in aged]) if aged else 0
    perf, own_avg = {}, {}
    for k in kinds:
        vs = [_views(r) for r in aged if r["kind"] == k]
        own_avg[k] = round(sum(vs) / len(vs)) if vs else None
        perf[k] = min(2.0, max(0.5, (statistics.median(vs) / overall) ** 0.8)) if len(vs) >= 2 and overall else 1.0

    # 2) what goes viral on YouTube right now (aggregated only)
    token = simchannel._youtube_token(cfg)
    trend = youtube_trends(token) if token else []
    total = sum(v["views"] for v in trend) or 1
    share = {k: sum(v["views"] for v in trend if k in _classify(v["text"])) / total for k in kinds}
    words: Counter = Counter()
    for v in trend:
        toks = [t for t in re.findall(r"[a-z][a-z']+", v["title"]) if t not in STOP and len(t) > 2]
        for t in set(toks + [" ".join(p) for p in zip(toks, toks[1:])]):
            words[t] += math.log10(v["views"] + 10)
    tags: Counter = Counter()
    for v in trend:
        found = {t.casefold().replace(" ", "") for t in v["tags"]} | set(re.findall(r"#([a-z0-9]+)", v["title"]))
        for t in found:
            if re.fullmatch(r"[a-z0-9]{4,24}", t) and t not in JUNK_TAGS:
                tags[t] += 1
    secs = [v["seconds"] for v in trend[:40] if v["seconds"]]
    median_len = statistics.median(secs) if secs else 45
    ranges = ([(22, 32), (28, 40), (35, 48)] if median_len < 35 else
              [(35, 48), (42, 56)] if median_len > 48 else [(28, 40), (35, 48), (42, 56)])

    weights = {k: round(min(3.0, max(0.4, perf[k] * (1 + 2 * share[k]))), 2) for k in kinds}
    keywords = [w for w, _ in words.most_common(25)]
    hashtags = [t for t, n in tags.most_common(12) if n >= 2][:6] or old.get("hashtags", [])

    # 3) fresh title hooks and questions from the trend keywords (our own wording)
    hooks, questions, summary = old.get("title_hooks", []), old.get("questions", []), ""
    if generate.available() and keywords:
        try:
            best = sorted(aged, key=_views, reverse=True)[:5]
            res = generate.ask_json(
                "Keywords trending this week in viral satisfying-simulation Shorts (most important first):\n"
                + ", ".join(keywords) + "\n\nOur formats and how strongly each trends (0-1): "
                + ", ".join(f"{k} {share[k]:.2f}" for k in kinds)
                + "\nOur best Reels so far: " + "; ".join(f"{r['title']} ({_views(r)} views)" for r in best)
                + "\n\nWrite 10 new title templates for our videos. Each template must work for any of our formats, "
                  "so it must not name a specific shape or format (no rings, pendulums, plinko, colours, polygons) – "
                  "use the placeholder {onscreen} (the question shown in the video) for that – and may use {song} "
                  "(the melody), "
                  "max 70 characters. Also write 4 short questions that invite comments, and a 3-sentence summary "
                  "in German of what is working right now and how we adapt.\n"
                  'Return JSON: {"title_hooks": [...], "questions": [...], "summary_de": "..."}',
                max_tokens=1500, system=HOOK_SYSTEM)
            ok = []
            for t in res.get("title_hooks", []):
                t = str(t).strip()
                specific = re.search(r"\b(rings?|pendulums?|plinko|colou?rs?|polygons?|hexagons?|string|grows?)\b",
                                     t.replace("{onscreen}", ""), re.I)
                if 8 < len(t) <= 80 and "#" not in t and not specific and not re.search(r"\{(?!onscreen\}|song\})", t):
                    ok.append(t)
            hooks = ok[:10] or hooks
            questions = [str(q).strip() for q in res.get("questions", []) if 5 < len(str(q)) <= 90][:4] or questions
            summary = str(res.get("summary_de", ""))[:800]
        except Exception as err:
            print(f"  LLM step skipped: {err}", flush=True)

    tuning = {"updated": now.isoformat(timespec="minutes"), "kind_weights": weights, "ranges": ranges,
              "hashtags": hashtags, "title_hooks": hooks, "questions": questions, "trend_keywords": keywords[:15],
              "trend_share": {k: round(share[k], 3) for k in kinds}, "trend_videos": len(trend),
              "trend_median_seconds": median_len, "summary_de": summary}
    simchannel.save(simchannel.TUNING, tuning)
    report(tuning, state, own_avg)
    print(f"[trends] {len(trend)} trending Shorts, {len(aged)} own Reels; weights {weights}", flush=True)
    return tuning


def report(t: dict, state: dict, own_avg: dict) -> None:
    vids = [v for v in state.get("videos", []) if v.get("stats")]
    day = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)
    fresh = sorted([v for v in vids if dt.datetime.fromisoformat(v["date"]) > day], key=_views, reverse=True)[:3]
    lines = ["# Loop Physics – Trend-Check", "", f"Stand: {t['updated'][:16].replace('T', ' ')} UTC · "
             f"{t['trend_videos']} angesagte Satisfying-Shorts der letzten 7 Tage ausgewertet · "
             f"typische Länge {round(t['trend_median_seconds'])} s", ""]
    if t.get("summary_de"):
        lines += [t["summary_de"], ""]
    lines += ["## Formate: Gewichtung für die nächsten 24 Stunden", "",
              "| Format | Gewicht | Trend-Anteil | Ø Aufrufe bei uns |", "|---|---:|---:|---:|"]
    for k, w in sorted(t["kind_weights"].items(), key=lambda kv: -kv[1]):
        avg = own_avg.get(k)
        lines.append(f"| {k} | {w} | {round(100 * t['trend_share'].get(k, 0))} % | {avg if avg is not None else '–'} |")
    lines += ["", "## Angesagte Schlagwörter", "", ", ".join(t.get("trend_keywords") or ["–"]), "",
              "## Hashtags in den Captions", "", " ".join(f"#{h}" for h in ["satisfying"] + t.get("hashtags", [])[:3]), "",
              "## Neue Titel-Vorlagen", ""] + [f"- {h}" for h in t.get("title_hooks", [])] + [""]
    if fresh:
        lines += ["## Heute für YouTube empfohlen (beste Reels der letzten 30 Stunden)", ""]
        for v in fresh:
            lines.append(f"- **{v['title']}** – {_views(v)} Aufrufe auf Instagram · "
                         f"[Video & Texte]({v.get('release', '')}) · [Reel]({v.get('instagram_url', '')})")
        lines.append("")
    top = sorted(vids, key=_views, reverse=True)[:10]
    lines += ["## Unsere Top 10 Reels", "", "| Titel | Format | Aufrufe | Likes | Saves | Shares |", "|---|---|---:|---:|---:|---:|"]
    for v in top:
        s = v["stats"]
        lines.append(f"| [{v['title']}]({v.get('instagram_url', '')}) | {v['kind']} | {s.get('views', 0)} | "
                     f"{s.get('likes', 0)} | {s.get('saved', 0)} | {s.get('shares', 0)} |")
    (simchannel.ROOT / "docs" / "loop-physics-trends.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
