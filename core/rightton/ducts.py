# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (apply_hvac_duct_loads,
# calc_delivery_effectiveness_heating/cooling and their _calc_de_* helpers,
# calculate_sensible_latent_split, calc_duct_conduction_values_for_dse,
# calc_duct_leakages_cfm25, calc_airflow_rate, get_duct_regain_factor,
# apply_hvac_air_temperatures).
"""Duct loads by the ASHRAE Standard 152 delivery-effectiveness method.

Delivery effectiveness (DE) is the share of the equipment's output that reaches
the rooms. The duct load is what must be added so that load / DE is delivered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import psychro, tables as T
from .airflow import leakage_at_pressure
from .model import OUTSIDE

MAX_ITERATIONS = 50
TOLERANCE = 0.001  # 0.1 %


def airflow_cfm(cfm_per_ton: float, load_btuh: float) -> float:
    """System airflow for a load, rounded to a whole cfm. Source: calc_airflow_rate."""
    return float(math.floor(round(cfm_per_ton) * load_btuh / psychro.BTUH_PER_TON + 0.5))


def leaving_air_temp_f(cool_sens_btuh: float, cool_total_btuh: float) -> float:
    """Cooling coil leaving-air temperature from the sensible heat ratio.

    Source: apply_hvac_air_temperatures ("Manual S Table 1-4" per the reference,
    with linear interpolation between 54 and 58 F for SHR 0.80-0.85).
    """
    shr = min(cool_sens_btuh / cool_total_btuh, 1.0)
    if shr < 0.80:
        return 54.0
    if shr < 0.85:
        return ((58.0 - 54.0) / (0.85 - 0.80)) * (shr - 0.8) + 54.0
    return 58.0


def conduction_fractions(area_s, area_r, r_s, r_r, cfm, air_density):
    """B_s, B_r = exp(-A / (60 * cfm * rho * cp * R)). Source: _calc_de_conduction_fractions."""
    cp = psychro.AIR_CP_BTU_PER_LB_F
    b_s = math.exp(-area_s / (60.0 * cfm * air_density * cp * r_s))
    b_r = math.exp(-area_r / (60.0 * cfm * air_density * cp * r_r))
    return b_s, b_r


def leakage_factors(q_s, q_r, cfm):
    """a_s, a_r = (cfm - leak) / cfm. Source: _calc_de_leakage_factors."""
    return (cfm - q_s) / cfm, (cfm - q_r) / cfm


def de_heating(a_s, b_s, a_r, b_r, dt_s, dt_r, dt_e):
    """ASHRAE 152 Equation 6-23. Source: _calc_de_heating."""
    return a_s * b_s - a_s * b_s * (1.0 - a_r * b_r) * (dt_r / dt_e) - a_s * (1.0 - b_s) * (dt_s / dt_e)


def de_cooling(a_s, cfm, load_total, a_r, h_r, b_r, dt_r, b_s, leaving_air_temp, t_amb_s, air_density, h_in):
    """ASHRAE 152 Equation 6-25. Source: _calc_de_cooling."""
    cp = psychro.AIR_CP_BTU_PER_LB_F
    return ((a_s * 60.0 * cfm * air_density) / (-load_total)) * (
        (-load_total) / (60.0 * cfm * air_density)
        + (1.0 - a_r) * (h_r - h_in)
        + a_r * cp * (b_r - 1.0) * dt_r
        + cp * (b_s - 1.0) * (leaving_air_temp - t_amb_s)
    )


def de_corrected(de, f_regain_s, f_regain_r, b_r, a_r, dt_r, dt_e):
    """DE corrected for thermal regain, ASHRAE 152 Equation 6-40, limited to
    0.25..1.0. Source: _calc_decorr."""
    decorr = de + f_regain_s * (1.0 - de) - (f_regain_s - f_regain_r - b_r * (a_r * f_regain_s - f_regain_r)) * dt_r / dt_e
    return min(max(decorr, 0.25), 1.0)


def delivery_effectiveness_heating(*, q_s, q_r, cfm, load_sens, t_amb_s, t_amb_r, area_s, area_r, t_setpoint,
                                   f_regain_s, f_regain_r, r_s, r_r, air_density):
    """Source: calc_delivery_effectiveness_heating."""
    b_s, b_r = conduction_fractions(area_s, area_r, r_s, r_r, cfm, air_density)
    a_s, a_r = leakage_factors(q_s, q_r, cfm)
    dt_e = load_sens / (60.0 * cfm * air_density * psychro.AIR_CP_BTU_PER_LB_F)
    dt_s, dt_r = t_setpoint - t_amb_s, t_setpoint - t_amb_r
    de = de_heating(a_s, b_s, a_r, b_r, dt_s, dt_r, dt_e)
    return de_corrected(de, f_regain_s, f_regain_r, b_r, a_r, dt_r, dt_e)


def delivery_effectiveness_cooling(*, q_s, q_r, leaving_air_temp, cfm, load_sens, load_total, t_amb_s, t_amb_r,
                                   area_s, area_r, t_setpoint, f_regain_s, f_regain_r, h_r, r_s, r_r,
                                   air_density, h_in):
    """Source: calc_delivery_effectiveness_cooling."""
    b_s, b_r = conduction_fractions(area_s, area_r, r_s, r_r, cfm, air_density)
    a_s, a_r = leakage_factors(q_s, q_r, cfm)
    dt_e = load_sens / (60.0 * cfm * air_density * psychro.AIR_CP_BTU_PER_LB_F)
    dt_r = t_setpoint - t_amb_r
    de = de_cooling(a_s, cfm, load_total, a_r, h_r, b_r, dt_r, b_s, leaving_air_temp, t_amb_s, air_density, h_in)
    return de_corrected(de, f_regain_s, f_regain_r, b_r, a_r, dt_r, -dt_e)


def duct_leakage_cfm(system, cfm: float) -> tuple[float, float]:
    """(supply, return) leakage to outside at 25 Pa. Source: calc_duct_leakages_cfm25."""
    def convert(value):
        if system.leakage_units == "fraction":
            return value * cfm
        if system.leakage_units == "cfm50":
            return leakage_at_pressure(value, 50.0, 25.0)
        if system.leakage_units == "cfm25":
            return value
        raise ValueError(f"Unknown duct leakage units: {system.leakage_units}")
    return convert(system.supply_leakage), convert(system.return_leakage)


def duct_regain_factor(bldg, location: str) -> float:
    """Share of duct losses that find their way back into the conditioned space.

    Source: get_duct_regain_factor.
    """
    from .spaces import average_r_value  # local import to avoid a cycle

    if location == OUTSIDE:
        return 0.0
    if bldg.is_room(location):
        return 1.0
    space = bldg.buffer(location)
    if space.kind == "weighted":
        return space.duct_regain
    if space.kind in ("attic_vented", "attic_unvented"):
        return T.DUCT_REGAIN_ATTIC
    if space.kind == "garage":
        return T.DUCT_REGAIN_GARAGE
    ceilings = [f for f in bldg.floors if not f.is_ceiling and location in (f.inside, f.outside)]
    walls = [w for w in bldg.foundation_walls if location in (w.inside, w.outside)]
    return T.DUCT_REGAIN[space.kind][(average_r_value(ceilings) > 4, average_r_value(walls) > 4)]


@dataclass
class DuctValues:
    area_s: float
    area_r: float
    r_s: float
    r_r: float
    t_amb_s: float
    t_amb_r: float
    f_regain_s: float
    f_regain_r: float


def duct_conduction_values(bldg, system, design_temps: dict[str, float]) -> DuctValues:
    """Area-weighted duct properties outside conditioned space, by supply/return.

    Source: calc_duct_conduction_values_for_dse. ``design_temps`` maps a location
    (buffer space id or OUTSIDE) to its design temperature.
    """
    out = {}
    for duct_type in ("supply", "return"):
        ducts = [d for d in system.ducts if d.duct_type == duct_type and not bldg.is_room(d.location)]
        total = sum(d.surface_area_ft2 * d.area_multiplier for d in ducts)
        if total == 0:
            # There may still be leakage to outside, so use the outdoor temperature
            out[duct_type] = (0.0, math.inf, design_temps[OUTSIDE], 0.0)
            continue
        u = t_amb = regain = 0.0
        for d in ducts:
            frac = d.surface_area_ft2 * d.area_multiplier / total
            u += frac / d.effective_r_value
            t_amb += frac * design_temps[d.location]
            regain += frac * duct_regain_factor(bldg, d.location)
        out[duct_type] = (total, 1.0 / u, t_amb, regain)
    s, r = out["supply"], out["return"]
    return DuctValues(s[0], r[0], s[1], r[1], s[2], r[2], s[3], r[3])


def heating_duct_load(*, bldg, system, load_btuh, design_temps, setpoint_f, air_density) -> float:
    """Heating duct load (Btu/h) for a zone load, iterating because airflow grows
    with the load. Source: apply_hvac_duct_loads (heating)."""
    v = duct_conduction_values(bldg, system, design_temps)
    delta, de, load_next = 1.0, None, load_btuh
    for _ in range(MAX_ITERATIONS):
        if abs(delta) <= TOLERANCE:
            break
        cfm = airflow_cfm(system.heating_cfm_per_ton, load_next)
        q_s, q_r = duct_leakage_cfm(system, cfm)
        de_prev = de
        de = delivery_effectiveness_heating(q_s=q_s, q_r=q_r, cfm=cfm, load_sens=load_next, t_amb_s=v.t_amb_s,
                                            t_amb_r=v.t_amb_r, area_s=v.area_s, area_r=v.area_r,
                                            t_setpoint=setpoint_f, f_regain_s=v.f_regain_s,
                                            f_regain_r=v.f_regain_r, r_s=v.r_s, r_r=v.r_r, air_density=air_density)
        if de_prev is not None:
            de = (de + de_prev) / 2.0  # damping, as in the reference
        load_prev = load_next
        load_next = load_btuh / de
        delta = (load_next - load_prev) / load_prev
    return load_next - load_btuh


def cooling_duct_load(*, bldg, system, load_sens_btuh, load_lat_btuh, design_temps, setpoint_f, air_density,
                      leaving_air_temp, cooling_humidity_ratio, indoor_enthalpy, altitude_factor,
                      design_grains) -> tuple[float, float]:
    """(sensible, latent) cooling duct load (Btu/h). Source: apply_hvac_duct_loads (cooling)."""
    v = duct_conduction_values(bldg, system, design_temps)
    h_r = psychro.enthalpy_btu_per_lb(v.t_amb_r, cooling_humidity_ratio)  # air around the return duct
    delta, de = 1.0, None
    total_next = load_sens_btuh + load_lat_btuh
    sens_next, lat_next = load_sens_btuh, load_lat_btuh
    cfm = airflow_cfm(system.cooling_cfm_per_ton, total_next)
    _, q_r = duct_leakage_cfm(system, cfm)
    for _ in range(MAX_ITERATIONS):
        if abs(delta) <= TOLERANCE:
            break
        # Latent load picked up through return leaks (calculate_sensible_latent_split)
        lat = load_lat_btuh + max(0.0, T.LATENT_AIR_FACTOR * altitude_factor * q_r * design_grains)
        sens = total_next - lat
        total = lat + sens
        cfm = airflow_cfm(system.cooling_cfm_per_ton, total)
        q_s, q_r = duct_leakage_cfm(system, cfm)
        de_prev = de
        de = delivery_effectiveness_cooling(q_s=q_s, q_r=q_r, leaving_air_temp=leaving_air_temp, cfm=cfm,
                                            load_sens=sens, load_total=total, t_amb_s=v.t_amb_s, t_amb_r=v.t_amb_r,
                                            area_s=v.area_s, area_r=v.area_r, t_setpoint=setpoint_f,
                                            f_regain_s=v.f_regain_s, f_regain_r=v.f_regain_r, h_r=h_r,
                                            r_s=v.r_s, r_r=v.r_r, air_density=air_density, h_in=indoor_enthalpy)
        if de_prev is not None:
            de = (de + de_prev) / 2.0
        total_prev = total_next
        sens_next = load_sens_btuh / de
        lat_next = load_lat_btuh / de
        total_next = sens_next + lat_next
        delta = (total_next - total_prev) / total_prev
    return sens_next - load_sens_btuh, lat_next - load_lat_btuh


def duct_effective_r_value(nominal_r: float, duct_type: str, rectangular_frac: float) -> float:
    """Effective R-value of a duct (air films, and the thinning of insulation
    wrapped around round ducts, included) from the R-value printed on its insulation.

    Source: Defaults.get_duct_effective_r_value in OS-HPXML defaults.rb (ducts not
    buried in attic insulation), which cites Palmiter & Kruse 2006, "True R-Values
    of Round Residential Ductwork", and ASHRAE HoF for bare ducts (R-1.7).
    """
    if nominal_r <= 0:
        return 1.7
    d_round = 6.0 if duct_type == "supply" else 14.0  # in, assumed average diameter
    f_round = 1.0 - rectangular_frac
    r_ext = 0.667  # exterior air film
    r_int_rect = 0.333  # interior film, rectangular duct
    r_int_round = 0.3429 * d_round**0.1974  # interior film, round duct
    t = nominal_r / 2.8  # insulation thickness, in (R-2.8 per inch fiberglass)
    r_actual = nominal_r / t * (d_round / 2.0) * math.log(1.0 + (2.0 * t) / d_round)
    r_rect = r_int_rect + nominal_r + r_ext
    r_round = r_int_round + r_actual + r_ext * (d_round / (d_round + 2 * t))
    return round(1.0 / (rectangular_frac / r_rect + f_round / r_round), 2)
