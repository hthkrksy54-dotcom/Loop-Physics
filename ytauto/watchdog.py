"""GitHub drops or delays scheduled runs, sometimes by hours. Every Loop Physics run and every sync calls this and
starts whatever is overdue via workflow_dispatch, which GitHub runs right away – so the first scheduled run that
does start catches up the others, without a runner waiting anywhere."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BERLIN = ZoneInfo("Europe/Berlin")
DAILY_HOUR = 4  # Quiet Thoughts and Real Numbers make the day's video from 4:00 German time (summer and winter)


def _load(path: str, default):
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _today(iso: str | None, now: dt.datetime) -> bool:
    return bool(iso) and dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).date() == now.date()


def daily_slot(records: list[dict], now: dt.datetime | None = None, every_days: int = 1) -> str | None:
    """None when the day's video is due now, else why not. every_days = 2: a video every second day."""
    local = (now or dt.datetime.now(dt.timezone.utc)).astimezone(BERLIN)
    if local.hour < DAILY_HOUR:
        return f"too early ({local:%H:%M} German time – the day's video starts at {DAILY_HOUR}:00)"
    days = [(local.date() - dt.datetime.fromisoformat(r["date"]).astimezone(BERLIN).date()).days
            for r in records if r.get("date")]
    if any(d == 0 for d in days):
        return "today's video is already out"
    if any(0 < d < every_days for d in days):
        return f"one video every {every_days} days – the last one is only {min(d for d in days if d > 0)} day old"
    return None


def _overdue(records: list[dict], now: dt.datetime, every_days: int = 1) -> bool:
    """Due, and the scheduled run had time to start (GitHub delays or drops scheduled runs)."""
    local = now.astimezone(BERLIN)
    return daily_slot(records, now, every_days) is None and local.hour * 60 + local.minute >= (DAILY_HOUR + 1) * 60 + 30


def due(now: dt.datetime | None = None) -> list[tuple[str, dict]]:
    """(workflow file, dispatch inputs) for every job that should have run by now but hasn't."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hm = now.hour * 60 + now.minute
    out: list[tuple[str, dict]] = []

    from . import simchannel  # Loop Physics: a posting slot without its post
    if simchannel.slot_due(_load("state/sims.json", {}), now):
        out.append(("sims.yml", {"source": "watchdog"}))

    tuning = _load("config/sims_tuning.json", {})  # the trend check runs every second day
    if not tuning.get("updated") or now - dt.datetime.fromisoformat(tuning["updated"]) > dt.timedelta(hours=50):
        out.append(("trends.yml", {}))

    config = _load("config/channels.json", {})
    published = _load("state/published.json", {})
    for lang, cfg in config.items():
        if not cfg.get("active", True):
            continue
        recs = published.get(lang, [])
        if _overdue(recs, now, cfg.get("every_days", 1)):
            out.append(("produce.yml", {"langs": lang, "source": "watchdog"}))
        ig = cfg.get("instagram") or {}
        if ig.get("enabled"):
            if now.weekday() in (1, 3, 5) and hm >= 16 * 60 + 12 and \
                    not any(_today(r.get("carousel_date"), now) for r in recs):
                out.append(("carousel.yml", {}))
            stories = _load(ig.get("story_log", ""), []) if ig.get("story_log") else []
            if hm >= 18 * 60 + 41 and not any(_today(s.get("date"), now) for s in stories):
                out.append(("stories.yml", {}))
    econ = _load("state/econ.json", {}).get("videos", [])
    waiting = {p.stem for p in (ROOT / "content" / "econ" / "scripts").glob("*.json")} - {r["id"] for r in econ}
    if waiting and _overdue(econ, now) and _load("config/econ.json", {}).get("active", True):  # Real Numbers: one episode every day while the writer keeps up
        out.append(("econ.yml", {"source": "watchdog"}))
    return out
