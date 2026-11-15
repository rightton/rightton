# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb
# (process_load_infiltration_ventilation, get_mj_default_ach_values,
# get_ventilation_data) and airflow.rb (leakage unit conversions).
"""Infiltration (from blower-door data) and mechanical ventilation airflows."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import tables as T


def leakage_at_pressure(q_old: float, p_old_pa: float, p_new_pa: float) -> float:
    """Scale an air leakage rate to another test pressure: Q2 = Q1 (P2/P1)^0.65.

    Source: Airflow.calc_infiltration_at_diff_pressure.
    """
    return q_old * (p_new_pa / p_old_pa) ** T.INFIL_PRESSURE_EXPONENT


def sla_from_ach50(ach50: float, avg_ceiling_height_ft: float) -> float:
    """Specific leakage area (ELA at 4 Pa per ft2 of floor) from ACH50.

    Source: Airflow.get_infiltration_SLA_from_ACH50.
    """
    n = T.INFIL_PRESSURE_EXPONENT
    return (ach50 * 0.283316 * 4.0**n) / (50.0**n * 60.0 * 144.0 / avg_ceiling_height_ft)


def sla_from_natural_ach(nach: float, height_ft: float, avg_ceiling_height_ft: float, wsf: float) -> float:
    """Source: Airflow.get_infiltration_SLA_from_ACH."""
    ref = T.REFERENCE_HEIGHT_FT
    return nach * (avg_ceiling_height_ft / ref) / (1000.0 * wsf * (height_ft / ref) ** 0.4)


def natural_ach_from_sla(sla: float, height_ft: float, avg_ceiling_height_ft: float, wsf: float) -> float:
    """Annual-average natural air changes per hour from SLA (ASHRAE 62.2 form).

    Source: Airflow.get_infiltration_ACH_from_SLA / get_infiltration_NL_from_SLA.
    """
    ref = T.REFERENCE_HEIGHT_FT
    normalized_leakage = 1000.0 * sla * (height_ft / ref) ** 0.4
    return normalized_leakage * wsf * ref / avg_ceiling_height_ft


def stack_wind_coefficients(stories_above_grade: float, shielding_class: int) -> tuple[float, float]:
    """(stack coefficient, wind coefficient). Source: process_load_infiltration_ventilation."""
    c_s = T.INFIL_STACK_COEFF_PER_STORY * stories_above_grade
    c_w = (T.INFIL_WIND_COEFF_BASE - T.INFIL_WIND_COEFF_PER_SHIELD_CLASS * (shielding_class - 3)) \
        * stories_above_grade**T.INFIL_WIND_STORY_EXPONENT
    return c_s, c_w


def design_infiltration_cfm(ela_in2: float, c_s: float, c_w: float, temp_diff_f: float, windspeed_mph: float) -> float:
    """Infiltration at design conditions: CFM = ELA * sqrt(Cs * dT + Cw * V^2).

    Source: process_load_infiltration_ventilation (icfm_cool / icfm_heat).
    """
    return ela_in2 * (c_s * temp_diff_f + c_w * windspeed_mph**2) ** 0.5


def default_table_ach(leakiness: str, cfa_ft2: float, stories_above_grade: float, detached: bool) -> tuple[float, float]:
    """(heating ACH, cooling ACH) from the tight/average/leaky default tables.

    Source: get_mj_default_ach_values.
    """
    index = next((i for i, limit in enumerate(T.ACH_FLOOR_AREA_BINS_FT2) if cfa_ft2 <= limit),
                 len(T.ACH_FLOOR_AREA_BINS_FT2))
    if detached:
        story = 0 if stories_above_grade < 2 else 1
        return T.ACH_SFD_HEATING[story][leakiness][index], T.ACH_SFD_COOLING[story][leakiness][index]
    return T.ACH_MF_HEATING[leakiness][index], T.ACH_MF_COOLING[leakiness][index]


def net_infiltration_cfm(icfm: float, q_imbalance_cfm: float) -> float:
    """Infiltration combined with unbalanced mechanical ventilation.

    ``q_imbalance_cfm`` is exhaust minus supply. Source:
    process_load_infiltration_ventilation (NCFM).
    """
    if q_imbalance_cfm == 0:
        return icfm
    if q_imbalance_cfm > 0:  # house depressurized
        return (icfm**1.5 + q_imbalance_cfm**1.5) ** 0.67
    if icfm < abs(q_imbalance_cfm):  # pressurization dominates
        return 0.0
    return (icfm**1.5 - abs(q_imbalance_cfm) ** 1.5) ** 0.67


@dataclass
class InfiltrationResult:
    """The ACH50-to-design-airflow conversion, kept step by step for display."""

    method: str
    ach50: float | None = None
    sla: float | None = None
    ela_in2: float | None = None
    stack_coefficient: float | None = None
    wind_coefficient: float | None = None
    heating_cfm: float = 0.0  # before ventilation imbalance
    cooling_cfm: float = 0.0
    net_heating_cfm: float = 0.0
    net_cooling_cfm: float = 0.0
    notes: list[str] = field(default_factory=list)


def infiltration_airflows(bldg, htd_f: float, ctd_f: float) -> InfiltrationResult:
    """Design infiltration airflow for the whole house.

    Source: process_load_infiltration_ventilation and
    Airflow.get_values_from_air_infiltration_measurements.
    """
    infil = bldg.infiltration
    if infil is None:
        return InfiltrationResult(method="none")
    cfa = bldg.cfa_ft2
    stories = bldg.stories_above_grade
    res = InfiltrationResult(method=infil.method)
    if infil.method == "blower_door":
        volume = infil.volume_ft3
        if volume is None:
            volume = sum(r.floor_area_ft2 * r.ceiling_height_ft for r in bldg.rooms)
        avg_ceiling = volume / cfa  # per ANSI/RESNET/ICC 380, via the reference
        wsf = bldg.conditions.wsf
        height = infil.height_ft if infil.height_ft is not None else avg_ceiling * stories
        if infil.ach50 is not None or infil.cfm50 is not None:
            ach = infil.ach50 if infil.ach50 is not None else infil.cfm50 * 60.0 / volume
            res.ach50 = leakage_at_pressure(ach, infil.house_pressure_pa, 50.0)
            res.sla = sla_from_ach50(res.ach50, avg_ceiling)
        elif infil.natural_ach is not None:
            res.sla = sla_from_natural_ach(infil.natural_ach, height, avg_ceiling, wsf)
        elif infil.ela_in2 is not None:
            res.sla = infil.ela_in2 / 144.0 / cfa
        elif infil.sla is not None:
            res.sla = infil.sla
        else:
            raise ValueError("Infiltration needs ach50, cfm50, natural_ach, ela_in2 or sla.")
        res.ela_in2 = res.sla * cfa * infil.exterior_fraction * 144.0
        res.stack_coefficient, res.wind_coefficient = stack_wind_coefficients(stories, infil.shielding_class)
        # [CONFIRM] The reference scales wind speed with height for apartments and
        # attached units above grade; not ported (v1 targets detached houses).
        res.cooling_cfm = design_infiltration_cfm(res.ela_in2, res.stack_coefficient, res.wind_coefficient,
                                                  ctd_f, T.INFIL_WINDSPEED_COOLING_MPH)
        res.heating_cfm = design_infiltration_cfm(res.ela_in2, res.stack_coefficient, res.wind_coefficient,
                                                  htd_f, T.INFIL_WINDSPEED_HEATING_MPH)
    elif infil.method == "default_table":
        ach_htg, ach_clg = default_table_ach(infil.leakiness, cfa, stories,
                                             bldg.facility_type == "single_family_detached")
        volume = bldg.above_grade_volume_ft3
        if volume is None:
            volume = sum(r.floor_area_ft2 * r.ceiling_height_ft for r in bldg.rooms if not r.below_grade)
        res.cooling_cfm = ach_clg * volume / 60.0
        res.heating_cfm = ach_htg * volume / 60.0
    else:
        raise ValueError(f"Unknown infiltration method: {infil.method}")
    if infil.has_fireplace:
        res.heating_cfm += T.FIREPLACE_HEATING_CFM
    return res


@dataclass
class VentilationData:
    q_imbalance_cfm: float = 0.0  # exhaust minus supply
    q_outdoor_air_cfm: float = 0.0  # supply air that is a space load
    heating_sensible_eff: float = 0.0
    cooling_sensible_eff: float = 0.0
    cooling_latent_eff: float = 0.0


def ventilation_data(fans) -> VentilationData:
    """Whole-house ventilation airflows.

    Source: get_ventilation_data. Not ported: preheat/precool coils and shared
    (multifamily) systems. [CONFIRM] The reference derives the apparent sensible
    effectiveness of an ERV/HRV from its rated recovery efficiency and fan power;
    here the effectiveness is a direct input.
    """
    fans = [f for f in fans if f.flow_cfm > 0]
    if not fans:
        return VentilationData()

    def total(*kinds):
        return sum(f.flow_cfm for f in fans if f.fan_type in kinds)

    q_recovery = total("erv", "hrv")
    q_cfis = total("cfis")
    q_supply_total = total("supply") + total("balanced") + q_recovery + q_cfis
    q_exhaust_total = total("exhaust") + total("balanced") + q_recovery
    data = VentilationData(q_imbalance_cfm=q_exhaust_total - q_supply_total,
                           q_outdoor_air_cfm=q_supply_total - q_cfis)
    for f in fans:
        if f.fan_type in ("erv", "hrv"):
            share = f.flow_cfm / data.q_outdoor_air_cfm
            data.heating_sensible_eff += share * f.sensible_effectiveness
            data.cooling_latent_eff += share * f.latent_effectiveness
    data.cooling_sensible_eff = data.heating_sensible_eff
    return data
