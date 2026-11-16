#!/usr/bin/env python3
"""Write examples/nrel-base-house.rtn.json from the reference sample house in the
validation snapshot (validation/houses/base.xml.gz)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "core"), str(ROOT / "validation")]
import compare  # noqa: E402
import hpxml_reader  # noqa: E402
from rightton import housefile  # noqa: E402

bldg = hpxml_reader.load(compare.HOUSES_DIR / "base.xml.gz", compare.EPW_DIR)
house = housefile.from_building(
    bldg, "NREL base house",
    "NREL's OpenStudio-HPXML sample house base.xml (a synthetic test building, not a real home): 2,700 ft2 on two "
    "levels with a conditioned basement, Denver weather, gas furnace and central air conditioner with ducts in an "
    "unvented attic. Converted from the reference engine's defaulted input, so every value is written out and "
    "RightTon's design loads for this file equal the reference engine's.")
house["project"]["created_with"] = "tools/convert_nrel_base.py"
house["location"]["weather_station_id"] = "725650"
house["location"]["weather_station_name"] = "Denver Intl Ap"
house["location"] = {k: house["location"][k] for k in ("weather_station_id", "weather_station_name", "design_conditions")}
housefile.save(house, ROOT / "examples" / "nrel-base-house.rtn.json")
