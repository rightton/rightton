"""Access to RightTon's data files (materials, glazing presets, defaults, weather
stations, the house-file schema).

In the repository the files live in ``data/`` and ``schema/``. When the package is
bundled on its own (for the browser), they are copied into ``rightton/_data/``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PACKAGE_DATA = Path(__file__).resolve().parent / "_data"
_REPO = Path(__file__).resolve().parents[2]


def data_path(name: str) -> Path:
    for candidate in (_PACKAGE_DATA / name, _REPO / "data" / name, _REPO / "schema" / name):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"RightTon data file not found: {name}")


@lru_cache(maxsize=None)
def _load(name: str):
    return json.loads(data_path(name).read_text(encoding="utf-8"))


def schema() -> dict:
    return _load("rightton-house.schema.json")


def materials() -> dict[str, dict]:
    return {m["id"]: m for m in _load("materials.json")["materials"]}


def glazing() -> dict[str, dict]:
    return {g["id"]: g for g in _load("glazing.json")["glazing"]}


def defaults() -> dict[str, dict]:
    return _load("defaults.json")["defaults"]


def weather_stations() -> dict[str, dict]:
    """Design summaries of weather stations, keyed by WMO station number (as text)."""
    return _load("weather_stations.json")["stations"]


def weather_stations_source() -> str:
    return _load("weather_stations.json")["_source"]
