# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Sources: HPXMLtoOpenStudio/resources/psychrometrics.rb, materials.rb (Gas, Liquid),
# unit_conversions.rb.
"""Moist-air properties and physical constants (IP units)."""

from __future__ import annotations

import math

# --- Constants (origin: OS-HPXML materials.rb, "Source: EES") -----------------
AIR_CP_BTU_PER_LB_F = 0.2399  # Gas.Air.cp
AIR_MOLAR_MASS = 28.97  # Gas.Air.m (lb/lbmol)
WATER_VAPOR_CP_BTU_PER_LB_F = 0.4495  # Gas.H2O_v.cp
WATER_VAPOR_MOLAR_MASS = 18.02  # Gas.H2O_v.m
WATER_CP_BTU_PER_LB_F = 0.9991  # Liquid.H2O_l.cp
WATER_HFG_BTU_PER_LB = 1055.0  # Liquid.H2O_l.h_fg
WATER_FREEZE_F = 32.0  # Liquid.H2O_l.t_frz
GAS_CONSTANT_BTU_PER_LBMOL_R = 1.9858  # materials.rb Gas#initialize
AIR_GAS_CONSTANT_BTU_PER_LB_R = GAS_CONSTANT_BTU_PER_LBMOL_R / AIR_MOLAR_MASS  # Gas.Air.r
PSYCH_MASS_RATIO = WATER_VAPOR_MOLAR_MASS / AIR_MOLAR_MASS  # Gas.PsychMassRat

# --- Unit conversions (origin: OS-HPXML unit_conversions.rb) -------------------
PSI_PER_ATM = 14.692
BTU_PER_FT3_PER_ATM = 2.719
GRAINS_PER_LB = 7000.0
BTU_PER_J = 3412.141633127942 / 1000.0 / 3600.0
KG_PER_LB = 0.45359237
BTUH_PER_TON = 12000.0


def f_to_r(t_f: float) -> float:
    """Fahrenheit to Rankine."""
    return t_f + 459.67


def f_to_c(t_f: float) -> float:
    return (t_f - 32.0) / 1.8


def c_to_f(t_c: float) -> float:
    return t_c * 1.8 + 32.0


def standard_pressure_psi(elevation_ft: float) -> float:
    """Standard atmospheric pressure (psi) at an elevation (ft).

    Source: Psychrometrics.Pstd_fZ.
    """
    return ((1.0 - 6.8754e-6 * elevation_ft) ** 5.2559) * PSI_PER_ATM


def saturation_pressure_psi(tdb_f: float) -> float:
    """Water vapor saturation pressure (psi) at a drybulb temperature (F).

    Source: Psychrometrics.Psat_fT (ASHRAE Handbook of Fundamentals correlations).
    """
    c1, c2, c3 = -1.0214165e4, -4.8932428, -5.3765794e-3
    c4, c5, c6, c7 = 1.9202377e-7, 3.5575832e-10, -9.0344688e-14, 4.1635019
    c8, c9, c10 = -1.0440397e4, -1.1294650e1, -2.7022355e-2
    c11, c12, c13 = 1.2890360e-5, -2.4780681e-9, 6.5459673
    t = f_to_r(tdb_f)
    if t < f_to_r(WATER_FREEZE_F):
        return math.exp(c1 / t + c2 + t * (c3 + t * (c4 + t * (c5 + c6 * t))) + c7 * math.log(t))
    return math.exp(c8 / t + c9 + t * (c10 + t * (c11 + c12 * t)) + c13 * math.log(t))


def humidity_ratio_from_rh(tdb_f: float, rh_frac: float, p_psi: float) -> float:
    """Humidity ratio (lb water / lb dry air) from drybulb (F), RH (0-1), pressure (psi).

    Source: Psychrometrics.w_fT_R_P. (Uses 0.62198, as the reference does.)
    """
    pw = rh_frac * saturation_pressure_psi(tdb_f)
    return 0.62198 * pw / (p_psi - pw)


def humidity_ratio_from_wetbulb(tdb_f: float, twb_f: float, p_psi: float) -> float:
    """Humidity ratio (lb/lb) from drybulb and wetbulb (F) and pressure (psi).

    Source: Psychrometrics.w_fT_Twb_P and w_fP.
    """
    pws = saturation_pressure_psi(twb_f)
    w_star = PSYCH_MASS_RATIO * pws / (p_psi - pws)
    num = (
        WATER_HFG_BTU_PER_LB - (WATER_CP_BTU_PER_LB_F - WATER_VAPOR_CP_BTU_PER_LB_F) * twb_f
    ) * w_star - AIR_CP_BTU_PER_LB_F * (tdb_f - twb_f)
    den = WATER_HFG_BTU_PER_LB + WATER_VAPOR_CP_BTU_PER_LB_F * tdb_f - WATER_CP_BTU_PER_LB_F * twb_f
    return num / den


def wetbulb_f(tdb_f: float, w: float, p_psi: float) -> float:
    """Wetbulb temperature (F) from drybulb (F), humidity ratio and pressure (psi).

    Inverse of ``humidity_ratio_from_wetbulb``. The reference
    (Psychrometrics.Twb_fT_w_P) solves the same equation with its own iteration
    scheme; here it is solved by bisection, to 1e-7 F.
    """
    lo, hi = -60.0, tdb_f
    if humidity_ratio_from_wetbulb(tdb_f, hi, p_psi) <= w:
        return tdb_f
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if humidity_ratio_from_wetbulb(tdb_f, mid, p_psi) < w:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def enthalpy_btu_per_lb(tdb_f: float, w: float) -> float:
    """Moist-air enthalpy (Btu/lb dry air) from drybulb (F) and humidity ratio (lb/lb).

    Source: Psychrometrics.h_fT_w / h_fT_w_SI.
    """
    t_c = f_to_c(tdb_f)
    h_j_per_kg = 1000.0 * (1.006 * t_c + w * (2501.0 + 1.86 * t_c))
    return h_j_per_kg * BTU_PER_J * KG_PER_LB


def air_density_lb_per_ft3(p_psi: float, tdb_f: float) -> float:
    """Dry-air density (lb/ft3) by the ideal gas law, as used in hvac_sizing.rb
    (process_site_calcs_and_design_temps: mj.indoor_air_density)."""
    p_atm = p_psi / PSI_PER_ATM
    return p_atm * BTU_PER_FT3_PER_ATM / (AIR_GAS_CONSTANT_BTU_PER_LB_R * f_to_r(tdb_f))


def design_grains(w_outdoor: float, w_indoor: float) -> float:
    """Outdoor minus indoor humidity ratio, in grains/lb.

    Source: HVACSizing.calculate_design_grains.
    """
    return (w_outdoor - w_indoor) * GRAINS_PER_LB
