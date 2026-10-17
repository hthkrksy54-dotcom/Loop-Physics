"""GitHub drops or delays many scheduled runs. The Loop Physics timer (a run started by workflow_dispatch, which
GitHub executes reliably) calls this every ~2 hours and starts whatever is overdue."""
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


def daily_slot(records: list[dict], now: dt.datetime | None = None) -> str | None:
    """None when the day's video is due now, else why not. The schedules run at 2:03 and 3:03 UTC, so one of
    them is 4:03 in Germany in summer and in winter; the other one stops here."""
    local = (now or dt.datetime.now(dt.timezone.utc)).astimezone(BERLIN)
    if local.hour < DAILY_HOUR:
        return f"too early ({local:%H:%M} German time – the day's video starts at {DAILY_HOUR}:00)"
    if any(dt.datetime.fromisoformat(r["date"]).astimezone(BERLIN).date() == local.date() for r in records if r.get("date")):
        return "today's video is already out"
    return None


def _overdue(records: list[dict], now: dt.datetime) -> bool:
    """Due, and the scheduled run had half an hour to start (GitHub delays or drops scheduled runs)."""
    local = now.astimezone(BERLIN)
    return daily_slot(records, now) is None and local.hour * 60 + local.minute >= DAILY_HOUR * 60 + 30


def due(now: dt.datetime | None = None) -> list[tuple[str, dict]]:
    """(workflow file, dispatch inputs) for every job that should have run by now but hasn't."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hm = now.hour * 60 + now.minute
    out: list[tuple[str, dict]] = [("sync.yml", {})]  # cheap and idempotent: always

    tuning = _load("config/sims_tuning.json", {})
    if not tuning.get("updated") or now - dt.datetime.fromisoformat(tuning["updated"]) > dt.timedelta(hours=24):
        out.append(("trends.yml", {}))

    config = _load("config/channels.json", {})
    published = _load("state/published.json", {})
    for lang, cfg in config.items():
        if not cfg.get("active", True):
            continue
        recs = published.get(lang, [])
        if _overdue(recs, now):  # one video every day
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
    if waiting and _overdue(econ, now):  # Real Numbers: one episode every day while the writer keeps up
        out.append(("econ.yml", {"source": "watchdog"}))
    return out
