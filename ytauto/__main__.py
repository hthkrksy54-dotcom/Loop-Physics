"""Command line entry point.

  python -m ytauto run --langs de en           pick next topic, write/load script, render, publish
  python -m ytauto run --langs de --no-upload  same, but keep files locally (out/)
  python -m ytauto render --lang en --topic hedonic-treadmill   render only (preview)
  python -m ytauto check                       test voice, script AI and YouTube connection
  python -m ytauto sync                        match manual YouTube uploads, post Instagram Reels
  python -m ytauto carousel                    post the next Instagram quote carousel
  python -m ytauto story                       daily Instagram story (quote / Sunday recap)
  python -m ytauto highlights                  which recent stories go into which highlight
  python -m ytauto sim --kind escape           render a satisfying physics simulation Short
  python -m ytauto sims                        Loop Physics channel: render + publish the next simulation
  python -m ytauto concepts                    Loop Physics: all concepts, the queue and what performs
  python -m ytauto concept-check KIND [--full] Loop Physics: quality gate for a (new) concept
  python -m ytauto trends                      Loop Physics: daily trend check and tuning
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

from . import check, generate, instagram, publish, render, simchannel, sims, social, sync, tiktok, trends, watchdog, youtube

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "channels.json"
TOPICS = ROOT / "content" / "topics.json"
SCRIPTS = ROOT / "content" / "scripts"
STATE = ROOT / "state" / "published.json"
OUT = ROOT / "out"
TIKTOK_QUEUE = ROOT / "state" / "tiktok_quiet.md"


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_topic(lang: str, state: dict, topics: list[dict]) -> dict:
    done = {e["id"] for e in state.get(lang, [])}
    can_write = generate.available()
    for t in topics:
        if t["id"] in done:
            continue
        if can_write or (SCRIPTS / lang / f"{t['id']}.json").exists():
            return t
    if not can_write:
        raise RuntimeError(
            "No finished script left and no LLM key configured. Add the free GEMINI_API_KEY secret (see SETUP.md)."
        )
    print("Topic backlog empty – asking the LLM for new topics", flush=True)
    new = generate.propose_topics(topics)
    if not new:
        raise RuntimeError("no new topics available")
    topics.extend(new)
    _save(TOPICS, topics)
    return new[0]


def load_or_write_script(topic: dict, lang: str) -> dict:
    path = SCRIPTS / lang / f"{topic['id']}.json"
    if path.exists():
        return _load(path, None)
    print(f"Writing new {lang} script for '{topic['id']}' with LLM", flush=True)
    example = next(iter(sorted((SCRIPTS / lang).glob("*.json"))), None)
    script = generate.generate_script(topic, lang, _load(example, None) if example else None)
    _save(path, script)
    return script


def produce(lang: str, topic_id: str | None, upload: bool, with_short: bool, keep_record: bool = True) -> dict:
    cfg = _load(CONFIG, {})[lang]
    topics = _load(TOPICS, [])
    state = _load(STATE, {})
    topic = next((t for t in topics if t["id"] == topic_id), None) if topic_id else next_topic(lang, state, topics)
    if topic is None:
        raise SystemExit(f"unknown topic {topic_id}")
    script = load_or_write_script(topic, lang)
    print(f"[{lang}] {script['title']}", flush=True)

    outdir = OUT / lang / script["id"]
    long = render.render_long(script, cfg, outdir)
    print(f"  long video: {long['duration'] / 60:.1f} min", flush=True)
    short = render.render_short(script, cfg, outdir) if with_short else None
    long["cover"] = social.reel_cover(outdir / "cover.jpg", script, cfg)  # vertical cover for the Instagram Reel

    record = {
        "id": script["id"],
        "title": script["title"],
        "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "duration_min": round(long["duration"] / 60, 1),
    }
    if upload:
        connected = youtube.configured(cfg["youtube"]["refresh_token_secret"])
        if connected and cfg["youtube"].get("upload_enabled"):
            record.update(publish.to_youtube(script, cfg, long, short))
        else:
            reason = "upload paused until the API audit is approved" if connected else "YouTube not connected yet"
            print(f"  YouTube: {reason} – files are in the GitHub release", flush=True)
        # Every video is archived as a release; its public Short URL also feeds Instagram.
        release = publish.to_github_release(script, cfg, long, short)
        short_url = release.pop("short_url", None)
        record.update(release)
        if short_url:
            record["short_url"] = short_url
        # The Reel goes out in the US morning (reel_hour) – the hourly sync posts it then, with a link to the
        # video if it is on YouTube by then; made during US daytime, it goes out right away.
        due = instagram.reel_due(cfg)
        if short and short_url and instagram.configured(cfg) and due:
            record["reel_due"] = due.isoformat(timespec="seconds")
            print(f"  instagram: Reel scheduled for {due:%H:%M} UTC", flush=True)
        elif short and short_url and instagram.configured(cfg):
            try:
                yt_url = f"https://youtu.be/{record['youtube_id']}" if record.get("youtube_id") else None
                record.update(instagram.post_reel(cfg, short_url, instagram.caption(script, cfg, yt_url),
                                                  highlight=social.highlight_for(script), label=script["short"]["title"],
                                                  cover_url=record.get("cover_url")))
            except Exception as err:  # Instagram must never block the YouTube side
                record.setdefault("warnings", []).append(f"instagram: {err}")
                print(f"  warning: instagram reel failed: {err}", flush=True)
        # Together with the Reel: the Short as a draft in the TikTok inbox (the owner posts it with one tap);
        # a full inbox waits for the hourly sync.
        if short and tiktok.configured(cfg) and tiktok.waiting(_load(STATE, {}).get(lang, [])) < tiktok.MAX_WAITING:
            try:
                record["tiktok"] = {**tiktok.send_draft(cfg, Path(short["video"])), "caption": tiktok_caption(script, cfg)}
            except Exception as err:  # noqa: BLE001
                record.setdefault("warnings", []).append(f"tiktok: {err}")
                print(f"  warning: tiktok failed: {err}", flush=True)
        if keep_record:
            state = _load(STATE, {})
            state.setdefault(lang, []).append(record)
            _save(STATE, state)
            if record.get("tiktok"):
                tiktok.write_queue(state[lang], cfg["channel_name"], TIKTOK_QUEUE, ai_voice=True)
    return record


def post_due_reels(lang: str, cfg: dict, state: dict) -> bool:
    """Post the Reels whose time has come (see instagram.reel_due); returns True if state changed."""
    changed = False
    for rec in state.get(lang, []):
        if not rec.get("reel_due") or rec.get("instagram_id") or instagram.reel_waiting(rec) \
                or rec.get("reel_tries", 0) >= 3 or not rec.get("short_url"):
            continue
        script = _load(SCRIPTS / lang / f"{rec['id']}.json", None)
        if not script:
            continue
        try:
            yt_url = f"https://youtu.be/{rec['youtube_id']}" if rec.get("youtube_id") else None
            rec.update(instagram.post_reel(cfg, rec["short_url"], instagram.caption(script, cfg, yt_url),
                                           highlight=social.highlight_for(script), label=script["short"]["title"],
                                           cover_url=rec.get("cover_url")))
        except Exception as err:  # noqa: BLE001 – tried again next hour, three times at most
            rec["reel_tries"] = rec.get("reel_tries", 0) + 1
            rec.setdefault("warnings", []).append(f"instagram: {err}")
            print(f"  warning: instagram reel for '{rec['id']}' failed: {err}", flush=True)
        changed = True
    return changed


def tiktok_caption(script: dict, cfg: dict) -> str:
    """TikTok text made for this video: the hook on screen, what the essay is about, its question for the
    comments, where the full essay is, a few tags (no links: TikTok drops them)."""
    short = script["short"]
    tags: dict[str, str] = {}
    for t in f"{script.get('hashtags', '')} {cfg['tiktok'].get('hashtags', '')}".split():
        tags.setdefault(t.lower(), t if t.startswith("#") else f"#{t}")
    where = f"Full video essay on YouTube: {cfg['channel_name']} ({cfg['tiktok'].get('youtube', '')})".replace(" ()", "")
    question = script.get("question") or tiktok.question_from(short.get("text", ""))
    lines = [short.get("hook") or short["title"].replace("#Shorts", "").strip(), tiktok.lead(script["description"]),
             f"💬 {question}" if question else "", where, " ".join(list(tags.values())[:5])]
    return "\n".join(x for x in lines if x)


def tiktok_backlog(lang: str, cfg: dict, max_pending: int = tiktok.MAX_WAITING) -> bool:
    """Which drafts the owner posted meanwhile, then recent Shorts not on TikTok yet (newest first)."""
    state = _load(STATE, {})
    records = state.get(lang, [])
    changed = tiktok.refresh(cfg, records)
    now = dt.datetime.now(dt.timezone.utc)
    todo = []
    for rec in sorted(records, key=lambda r: r["date"], reverse=True):
        # older records have no short_url, but their release holds the Short under a fixed name
        url = rec.get("short_url") or (rec.get("release") and f"{rec['release'].replace('/releases/tag/', '/releases/download/')}"
                                                             f"/{lang}-{rec['id']}-short.mp4")
        if rec.get("tiktok") or rec.get("tiktok_skip") or not url \
                or now - dt.datetime.fromisoformat(rec["date"]) > dt.timedelta(days=14):
            continue
        script = _load(SCRIPTS / lang / f"{rec['id']}.json", None)
        if script and script.get("short"):
            todo.append((rec, url, tiktok_caption(script, cfg)))
    changed |= tiktok.backlog(cfg, todo, records, max_pending) > 0
    if changed:
        _save(STATE, state)
        tiktok.write_queue(records, cfg["channel_name"], TIKTOK_QUEUE, ai_voice=True)
    return changed


def post_carousel(lang: str, cfg: dict, render_only: bool = False) -> bool:
    """Post a quote carousel for the oldest published video that has none yet (live on YouTube first)."""
    state = _load(STATE, {})
    now = dt.datetime.now(dt.timezone.utc)
    last = max((dt.datetime.fromisoformat(r["carousel_date"]) for r in state.get(lang, []) if r.get("carousel_date")), default=None)
    if last and now - last < dt.timedelta(hours=30) and not render_only:
        print(f"[{lang}] a carousel already went out at {last:%Y-%m-%d %H:%M} UTC – skipping", flush=True)
        return False
    records = [r for r in state.get(lang, []) if not r.get("carousel_id")]
    records.sort(key=lambda r: not r.get("youtube_id"))  # stable: oldest video with a YouTube link first
    for rec in records:
        path = SCRIPTS / lang / f"{rec['id']}.json"
        script = _load(path, None)
        if script is None:
            continue
        if not script.get("carousel"):
            if not generate.available():
                continue
            try:
                script.update(generate.social_extras(script))
                _save(path, script)
            except Exception as err:
                print(f"[{lang}] no carousel for '{rec['id']}': {err}", flush=True)
                continue
        outdir = OUT / lang / script["id"] / "carousel"
        slides = social.carousel(script, cfg, outdir)
        print(f"[{lang}] carousel '{rec['id']}': {len(slides)} slides in {outdir}", flush=True)
        if render_only:
            return False
        images = list(slides)
        quote = social.best_quote(script)
        if quote:  # the same day a quote card goes to Stories (feeds the "Quotes" highlight)
            images.append(social.quote_story(outdir / "story_quote.jpg", quote["text"], quote["author"],
                                             render.seed_for(script), "@" + cfg["instagram"].get("account", "")))
        tag = f"carousel-{lang}-{script['id']}"
        rel = publish.github_release(
            tag, f"[{lang.upper()}] Carousel – {script['carousel']['cover']}",
            f"Instagram carousel for “{script['title']}”.",
            [(p, f"{tag}-{p.stem}.jpg", "image/jpeg") for p in images],
        )
        urls = {p: rel.get("assets", {}).get(f"{tag}-{p.stem}.jpg") for p in images}
        if not all(urls[p] for p in slides):
            raise RuntimeError("carousel images could not be published as release assets")
        yt = f"https://youtu.be/{rec['youtube_id']}" if rec.get("youtube_id") else None
        rec.update(instagram.post_carousel(cfg, [urls[p] for p in slides], instagram.carousel_caption(script, cfg, yt)))
        rec["carousel_date"] = now.isoformat(timespec="seconds")
        _save(STATE, state)
        if quote and urls.get(images[-1]):
            try:
                rec["quote_story_id"] = instagram.post_story(cfg, image_url=urls[images[-1]], kind="quote", highlight="Quotes",
                                                             label=f"{quote['author']}: {quote['text'][:60]}")
                _save(STATE, state)
            except Exception as err:
                print(f"  warning: quote story failed: {err}", flush=True)
        return True
    print(f"[{lang}] no video left without a carousel", flush=True)
    return False


def daily_story(lang: str, cfg: dict, force: bool = False) -> bool:
    """Keep a fresh story up every day: Sunday a weekly recap, otherwise a quote – unless a Reel or
    carousel story already went out in the last 20 hours."""
    now = dt.datetime.now(dt.timezone.utc)
    sunday = now.weekday() == 6
    if not (force or sunday):
        fresh = [s for s in instagram.live_stories(cfg)
                 if now - dt.datetime.strptime(s["timestamp"], "%Y-%m-%dT%H:%M:%S%z") < dt.timedelta(hours=20)]
        if fresh:
            print(f"[{lang}] {len(fresh)} fresh stor{'y' if len(fresh) == 1 else 'ies'} already up – nothing to do", flush=True)
            return False
    state = _load(STATE, {})
    records = state.get(lang, [])
    scripts = {r["id"]: _load(SCRIPTS / lang / f"{r['id']}.json", None) for r in records}
    live = [r for r in records if r.get("youtube_id") and scripts.get(r["id"])]
    outdir = OUT / lang / "stories"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%d")
    week = [r for r in live if now - dt.datetime.fromisoformat(r["date"]) < dt.timedelta(days=8)]

    if sunday and week:
        path = social.story_card(
            outdir / f"{stamp}-week.jpg", "This week", cfg["channel_name"],
            [scripts[r["id"]]["title_card"] for r in week] + ["Full video essays on YouTube – link in bio"],
            seed=now.isocalendar()[1],
        )
        kind, highlight, label = "recap", None, f"week {now:%G-W%V}: {len(week)} videos"
    else:
        pool = social.quote_pool([scripts[r["id"]] for r in live] or [s for s in scripts.values() if s])
        if not pool:
            print(f"[{lang}] no quotes available for a story", flush=True)
            return False
        used = {}
        for i, e in enumerate(instagram.story_log(cfg)):
            if e.get("kind") == "quote":
                used[e.get("label", "")] = i
        key = lambda q: f"{q['author']}: {q['text'][:60]}"
        quote = min(pool, key=lambda q: used.get(key(q), -1))  # unused first, then the longest-ago one
        path = social.quote_story(outdir / f"{stamp}-quote.jpg", quote["text"], quote["author"],
                                  render.seed_for(quote["script"]) + now.toordinal(), "@" + cfg["instagram"].get("account", ""))
        kind, highlight, label = "quote", "Quotes", key(quote)

    url = publish.release_asset(f"stories-{lang}", f"[{lang.upper()}] Instagram stories", path,
                                f"story-{lang}-{path.name}", "image/jpeg")
    if not url:
        raise RuntimeError("story image could not be published as a release asset")
    instagram.post_story(cfg, image_url=url, kind=kind, highlight=highlight, label=label)
    return True


def highlight_list(cfg: dict, days: int = 7) -> list[str]:
    """Stories of the last days, grouped by the highlight they belong in (for the owner to file)."""
    now = dt.datetime.now(dt.timezone.utc)
    groups: dict[str, list[str]] = {}
    for e in instagram.story_log(cfg):
        if e.get("highlight") and now - dt.datetime.fromisoformat(e["date"]) < dt.timedelta(days=days):
            day = dt.datetime.fromisoformat(e["date"]).strftime("%a %d.%m.")
            groups.setdefault(e["highlight"], []).append(f"{day} {e['kind']}: {e.get('label', '')}")
    return [f"{h}: " + " | ".join(items) for h, items in groups.items()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ytauto")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--langs", nargs="+", default=["de", "en"])
    run.add_argument("--topic")
    run.add_argument("--no-upload", action="store_true")
    run.add_argument("--no-short", action="store_true")
    run.add_argument("--no-record", action="store_true", help="test run: publish but don't mark the topic as done")
    ren = sub.add_parser("render")
    ren.add_argument("--lang", required=True)
    ren.add_argument("--topic", required=True)
    ren.add_argument("--no-short", action="store_true")
    sub.add_parser("check")
    sub.add_parser("stats", help="views, followers, likes and comments of all channels, per account and in total")
    sub.add_parser("sync", help="match manual YouTube uploads, fix Shorts, post Instagram Reels")
    car = sub.add_parser("carousel", help="post the next Instagram quote carousel")
    car.add_argument("--render-only", action="store_true")
    sto = sub.add_parser("story", help="daily Instagram story (quote, or Sunday weekly recap)")
    sto.add_argument("--force", action="store_true", help="post even if a fresh story is already up")
    sm = sub.add_parser("sim", help="render a satisfying physics simulation (vertical, with generated melody)")
    sm.add_argument("--kind", choices=sorted(sims.KINDS), default="escape")
    sm.add_argument("--seed", type=int, help="fixed seed; default: first seed after --start with a 35-55 s run")
    sm.add_argument("--start", type=int, default=0)
    sm.add_argument("--melody", choices=sorted(sims.MELODIES))
    sm.add_argument("--handle", default="")
    sc = sub.add_parser("sims", help="Loop Physics channel: render and publish the next simulation Short")
    sc.add_argument("--no-upload", action="store_true")
    sc.add_argument("--branding", action="store_true", help="set banner, description and keywords on YouTube")
    sc.add_argument("--youtube", choices=["check", "apply", "describe", "demo"],
                    help="match manual YouTube uploads and polish them; describe = newest 4 get the current description")
    sc.add_argument("--due", action="store_true", help="print 'post' if a posting slot is open, else 'idle'")
    sc.add_argument("--reels", nargs="?", const=0, type=int, metavar="N",
                    help="post the videos whose Instagram Reel failed, now (N = at most N of them, oldest first)")
    tk = sub.add_parser("tiktok", help="TikTok setup: url | connect | check | send | backlog (--channel econ / quiet)")
    tk.add_argument("action", choices=["url", "connect", "check", "send", "refresh", "backlog"])
    tk.add_argument("--channel", choices=["sims", "econ", "quiet"], default="sims")
    tk.add_argument("--max", type=int, help="backlog: at most this many drafts waiting in the inbox "
                                            "(default: 3 for Loop Physics, 5 for the others)")
    tk.add_argument("--files", help="backlog: folder with <kind>-<seed>.mp4 files to use instead of releases")
    tk.add_argument("--key", help="client key of the TikTok developer app")
    tk.add_argument("--secret", help="client secret of the TikTok developer app")
    tk.add_argument("--redirect", help="the full address TikTok sent you to after allowing access")
    tk.add_argument("--video", help="send: this MP4 as a draft")
    ec = sub.add_parser("econ", help="Real Numbers: check | render | produce | queue | reel | banner | branding")
    ec.add_argument("action", choices=["check", "render", "produce", "queue", "reel", "banner", "branding"])
    ec.add_argument("script", nargs="*", help="script ids (default: next in the queue)")
    ec.add_argument("--no-upload", action="store_true")
    ec.add_argument("--short-only", action="store_true")
    ec.add_argument("--all", action="store_true", help="reel: catch up every missing Reel now, not one a day")
    ic = sub.add_parser("instagram-connect", help="store a new Instagram token for a channel (encrypted)")
    ic.add_argument("--channel", choices=["quiet", "sims", "econ"], required=True)
    ic.add_argument("--token", required=True)
    sub.add_parser("concepts", help="Loop Physics: every concept with status, queue and performance")
    sub.add_parser("melodies", help="Loop Physics: every melody with its views, trend signal, boost and weight")
    cc = sub.add_parser("concept-check", help="Loop Physics: quality gate + contact sheet for a concept")
    cc.add_argument("kind", nargs="?")
    cc.add_argument("--full", action="store_true", help="also render the whole video and check its loudness")
    cc.add_argument("--all", action="store_true", help="quick check of every kind (after changing shared code)")
    sub.add_parser("trends", help="Loop Physics: daily trend check, writes config/sims_tuning.json")
    sub.add_parser("watchdog", help="print overdue workflows as JSON lines (file, inputs)")
    hl = sub.add_parser("highlights", help="list recent stories by the highlight they belong in")
    hl.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return check.run(_load(CONFIG, {}))
    if args.cmd == "stats":
        from . import stats
        return stats.run()
    if args.cmd == "sync":
        config, state = _load(CONFIG, {}), _load(STATE, {})
        changed = False
        for lang, cfg in config.items():
            if cfg.get("active", True):
                changed |= sync.run(lang, cfg, state, lambda tid, lang=lang: _load(SCRIPTS / lang / f"{tid}.json", None))
                if instagram.configured(cfg):
                    changed |= post_due_reels(lang, cfg, state)
            elif instagram.configured(cfg):  # paused: nothing is posted, but the token stays valid for a restart
                try:
                    instagram.fresh_token(cfg)
                except Exception as err:  # noqa: BLE001 – tried again next run
                    print(f"[{lang}] instagram token refresh failed: {err}", flush=True)
        if changed:
            _save(STATE, state)
        from . import econ
        econ.youtube_sync()  # Real Numbers: finish the episodes the owner uploaded by hand
        econ.post_due_reel()
        from . import imprint
        imprint.run()  # the Impressum link stays in every channel description
        return 0

    if args.cmd == "carousel":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and (args.render_only or instagram.configured(cfg)):
                post_carousel(lang, cfg, render_only=args.render_only)
        return 0

    if args.cmd == "sim":
        seed = args.seed if args.seed is not None else sims.pick_seed(args.kind, args.start)
        result = sims.render(args.kind, seed, OUT / "sims" / f"{args.kind}-{seed}.mp4", args.melody, args.handle)
        print(f"{result['video']}  ({result['duration']:.1f}s, {result['melody_name']})")
        return 0

    if args.cmd == "instagram-connect":
        if args.channel == "econ":
            from . import econ
            cfg = econ.load(econ.CONFIG, {})
        elif args.channel == "sims":
            cfg = simchannel.load(simchannel.CONFIG, {})
        else:
            cfg = _load(CONFIG, {})["en"]
        print(instagram.connect(cfg, args.token))
        return 0
    if args.cmd == "econ":
        from . import econ
        if args.action == "check":
            ids = args.script or [p.stem for p in sorted(econ.SCRIPTS.glob("*.json"))]
            return 0 if all([econ.check(i) for i in ids]) else 1
        if args.action == "queue":
            state = econ.load(econ.STATE, {"videos": []})
            q = econ.queue(state)
            print(f"{len(q)} scripts waiting: " + ", ".join(q))
        elif args.action == "banner":  # draw assets/brand/real-numbers-banner.png
            print(econ.banner())
        elif args.action == "branding":  # draw it and set it on the YouTube channel
            econ.branding()
        elif args.action == "reel":  # one missing Reel a day (episodes from before Instagram was connected)
            while econ.backfill_reel(every_day=not args.all) and args.all:
                pass
        elif args.action == "render":
            print(econ.render_script((args.script or econ.queue(econ.load(econ.STATE, {})))[0], args.short_only))
        else:
            for script_id in args.script or [None]:  # several ids: one after the other in this run
                econ.produce(upload=not args.no_upload, script_id=script_id)
        return 0
    if args.cmd == "tiktok":
        from . import econ
        cfg = simchannel.load(simchannel.CONFIG, {})
        app = tiktok._load(cfg) if tiktok._path(cfg).exists() and os.environ.get("IG_TOKEN_KEY") else {}
        key, secret = args.key or app.get("client_key"), args.secret or app.get("client_secret")  # same app
        channels = {"sims": cfg, "econ": econ.load(econ.CONFIG, {}), "quiet": _load(CONFIG, {})["en"]}
        cfg = channels[args.channel]
        if args.action == "url":
            print(tiktok.auth_url(key, state=args.channel))
        elif args.action == "connect":
            taken = {tiktok.open_id(c) for name, c in channels.items() if name != args.channel and c.get("tiktok")}
            data = tiktok.connect(cfg, key, secret, args.redirect, channel=args.channel, taken=taken - {None})
            print(f"connected (scopes: {data.get('scope')}), token stored in {cfg['tiktok']['token_file']}")
        elif args.action == "check":
            print(f"TikTok account: {tiktok.account(cfg).get('display_name')}")
        elif args.action in ("refresh", "backlog") and args.channel == "econ":
            econ.tiktok_backlog(args.max or tiktok.MAX_WAITING)
        elif args.action in ("refresh", "backlog") and args.channel == "quiet":
            if cfg.get("active", True) and tiktok.configured(cfg):
                tiktok_backlog("en", cfg, args.max or tiktok.MAX_WAITING)
        elif args.action in ("refresh", "backlog"):  # heartbeat: what was posted, then top up the drafts
            state = simchannel.load(simchannel.STATE, {"videos": []})
            if not tiktok.configured(cfg):
                return 0
            changed = tiktok.refresh(cfg, state["videos"])
            files = {p.stem: p for p in Path(args.files).glob("*.mp4")} if args.files else None
            changed |= simchannel.tiktok_backlog(cfg, state, args.max or simchannel.TIKTOK_PENDING, files) > 0
            if changed:
                simchannel.save(simchannel.STATE, state)
                tiktok.write_queue(state["videos"], cfg["channel_name"], tips=simchannel.sound_tips())
                print("tiktok: drafts and statuses updated")
        else:
            print(tiktok.send_draft(cfg, Path(args.video)))
        return 0
    if args.cmd == "melodies":
        mw = simchannel.melody_weights(simchannel.load(simchannel.STATE, {}))
        total = sum(v["weight"] for v in mw.values()) or 1
        print(f"{'melody':16} {'posts':>5} {'lift':>5} {'trend':>6} {'boost':>5} {'recent':>6} {'chance':>7}")
        for m, v in sorted(mw.items(), key=lambda x: -x[1]["weight"]):
            print(f"{m:16} {v['posts']:>5} {v['lift']:>5} {v['trend']:>6.3f} {v['boost']:>5} {v['recent']:>6} "
                  f"{100 * v['weight'] / total:>6.1f}%")
        return 0
    if args.cmd == "concepts":
        from . import conceptcheck
        print(conceptcheck.listing(simchannel.load(simchannel.CONFIG, {}), simchannel.load(simchannel.STATE, {})))
        return 0
    if args.cmd == "concept-check":
        from . import conceptcheck
        kinds = list(sims.KINDS) if args.all else [args.kind]
        if not kinds or not kinds[0]:
            ap.error("concept-check needs a kind or --all")
        ok = [conceptcheck.check(k, full=args.full and not args.all) for k in kinds]
        return 0 if all(ok) else 1

    if args.cmd == "sims":
        if args.due:
            manual = not simchannel.planned_run()
            print("post" if manual or simchannel.slot_due(simchannel.load(simchannel.STATE, {})) else "idle")
        elif args.reels is not None:
            simchannel.backfill_reels(args.reels or None)
        elif args.branding:
            simchannel.branding()
        elif args.youtube:
            if args.youtube == "describe":
                simchannel.youtube_describe()
            elif args.youtube == "demo":
                simchannel.youtube_demo()
            else:
                simchannel.youtube_polish(apply=args.youtube == "apply")
        else:
            simchannel.run(upload=not args.no_upload)
        return 0

    if args.cmd == "watchdog":
        for wf, inputs in watchdog.due():
            print(json.dumps({"workflow": wf, "inputs": inputs}))
        return 0

    if args.cmd == "trends":
        trends.run()
        return 0

    if args.cmd == "highlights":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and cfg.get("instagram", {}).get("enabled"):
                print("\n".join(highlight_list(cfg, args.days)) or f"[{lang}] no new stories")
        return 0

    if args.cmd == "story":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and instagram.configured(cfg):
                daily_story(lang, cfg, force=args.force)
        return 0

    if args.cmd == "render":
        produce(args.lang, args.topic, upload=False, with_short=not args.no_short)
        return 0

    failed = []
    config = _load(CONFIG, {})
    unattended = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("IN_SOURCE") == "watchdog"
    for lang in args.langs:
        why_not = watchdog.daily_slot(_load(STATE, {}).get(lang, []), None,
                                      config.get(lang, {}).get("every_days", 1)) if unattended else None
        if why_not:
            print(f"[{lang}] {why_not} – skipping", flush=True)
            continue
        if not config.get(lang, {}).get("active", True):
            print(f"[{lang}] paused (\"active\": false in config/channels.json) – skipping", flush=True)
            continue
        try:
            produce(lang, args.topic, upload=not args.no_upload, with_short=not args.no_short, keep_record=not args.no_record)
        except Exception:
            traceback.print_exc()
            failed.append(lang)
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
