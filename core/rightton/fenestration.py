# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (process_load_windows_skylights,
# calculate_aed_excursion, get_window_interior_shading_coefficient, get_mj_azimuth),
# constructions.rb (get_ufactor_shgc_adjusted_by_storms), math.rb.
"""Window and skylight heat-transfer multipliers (HTM, Btu/h per ft2)."""

from __future__ import annotations

import math
from typing import Optional, Sequence

from . import tables as T

HOURS = 12  # hourly fenestration loads are kept for hours 8..19


def interp_neighbors(sorted_values: Sequence[float], target: float) -> tuple[int, int]:
    """Indices of the two table points used to interpolate (or extrapolate).

    Source: MathTools.find_array_neighbor_indices.
    """
    for i, x in enumerate(sorted_values):
        if x >= target:
            return (0, 1) if i == 0 else (i - 1, i)
    return len(sorted_values) - 2, len(sorted_values) - 1


def interp_table(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    """Linear interpolation, extrapolating beyond the ends. Source: MathTools.interp2."""
    i1, i2 = interp_neighbors(xs, x)
    return ys[i1] + ((x - xs[i1]) / (xs[i2] - xs[i1])) * (ys[i2] - ys[i1])


def orientation_index(azimuth_deg: float) -> int:
    """Index into the orientation tables (0=S, 2=W, 4=N, 6=E) for a compass azimuth.

    Source: get_mj_azimuth and ``(az / 45.0).round`` (Ruby rounds halves up).
    """
    az = azimuth_deg - 180.0
    if az < 0:
        az += 360.0
    return int(math.floor(az / 45.0 + 0.5))


def storm_adjusted(u_factor: float, shgc: float, storm: Optional[str]) -> tuple[float, float]:
    """U-factor and SHGC of a window with a storm window added.

    Source: Constructions.get_ufactor_shgc_adjusted_by_storms.
    """
    if storm is None:
        return u_factor, shgc
    if storm == "clear":
        reduction, shgc_corr = max(0.6435 * u_factor - 0.1533, 0.0), 0.9
    elif storm == "low_e":
        reduction, shgc_corr = max(0.766 * u_factor - 0.1532, 0.0), 0.8
    else:
        raise ValueError(f"Unknown storm window type: {storm}")
    return u_factor - reduction, shgc * shgc_corr


def glass_description(u_factor: float, shgc: float, glass_layers: Optional[int] = None,
                      glass_type: Optional[str] = None) -> str:
    """Glazing category used by the interior-shading table.

    Source: get_window_interior_shading_coefficient ("Estimate based U-factor/SHGC").
    """
    if glass_layers is None or glass_type is None:
        if u_factor >= 0.85:  # single pane
            if shgc >= (0.74 + 0.5) / 2:
                return "1P Clear"
            return "1P Heat Absorbing" if shgc >= (0.5 + 0.44) / 2 else "1P Reflective"
        if u_factor >= 0.30:  # double pane
            if shgc >= (0.64 + 0.55) / 2:
                return "2P Clear"
            if shgc >= (0.55 + 0.48) / 2:
                return "2P Low-e Option 1"
            if shgc >= (0.48 + 0.43) / 2:
                return "2P Low-e Option 2"
            return "2P Heat Absorbing" if shgc >= (0.43 + 0.33) / 2 else "2P Low-e Option 3"
        return "3P Clear" if shgc >= (0.59 + 0.30) / 2 else "3P Heat Absorbing"
    if glass_type in ("reflective", "tinted_reflective"):
        return f"{glass_layers}P Reflective"
    if glass_type == "tinted":
        return f"{glass_layers}P Heat Absorbing"
    if glass_layers == 2:
        if glass_type == "low_e_low_solar":
            return "2P Low-e Option 3"
        if glass_type == "low_e":
            return "2P Low-e Option 2"
        if glass_type == "low_e_high_solar":
            return "2P Low-e Option 1"
    return f"{glass_layers}P Clear"


def interior_shading_coefficient(window) -> float:
    """Interior shading coefficient (1 = no shading) for a window.

    Source: process_load_windows_skylights (choice between table and direct
    value) and get_window_interior_shading_coefficient.
    """
    kind = window.interior_shading_type
    if kind is None or kind == "other":
        return window.interior_shading_coefficient
    if kind == "none":
        return 1.0
    glass = glass_description(window.u_factor, window.shgc, window.glass_layers, window.glass_type)
    isc = T.INTERIOR_SHADING_COEFF[glass][T.INTERIOR_SHADING_COLUMNS.index(kind)]
    covered = window.interior_shading_coverage
    isc = covered * isc + (1.0 - covered) * 1.0
    if kind.endswith("blinds"):
        if window.blinds_position == "open":
            isc = 1.0
        elif window.blinds_position == "half_open":
            isc *= T.BLINDS_HALF_OPEN_MULTIPLIER
    return round(isc, 3)


def exterior_shading(window) -> tuple[float, Optional[float]]:
    """(exterior shading coefficient, solar-screen coefficient or None).

    Source: process_load_windows_skylights (window_esc, screen_sc).
    """
    esc = 1.0
    if window.insect_screen == "interior":
        esc = 1.0 - 0.1 * window.insect_screen_coverage
    elif window.insect_screen == "exterior":
        esc = 1.0 - 0.2 * window.insect_screen_coverage
    screen_sc = None
    if window.exterior_shading_type in ("solar_screens", "solar_film"):
        screen_sc = 0.25
    elif window.exterior_shading_coefficient is not None:
        esc *= window.exterior_shading_coefficient
    return esc, screen_sc


def _overhang_slm(orient: int, latitude: float, hr: Optional[int]) -> float:
    """Shade line multiplier: ft of shadow per ft of overhang depth."""
    if hr is None:
        return interp_table(T.SLM_AVG_LATS, T.SLM_AVG[orient], latitude)
    period = hr // 3  # hours 8-10 -> 09:00, 11-13 -> noon, 14-16 -> 15:00, 17-19 -> 18:00
    return interp_table(T.SLM_HR_LATS, [row[period] for row in T.SLM_HR[orient]], latitude)


def window_cooling_htm(*, latitude: float, azimuth_deg: float, u_factor: float, shgc: float,
                       isc: float, esc: float = 1.0, screen_sc: Optional[float] = None,
                       ctd_f: float, daily_range_index: int, hr: Optional[int] = None,
                       overhang_depth_ft: float = 0.0, overhang_to_top_ft: float = 0.0,
                       overhang_to_bottom_ft: float = 0.0) -> float:
    """Cooling HTM (Btu/h-ft2) of a window.

    ``hr=None`` gives the average-load-procedure value; ``hr`` 0..11 gives the
    value for clock hour 8+hr (used for the hourly fenestration curve).

    Source: process_load_windows_skylights. For the window's direction d and for
    a fully shaded (north) window n:

        HTM = (PSF * CLF * SHGC * ISC / 0.87 + U * CTD) * ESC

    then a solar screen or an overhang blends HTM_d toward HTM_n.
    """
    orient = orientation_index(azimuth_deg)
    shaded = isc < 1
    if hr is None:
        clf = T.CLF_AVG_SHADE if shaded else T.CLF_AVG_NO_SHADE
        clf_d, clf_n = clf[orient], clf[T.NORTH_INDEX]
        ctd_adj = ctd_f
    else:
        clf = T.CLF_HR_SHADE if shaded else T.CLF_HR_NO_SHADE
        clf_d, clf_n = clf[orient][hr], clf[T.NORTH_INDEX][hr]
        ctd_adj = ctd_f + T.HTA[daily_range_index][hr]
    psf_d = interp_table(T.PSF_LATS, T.PSF[orient], latitude)
    psf_n = interp_table(T.PSF_LATS, T.PSF[T.NORTH_INDEX], latitude)
    htm_d = (psf_d * clf_d * shgc * isc / 0.87 + u_factor * ctd_adj) * esc
    htm_n = (psf_n * clf_n * shgc * isc / 0.87 + u_factor * ctd_adj) * esc

    if screen_sc is not None:
        return (htm_d - htm_n) * screen_sc + htm_n
    if overhang_depth_ft > 0:
        shade_line_ft = _overhang_slm(orient, latitude, hr) * overhang_depth_ft
        if shade_line_ft < overhang_to_top_ft:
            return htm_d  # shadow does not reach the glass
        if shade_line_ft < overhang_to_bottom_ft:
            height = overhang_to_bottom_ft - overhang_to_top_ft
            frac_shaded = (shade_line_ft - overhang_to_top_ft) / height
            return frac_shaded * htm_n + (1.0 - frac_shaded) * htm_d
        return htm_n  # fully shaded
    return htm_d


def skylight_u_effective(sky) -> float:
    """Skylight U-factor including curb and shaft losses, per ft2 of skylight.

    Source: process_load_windows_skylights (u_eff_skylight).
    """
    u, _ = storm_adjusted(sky.u_factor, sky.shgc, sky.storm)
    if sky.curb_area_ft2 is not None and sky.curb_r_value is not None:
        u += (1.0 / sky.curb_r_value) * (sky.curb_area_ft2 / sky.area_ft2)
    if sky.shaft_area_ft2 is not None and sky.shaft_r_value is not None:
        u += (1.0 / sky.shaft_r_value) * (sky.shaft_area_ft2 / sky.area_ft2)
    return u


def skylight_cooling_htm(*, latitude: float, azimuth_deg: float, pitch: float, u_effective: float,
                         shgc: float, isc: float, ctd_f: float, daily_range_index: int,
                         hr: Optional[int] = None) -> float:
    """Cooling HTM (Btu/h-ft2) of a skylight on a roof of the given pitch (rise/12).

    Source: process_load_windows_skylights:
        HTM = (cos(tilt) * PSF_horiz * CLF_horiz + sin(tilt) * PSF_d * CLF_d)
              * SHGC * ISC / 0.87 + U_eff * (CTD + 15)
    """
    orient = orientation_index(azimuth_deg)
    tilt = math.atan(pitch / 12.0)
    shaded = isc < 1
    if hr is None:
        clf_d = (T.CLF_AVG_SHADE if shaded else T.CLF_AVG_NO_SHADE)[orient]
        clf_h = T.CLF_AVG_SHADE_HORIZ if shaded else T.CLF_AVG_NO_SHADE_HORIZ
        ctd_adj = ctd_f
    else:
        clf_d = (T.CLF_HR_SHADE if shaded else T.CLF_HR_NO_SHADE)[orient][hr]
        clf_h = (T.CLF_HR_SHADE_HORIZ if shaded else T.CLF_HR_NO_SHADE_HORIZ)[hr]
        ctd_adj = ctd_f + T.HTA[daily_range_index][hr]
    psf_d = interp_table(T.PSF_LATS, T.PSF[orient], latitude)
    psf_h = interp_table(T.PSF_LATS, T.PSF_HORIZ, latitude)
    sol_h = math.cos(tilt) * psf_h * clf_h
    sol_v = math.sin(tilt) * psf_d * clf_d
    return (sol_h + sol_v) * (shgc * isc / 0.87) + u_effective * (ctd_adj + 15.0)


def aed_excursion(hourly_loads_btuh: Sequence[float]) -> float:
    """Adequate-exposure-diversity excursion (Btu/h): how far the peak hourly
    fenestration load rises above 1.3 x the daily average.

    Source: HVACSizing.calculate_aed_excursion.
    """
    average = sum(hourly_loads_btuh) / len(hourly_loads_btuh)
    return max(0.0, max(hourly_loads_btuh) - T.AED_EXCURSION_LIMIT * average)
