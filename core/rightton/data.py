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


def material_categories() -> dict[str, str]:
    """Material types in display order (id -> name). Materials are grouped by type, never by use."""
    return dict(_load("materials.json")["_categories"])


def materials_by_category() -> list[tuple[str, str, list[dict]]]:
    """(category id, category name, materials) in display order."""
    mats = list(materials().values())
    return [(cid, cname, [m for m in mats if m["category"] == cid]) for cid, cname in material_categories().items()]


def framing() -> dict:
    """Lumber sizes and typical framing factors (data/framing.json)."""
    return _load("framing.json")


def assembly_presets() -> list[dict]:
    """Ready-made assemblies (data/assembly_presets.json) the app copies into a house file."""
    return _load("assembly_presets.json")["presets"]


def glazing() -> dict[str, dict]:
    return {g["id"]: g for g in _load("glazing.json")["glazing"]}


def defaults() -> dict[str, dict]:
    return _load("defaults.json")["defaults"]


def weather_stations() -> dict[str, dict]:
    """Design summaries of weather stations, keyed by WMO station number (as text)."""
    return _load("weather_stations.json")["stations"]


def weather_stations_source() -> str:
    return _load("weather_stations.json")["_source"]


def input_ranges() -> dict[str, dict]:
    """Plausible low/high ranges by field name, for the input-confidence load range."""
    return _load("input_ranges.json")["rules"]
