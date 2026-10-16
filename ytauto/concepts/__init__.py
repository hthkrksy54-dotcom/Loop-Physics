"""Designed Loop Physics concepts – one module per concept (ytauto/concepts/<kind>.py).

The concept designer (a scheduled Claude session, see docs/concept-designer.md) adds a new module twice a day.
Each module defines one `sims.Sim` subclass with a unique `kind` and a `concept` dict; it is picked up here
automatically. A module that fails to import is skipped (and listed in BROKEN), so one bad concept can never stop
the channel.
"""
from __future__ import annotations

import importlib
import pkgutil
import traceback

BROKEN: dict[str, str] = {}


def discover() -> dict[str, type]:
    from .. import sims

    found: dict[str, type] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{info.name}")
            for obj in vars(mod).values():
                if isinstance(obj, type) and issubclass(obj, sims.Sim) and obj.__module__ == mod.__name__ \
                        and obj.kind and obj.concept:
                    found[obj.kind] = obj
        except Exception:  # noqa: BLE001 – a broken concept must not take the others down
            BROKEN[info.name] = traceback.format_exc(limit=4)
    return found
