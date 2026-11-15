# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (get_design_temp_heating,
# get_design_temp_cooling, get_garage_frac_under_conditioned, get_space_ua_values,
# calculate_space_design_temp, calculate_average_r_value).
"""Design temperatures of unconditioned buffer spaces (attics, crawlspaces,
unconditioned basements, garages)."""

from __future__ import annotations

import math

from . import psychro, tables as T
from .foundation import concrete_r, foundation_wall_above_grade_u, foundation_wall_below_grade_u
from .model import GROUND, OUTSIDE, BufferSpace, Building, Floor, FoundationWall, Slab

# origin: OS-HPXML defaults (vent area / floor area) used when no value is given
DEFAULT_VENTED_ATTIC_SLA = 1.0 / 300.0
DEFAULT_VENTED_CRAWL_SLA = 1.0 / 150.0


def average_r_value(surfaces) -> float:
    """Area-weighted average R-value; NaN for an empty list (comparisons are then
    False, as in the reference). Source: calculate_average_r_value."""
    area = sum(s.area_ft2 for s in surfaces)
    ua = 0.0
    for s in surfaces:
        if isinstance(s, FoundationWall) and s.r_value is None and s.assembly is None:
            r = s.insulation_interior_r + s.insulation_exterior_r
            ua += math.inf if r == 0 else s.area_ft2 / r
        else:
            ua += s.area_ft2 / s.r
    if area == 0:
        return math.nan
    return area / ua


def _touches(surface, space_id: str) -> bool:
    return space_id in (surface.inside, surface.outside)


def foundation_wall_combined_u(fw: FoundationWall, bldg: Building, ground_conductivity: float) -> float:
    """Area-weighted U of a foundation wall (below-grade part without soil
    resistance, above-grade part net of openings).

    Source: get_space_ua_values and process_load_floors (sum_ua_wall / sum_a_wall).
    """
    ua, area = _foundation_wall_ua(fw, bldg, ground_conductivity)
    return ua / area


def _foundation_wall_ua(fw, bldg, ground_conductivity):
    ua = area = 0.0
    bg_area = fw.below_grade_area_ft2
    if bg_area > 0:
        ua += foundation_wall_below_grade_u(fw, False, ground_conductivity) * bg_area
        area += bg_area
    ag_area = bldg.net_area_ft2(fw) - bg_area
    if ag_area > 0:
        ua += foundation_wall_above_grade_u(fw, True) * ag_area
        area += ag_area
    return ua, area


def space_ua_values(bldg: Building, space: BufferSpace, outside_air_density: float) -> dict[str, float]:
    """UA (Btu/h-F) from a buffer space to outdoor air, ground, and conditioned space.

    Source: get_space_ua_values.
    """
    k_soil = bldg.conditions.ground_conductivity_btu_h_ft_f
    ua = {"outside": 0.0, "ground": 0.0, "conditioned": 0.0}

    def side_kind(ref):
        if ref == OUTSIDE:
            return "outside"
        if ref == GROUND:
            return "ground"
        return "conditioned" if bldg.is_room(ref) else None

    for s in bldg.opaque_surfaces:
        if s.inside == space.id:
            other = side_kind(s.outside)
        elif s.outside == space.id:
            other = side_kind(s.inside)
        else:
            continue
        if other is None:
            continue  # borders another buffer space
        if other in ("outside", "conditioned"):
            if isinstance(s, FoundationWall):
                u = foundation_wall_above_grade_u(s, True)
            else:
                u = s.u
            ua[other] += u * s.area_ft2
            continue
        # Ground contact. Ground temperature is used for basements, not crawlspaces
        # (Walker 1998, per the reference).
        target = "outside" if space.kind in ("crawlspace_vented", "crawlspace_unvented") else "ground"
        if isinstance(s, FoundationWall):
            ua[target] += foundation_wall_combined_u(s, bldg, k_soil) * s.area_ft2
        elif isinstance(s, Slab):
            if s.thickness_in == 0:
                ua[target] += 0.1 * s.area_ft2  # dirt floor, U = 0.1 (Walker 1998, per the reference)
            else:
                r_conc = concrete_r(s.thickness_in)
                if s.under_slab_insulation_spans_slab:
                    horiz_area = s.area_ft2
                else:
                    horiz_area = s.under_slab_insulation_width_ft * s.exposed_perimeter_ft
                ua[target] += horiz_area / (r_conc + s.under_slab_insulation_r)
                vert_area = s.perimeter_insulation_depth_ft * s.exposed_perimeter_ft
                ua[target] += vert_area / (r_conc + s.perimeter_insulation_r)
                ua[target] += max(s.area_ft2 - horiz_area - vert_area, 0.0) / r_conc

    # Infiltration of outdoor air into the space
    if space.kind in ("attic_vented", "crawlspace_vented"):
        if space.vent_ach is not None:
            ach = space.vent_ach
        else:
            sla = space.vent_sla
            if sla is None:
                sla = DEFAULT_VENTED_ATTIC_SLA if space.kind == "attic_vented" else DEFAULT_VENTED_CRAWL_SLA
            # Airflow.get_infiltration_ACH_from_SLA at the reference height reduces to this:
            ach = 1000.0 * sla * bldg.conditions.wsf
    else:
        ach = T.UNVENTED_SPACE_ACH
    cfm = ach / 60.0 * space.volume_ft3
    ua["outside"] += cfm * outside_air_density * psychro.AIR_CP_BTU_PER_LB_F * 60.0
    return ua


def balance_temperature(ua: dict[str, float], setpoint_f: float, outdoor_f: float, ground_f: float) -> float:
    """Steady-state temperature of a space from its UA to each neighbor.

    Source: calculate_space_design_temp (general case).
    """
    total = ua["outside"] + ua["ground"] + ua["conditioned"]
    return (ua["outside"] * outdoor_f + ua["ground"] * ground_f + ua["conditioned"] * setpoint_f) / total


def insulated_unvented_attic_cooling_temp(ua: dict[str, float], cooling_setpoint_f: float) -> float:
    """Cooling design temperature of an unvented attic insulated at the roof.

    Source: calculate_space_design_temp (special case): between setpoint + 5 F
    and setpoint + 50 F, by the share of UA that goes to conditioned space.
    """
    max_temp = cooling_setpoint_f + 50.0
    min_temp = cooling_setpoint_f + 5.0
    frac_conditioned = ua["conditioned"] / (ua["conditioned"] + ua["outside"])
    return max_temp - frac_conditioned * (max_temp - min_temp)


def garage_fraction_under_conditioned(bldg: Building, space: BufferSpace) -> float:
    """Source: get_garage_frac_under_conditioned."""
    total = sum(r.area_ft2 for r in bldg.roofs if r.inside == space.id)
    conditioned = 0.0
    for f in bldg.floors:
        if _touches(f, space.id):
            total += f.area_ft2
            if bldg.is_room(f.inside) or bldg.is_room(f.outside):
                conditioned += f.area_ft2
    return 0.5 if total == 0 else conditioned / total


def _attic_is_roof_insulated(bldg, space) -> bool:
    ceilings = [f for f in bldg.floors if f.is_ceiling and _touches(f, space.id)]
    roofs = [r for r in bldg.roofs if r.inside == space.id]
    return average_r_value(ceilings) < average_r_value(roofs)


def _is_above_grade_garage(bldg, space) -> bool:
    return space.kind == "garage" and not any(fw.inside == space.id for fw in bldg.foundation_walls)


def heating_design_temp(bldg: Building, space: BufferSpace, outside_air_density: float) -> float:
    """Source: get_design_temp_heating."""
    if space.heating_design_temp_f is not None:
        return space.heating_design_temp_f
    c = bldg.conditions
    outdoor = c.heating_design_temp_f

    def balance():
        return balance_temperature(space_ua_values(bldg, space, outside_air_density), c.heating_setpoint_f,
                                   outdoor, c.ground_temp_winter_f)

    if space.kind in ("attic_vented", "attic_unvented"):
        if _attic_is_roof_insulated(bldg, space) and space.kind == "attic_unvented":
            return balance()
        return outdoor
    if _is_above_grade_garage(bldg, space):
        return outdoor + T.GARAGE_HEAT_ADDER_UNDER_CONDITIONED_F * garage_fraction_under_conditioned(bldg, space)
    return balance()


def cooling_design_temp(bldg: Building, space: BufferSpace, outside_air_density: float) -> float:
    """Source: get_design_temp_cooling."""
    if space.cooling_design_temp_f is not None:
        return space.cooling_design_temp_f
    c = bldg.conditions
    outdoor = c.cooling_design_temp_f
    dr = T.DAILY_RANGE_INDEX[c.daily_temp_range]

    if space.kind in ("attic_vented", "attic_unvented"):
        if _attic_is_roof_insulated(bldg, space):
            if space.kind == "attic_vented":
                return outdoor + 40.0  # origin: OS-HPXML ("number from a California study")
            return insulated_unvented_attic_cooling_temp(space_ua_values(bldg, space, outside_air_density),
                                                         c.cooling_setpoint_f)
        # Area-weighted table temperature, then shifted for design temp and daily range
        total_area = weighted = 0.0
        for roof in bldg.roofs:
            if roof.inside != space.id:
                continue
            area = bldg.net_area_ft2(roof)
            total_area += area
            if space.kind == "attic_unvented":
                temp = T.ATTIC_UNVENTED_TEMP_F[roof.radiant_barrier]
            else:
                temp = T.ATTIC_VENTED_TEMP_F[roof.radiant_barrier][T.ROOF_MATERIAL_CLASS[roof.roof_type]][
                    T.ROOF_COLOR_CLASS[roof.roof_color]]
            weighted += temp * area
        if total_area == 0:
            raise ValueError(f"Attic '{space.id}' has no roof surfaces.")
        return weighted / total_area + (outdoor - 95.0) + T.DAILY_RANGE_TEMP_ADJUST_F[dr]
    if _is_above_grade_garage(bldg, space):
        frac = garage_fraction_under_conditioned(bldg, space)
        under, not_under = T.GARAGE_COOL_ADDER_F[dr]
        return outdoor + under * frac + not_under * (1.0 - frac)
    return balance_temperature(space_ua_values(bldg, space, outside_air_density), c.cooling_setpoint_f,
                               outdoor, c.ground_temp_summer_f)
