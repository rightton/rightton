# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (process_load_doors,
# process_load_walls, process_load_roofs, process_load_ceilings,
# process_load_floors, get_ashrae_wall_group).
"""Opaque envelope: cooling load temperature differences (CLTD) and partition
temperature differences. A surface load is always U x area x temperature difference."""

from __future__ import annotations

from . import tables as T

# Table 4A wall-group thresholds: (max U-factor, group letter); the last letter
# applies above every threshold.
# origin: OS-HPXML get_ashrae_wall_group ("Correlations are estimated by analyzing
# the construction tables" of MJ8 Table 4A)
_WOOD_STUD_MASONRY_VENEER = ((0.070, "K"), (0.083, "J"), (0.095, "I"), (0.100, "H"), (0.130, "G"), (0.175, "F")), "E"
_WOOD_STUD = ((0.048, "J"), (0.051, "I"), (0.059, "H"), (0.063, "G"), (0.067, "F"), (0.075, "E"),
              (0.086, "D"), (0.110, "C"), (0.170, "B")), "A"
_STEEL_STUD_MASONRY_VENEER = ((0.090, "K"), (0.105, "J"), (0.118, "I"), (0.125, "H"), (0.145, "G"), (0.200, "F")), "E"
_STEEL_STUD = ((0.066, "J"), (0.070, "I"), (0.075, "H"), (0.081, "G"), (0.088, "F"), (0.100, "E"),
               (0.105, "D"), (0.120, "C"), (0.200, "B")), "A"
_CMU = ((0.0575, "J"), (0.067, "I"), (0.080, "H"), (0.108, "G"), (0.148, "F")), "E"
# "U at or above" thresholds: (min U-factor, group letter); last letter below all.
_MASONRY = (((0.218 + 0.179) / 2, "G"), ((0.152 + 0.132) / 2, "H"), ((0.117 + 0.079) / 2, "I"), (0.079, "J")), "K"
_LOG = (((0.103 + 0.091) / 2, "G"), ((0.091 + 0.082) / 2, "H"), ((0.074 + 0.068) / 2, "I"),
        ((0.068 + 0.063) / 2, "J")), "K"
_FND_BLOCK_OPEN = (((0.269 + 0.175) / 2, "E"), ((0.175 + 0.130) / 2, "F"), ((0.103 + 0.085) / 2, "G"),
                   ((0.085 + 0.060) / 2, "H"), ((0.060 + 0.046) / 2, "J")), "K"
_FND_BLOCK_FILLED = (((0.188 + 0.137) / 2, "E"), ((0.137 + 0.107) / 2, "F"), ((0.088 + 0.075) / 2, "G"),
                     ((0.075 + 0.055) / 2, "H"), ((0.055 + 0.043) / 2, "J")), "K"
_FND_CONCRETE_4IN = (((0.308 + 0.190) / 2, "E"), ((0.190 + 0.138) / 2, "F"), ((0.108 + 0.089) / 2, "G"),
                     ((0.089 + 0.062) / 2, "H"), ((0.062 + 0.047) / 2, "J")), "K"
_FND_MASONRY_8IN = (((0.247 + 0.165) / 2, "G"), ((0.165 + 0.124) / 2, "H"), ((0.100 + 0.083) / 2, "I"),
                    ((0.083 + 0.059) / 2, "J")), "K"
_FND_WOOD = (((0.106 + 0.098) / 2, "J"),), "K"


def _at_most(table, u: float) -> str:
    rows, last = table
    for limit, group in rows:
        if u <= limit:
            return group
    return last


def _at_least(table, u: float) -> str:
    rows, last = table
    for limit, group in rows:
        if u >= limit:
            return group
    return last


def wall_group(wall_type: str, siding: str, u_factor: float) -> str:
    """ASHRAE wall group ("B" heaviest .. "G" lightest) for an above-grade wall.

    Source: get_ashrae_wall_group. Heavier, better insulated walls delay and
    damp the solar gain, which lowers the cooling temperature difference.
    """
    veneer = siding in ("brick", "stone")
    if wall_type == "wood_stud":
        letter = _at_most(_WOOD_STUD_MASONRY_VENEER if veneer else _WOOD_STUD, u_factor)
    elif wall_type == "steel_stud":
        letter = _at_most(_STEEL_STUD_MASONRY_VENEER if veneer else _STEEL_STUD, u_factor)
    elif wall_type == "double_wood_stud":
        letter = "K" if veneer else "J"
    elif wall_type == "sip":
        if u_factor >= (0.072 + 0.050) / 2:
            letter = "J" if veneer else "G"
        elif u_factor >= 0.050:
            letter = "K" if veneer else "I"
        else:
            letter = "K"
    elif wall_type == "cmu":
        letter = _at_most(_CMU, u_factor)
    elif wall_type in ("brick", "adobe", "concrete", "stone"):
        letter = _at_least(_MASONRY, u_factor)
    elif wall_type == "log":
        letter = _at_least(_LOG, u_factor)
    elif wall_type in ("icf", "straw_bale"):
        letter = "K"
    else:
        raise ValueError(f"Unknown wall type: {wall_type}")
    return T.TABLE_4A_TO_ASHRAE_GROUP[letter]


def foundation_wall_group(wall_type: str, thickness_in: float, u_above_grade: float) -> str:
    """ASHRAE wall group for the above-grade part of a foundation wall.

    Source: get_ashrae_wall_group (FoundationWall branch).
    """
    if wall_type in ("concrete_block", "concrete_block_foam_core", "concrete_block_perlite_core",
                     "concrete_block_vermiculite_core"):
        letter = _at_least(_FND_BLOCK_OPEN, u_above_grade)
    elif wall_type == "concrete_block_solid_core":
        letter = _at_least(_FND_BLOCK_FILLED, u_above_grade)
    elif wall_type == "solid_concrete" and thickness_in < 6.0:
        letter = _at_least(_FND_CONCRETE_4IN, u_above_grade)
    elif wall_type in ("double_brick", "solid_concrete"):
        letter = _at_least(_FND_MASONRY_8IN, u_above_grade)
    elif wall_type == "wood":
        letter = _at_least(_FND_WOOD, u_above_grade)
    else:
        raise ValueError(f"Unknown foundation wall type: {wall_type}")
    return T.TABLE_4A_TO_ASHRAE_GROUP[letter]


def wall_color(solar_absorptance: float) -> str:
    """Light / medium / dark from solar absorptance. Source: process_load_walls."""
    if solar_absorptance <= 0.5:
        return "light"
    return "medium" if solar_absorptance <= 0.75 else "dark"


def wall_cltd(group: str, color: str, ctd_f: float, cooling_design_temp_f: float, daily_range_index: int) -> float:
    """Cooling load temperature difference (F) for an exterior wall.

    Source: process_load_walls. Base CLTD (95 F day, by wall group) x color
    multiplier, shifted by (outdoor design - 95) and the daily-range adjustment.
    For cooling temperature differences under 10 F the alternative correction
    (CTD - 20 - daily-range adjustment) is used and the result floored at zero.
    """
    cltd = T.WALL_CLTD_BASE_SUN_F[group] * T.WALL_COLOR_MULTIPLIER[color]
    adjust = T.DAILY_RANGE_TEMP_ADJUST_F[daily_range_index]
    if ctd_f >= 10.0:
        return cltd + (cooling_design_temp_f - 95.0) + adjust
    return max(cltd + (ctd_f - 20.0 - adjust), 0.0)


def roof_cltd(r_value: float, roof_type: str, roof_color: str, cooling_design_temp_f: float,
              daily_range_index: int) -> float:
    """Cooling load temperature difference (F) for a roof directly over conditioned space.

    Source: process_load_roofs.
    """
    cltd = next(c for max_r, c in T.ROOF_CLTD_BY_R if r_value <= max_r)
    color = T.ROOF_COLOR_CLASS[roof_color]
    if color == "dark":
        if roof_type in ("clay_tile", "wood_shingles", "concrete"):
            cltd *= 0.83
    elif color == "medium":
        cltd *= 0.65 if roof_type in ("clay_tile", "concrete") else 0.83
    else:  # white / reflective
        cltd *= 0.83 if roof_type in ("asphalt_shingles", "wood_shingles", "shingles") else 0.65
    return cltd + (cooling_design_temp_f - 95.0) + T.DAILY_RANGE_TEMP_ADJUST_F[daily_range_index]


def door_cltd(ctd_f: float, daily_range_index: int) -> float:
    """Cooling temperature difference (F) for an exterior door. Source: process_load_doors."""
    return ctd_f + T.DOOR_CLTD_ADDER_F[daily_range_index]


def exposed_horizontal_ctd(ctd_f: float, daily_range_index: int) -> float:
    """Cooling temperature difference (F) for a floor or ceiling exposed to outdoor
    air (e.g. a floor over an open carport). Source: process_load_floors/ceilings."""
    return ctd_f - 5.0 + T.DAILY_RANGE_TEMP_ADJUST_F[daily_range_index]


def floor_over_enclosed_space_td(td_f: float, u_floor: float, u_wall: float, vented: bool) -> float:
    """Temperature difference (F) across a floor over a crawlspace or unconditioned
    basement, given the indoor-outdoor difference ``td_f`` and the area-weighted
    U-factor of the enclosing walls.

    Source: process_load_floors ("Manual J Figures A12-6 and A12-17" per the reference).
    """
    if vented:
        return td_f / (1.0 + (T.CRAWL_FLOOR_FACTOR * u_floor) / (u_wall + T.CRAWL_VENTED_WALL_ADDER))
    return u_wall * td_f / (T.CRAWL_FLOOR_FACTOR * u_floor + u_wall)
