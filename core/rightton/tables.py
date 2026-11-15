# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb.
"""Numeric tables used by the design-load method.

ORIGIN TAGS. Every value in this file was taken from the OpenStudio-HPXML source
code, never from the ACCA book. Each table is tagged with:

* ``origin``: where OpenStudio-HPXML says the numbers come from (NREL transcribed
  many of them from the ACCA 8th-edition residential load manual, abbreviated
  "MJ8" below, and published them under its BSD-style license);
* ``via``: the function in hvac_sizing.rb that the values were ported from.

The tags exist so any table can later be replaced with an independently derived one.
"""

from __future__ import annotations

# Orientation index used by all fenestration tables: 0=S, 1=SW, 2=W, 3=NW, 4=N,
# 5=NE, 6=E, 7=SE, 8=S (repeated so a rounded azimuth of 360 lands on S).
ORIENTATIONS = ("S", "SW", "W", "NW", "N", "NE", "E", "SE", "S")
NORTH_INDEX = 4

# origin: MJ8 Table 3D-3 (average cooling load factors, no internal shading)
# via: process_load_windows_skylights (clf_avg_nois, clf_avg_nois_horiz)
CLF_AVG_NO_SHADE = (0.24, 0.35, 0.38, 0.4, 0.48, 0.4, 0.38, 0.35, 0.24)
CLF_AVG_NO_SHADE_HORIZ = 0.68

# origin: MJ8 Table 3D-3 (average cooling load factors, with internal shading)
# via: process_load_windows_skylights (clf_avg_is, clf_avg_is_horiz)
CLF_AVG_SHADE = (0.18, 0.29, 0.32, 0.32, 0.29, 0.32, 0.32, 0.29, 0.18)
CLF_AVG_SHADE_HORIZ = 0.52

# origin: MJ8 Table A11-5 (hourly CLF, no internal shading), hours 8..20
# via: process_load_windows_skylights (clf_hr_nois, clf_hr_nois_horiz)
CLF_HR_NO_SHADE = (
    (0.14, 0.22, 0.34, 0.48, 0.59, 0.65, 0.65, 0.59, 0.50, 0.43, 0.36, 0.28, 0.22),  # S
    (0.10, 0.12, 0.14, 0.16, 0.24, 0.36, 0.49, 0.60, 0.66, 0.66, 0.58, 0.43, 0.33),  # SW
    (0.08, 0.10, 0.11, 0.12, 0.14, 0.20, 0.32, 0.45, 0.57, 0.64, 0.61, 0.44, 0.34),  # W
    (0.10, 0.12, 0.14, 0.16, 0.17, 0.19, 0.23, 0.33, 0.47, 0.59, 0.60, 0.43, 0.33),  # NW
    (0.48, 0.56, 0.63, 0.71, 0.76, 0.80, 0.82, 0.82, 0.79, 0.75, 0.69, 0.61, 0.48),  # N
    (0.51, 0.51, 0.45, 0.39, 0.36, 0.33, 0.31, 0.28, 0.26, 0.23, 0.19, 0.15, 0.12),  # NE
    (0.51, 0.57, 0.57, 0.50, 0.42, 0.37, 0.32, 0.29, 0.25, 0.22, 0.19, 0.15, 0.12),  # E
    (0.43, 0.55, 0.62, 0.63, 0.57, 0.48, 0.42, 0.37, 0.33, 0.28, 0.24, 0.19, 0.15),  # SE
    (0.14, 0.22, 0.34, 0.48, 0.59, 0.65, 0.65, 0.59, 0.50, 0.43, 0.36, 0.28, 0.22),  # S
)
CLF_HR_NO_SHADE_HORIZ = (0.24, 0.36, 0.48, 0.58, 0.66, 0.72, 0.74, 0.73, 0.67, 0.59, 0.47, 0.37, 0.29)

# origin: MJ8 Table A11-6 (hourly CLF, with internal shading), hours 8..20
# via: process_load_windows_skylights (clf_hr_is, clf_hr_is_horiz)
CLF_HR_SHADE = (
    (0.23, 0.38, 0.58, 0.75, 0.83, 0.80, 0.68, 0.50, 0.35, 0.27, 0.19, 0.11, 0.09),  # S
    (0.14, 0.16, 0.19, 0.22, 0.38, 0.59, 0.75, 0.83, 0.81, 0.69, 0.45, 0.16, 0.12),  # SW
    (0.11, 0.13, 0.15, 0.16, 0.17, 0.31, 0.53, 0.72, 0.82, 0.81, 0.61, 0.16, 0.12),  # W
    (0.14, 0.17, 0.19, 0.20, 0.21, 0.22, 0.30, 0.52, 0.73, 0.82, 0.69, 0.16, 0.12),  # NW
    (0.65, 0.73, 0.80, 0.86, 0.89, 0.89, 0.86, 0.82, 0.75, 0.78, 0.91, 0.24, 0.18),  # N
    (0.74, 0.58, 0.37, 0.29, 0.27, 0.26, 0.24, 0.22, 0.20, 0.16, 0.12, 0.06, 0.05),  # NE
    (0.80, 0.76, 0.62, 0.41, 0.27, 0.24, 0.22, 0.20, 0.17, 0.14, 0.11, 0.06, 0.05),  # E
    (0.74, 0.81, 0.79, 0.68, 0.49, 0.33, 0.28, 0.25, 0.22, 0.18, 0.13, 0.08, 0.07),  # SE
    (0.23, 0.38, 0.58, 0.75, 0.83, 0.80, 0.68, 0.50, 0.35, 0.27, 0.19, 0.11, 0.09),  # S
)
CLF_HR_SHADE_HORIZ = (0.44, 0.59, 0.72, 0.81, 0.85, 0.85, 0.81, 0.71, 0.58, 0.42, 0.25, 0.14, 0.12)

# origin: MJ8 Table A11-7 (mid-summer hourly shade line multipliers)
# via: process_load_windows_skylights (slm_hr_lats, slm_hr)
# Indexed [orientation][latitude][period]; periods are 09:00, noon, 15:00, 18:00.
SLM_HR_LATS = (28.0, 34.0, 40.0, 46.0, 52.0, 60.0)  # degrees
SLM_HR = (
    ((5.3, 3.7, 5.3, 0.0), (3.2, 2.5, 3.2, 0.0), (2.2, 1.9, 2.2, 0.2), (1.8, 1.5, 1.8, 0.0), (1.4, 1.2, 1.4, 0.0), (1.1, 0.9, 1.1, 0.0)),  # S
    ((0.0, 5.0, 1.2, 0.2), (0.0, 3.4, 1.1, 0.2), (0.0, 2.6, 0.9, 0.1), (0.0, 2.1, 0.8, 0.2), (0.0, 1.7, 0.8, 0.3), (0.0, 1.3, 0.7, 0.3)),  # SW
    ((0.0, 0.0, 1.0, 0.1), (0.0, 0.0, 1.0, 0.1), (0.0, 0.0, 1.0, 0.1), (0.0, 0.0, 0.9, 0.2), (0.0, 0.0, 0.9, 0.2), (0.0, 0.0, 0.8, 0.2)),  # W
    ((0.0, 0.0, 1.9, 0.1), (0.0, 0.0, 2.1, 0.1), (0.0, 0.0, 2.4, 0.0), (0.0, 0.0, 2.6, 0.2), (0.0, 0.0, 3.1, 0.2), (0.0, 0.0, 3.9, 0.2)),  # NW
    ((0.0, 0.0, 0.0, 0.5), (0.0, 0.0, 0.0, 0.7), (0.0, 0.0, 0.0, 0.8), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.3), (0.0, 0.0, 0.0, 1.8)),  # N
    ((1.9, 0.0, 0.0, 0.0), (2.1, 0.0, 0.0, 0.0), (2.4, 0.0, 0.0, 0.0), (2.6, 0.0, 0.0, 0.0), (3.1, 0.0, 0.0, 0.0), (3.9, 0.0, 0.0, 0.0)),  # NE
    ((1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.9, 0.0, 0.0, 0.0), (0.9, 0.0, 0.0, 0.0), (0.8, 0.0, 0.0, 0.0)),  # E
    ((1.2, 5.0, 0.0, 0.0), (1.1, 3.4, 0.0, 0.0), (0.9, 2.6, 0.0, 0.0), (0.8, 2.1, 0.0, 0.0), (0.8, 1.7, 0.0, 0.0), (0.7, 1.3, 0.0, 0.0)),  # SE
    ((5.3, 3.7, 5.3, 0.0), (3.2, 2.5, 3.2, 0.0), (2.2, 1.9, 2.2, 0.2), (1.8, 1.5, 1.8, 0.0), (1.4, 1.2, 1.4, 0.0), (1.1, 0.9, 1.1, 0.0)),  # S
)

# origin: MJ8 Table 3E-1 (mid-summer average shade line multipliers)
# via: process_load_windows_skylights (alm_avg_lats, slm_avg)
SLM_AVG_LATS = (25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
SLM_AVG = (
    (10.1, 5.40, 3.53, 2.60, 2.05, 1.70),  # S
    (1.89, 1.63, 1.41, 1.25, 1.13, 1.01),  # SW
    (0.83, 0.83, 0.82, 0.81, 0.80, 0.79),  # W
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),  # NW
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),  # N
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),  # NE
    (0.83, 0.83, 0.82, 0.81, 0.80, 0.79),  # E
    (1.89, 1.63, 1.41, 1.25, 1.13, 1.01),  # SE
    (10.1, 5.40, 3.53, 2.60, 2.05, 1.70),  # S
)

# origin: MJ8 Table 3D-2 (mid-summer peak solar factors, Btu/h-ft2)
# via: process_load_windows_skylights (psf_lats, psf, psf_horiz)
PSF_LATS = (28.0, 34.0, 40.0, 46.0, 52.0, 60.0)
PSF = (
    (91.0, 121.0, 149.0, 173.0, 193.0, 211.0),  # S
    (172.0, 185.0, 196.0, 205.0, 212.0, 217.0),  # SW
    (220.0, 219.0, 216.0, 213.0, 208.0, 199.0),  # W
    (149.0, 140.0, 135.0, 130.0, 124.0, 114.0),  # NW
    (38.0, 37.0, 35.0, 34.0, 32.0, 28.0),  # N
    (149.0, 140.0, 135.0, 130.0, 124.0, 114.0),  # NE
    (220.0, 219.0, 216.0, 213.0, 208.0, 199.0),  # E
    (172.0, 185.0, 196.0, 205.0, 212.0, 217.0),  # SE
    (91.0, 121.0, 149.0, 173.0, 193.0, 211.0),  # S
)
PSF_HORIZ = (272.0, 261.0, 247.0, 230.0, 208.0, 176.0)

# origin: MJ8 Table A11-3 (hourly temperature adjustment, F), hours 8..20
# via: process_load_windows_skylights (hta); rows: low, medium, high daily range
HTA = (
    (-6.3, -5.0, -3.7, -2.5, -1.5, -0.7, -0.2, 0.0, -0.2, -0.7, -1.5, -2.5, -3.7),
    (-12.6, -10.0, -7.4, -5.0, -2.9, -1.3, -0.3, 0.0, -0.3, -1.3, -2.9, -5.0, -7.4),
    (-18.9, -15.0, -11.1, -7.5, -4.4, -2.0, -0.5, 0.0, -0.5, -2.0, -4.4, -7.5, -11.1),
)

# origin: OS-HPXML ("CLTD adjustments based on daily temperature range")
# via: process_site_calcs_and_design_temps (mj.daily_range_temp_adjust); low/medium/high
DAILY_RANGE_TEMP_ADJUST_F = (4.0, 0.0, -5.0)
DAILY_RANGE_INDEX = {"low": 0, "medium": 1, "high": 2}

# origin: "CLTD values derived from Table 4A Construction 11 table" (MJ8)
# via: process_load_doors; added to the cooling temperature difference, by daily range
DOOR_CLTD_ADDER_F = (15.0, 11.0, 6.0)

# origin: MJ8 Figure A12-8 (base CLTD for sunlit walls, F); intermediate groups
#         by linear interpolation (done by NREL)
# via: process_load_walls (cltd_base_sun)
WALL_CLTD_BASE_SUN_F = {
    "G": 38.0, "F-G": 34.95, "F": 31.9, "E-F": 29.45, "E": 27.0, "D-E": 24.5,
    "D": 22.0, "C-D": 21.25, "C": 20.5, "B-C": 19.65, "B": 18.8,
}

# origin: MJ8 Figure A12-12 (Table 4A group letter -> ASHRAE wall group)
# via: get_ashrae_wall_group
TABLE_4A_TO_ASHRAE_GROUP = {
    "A": "G", "B": "F-G", "C": "F", "D": "E-F", "E": "E", "F": "D-E",
    "G": "D", "H": "C-D", "I": "C", "J": "B-C", "K": "B",
}

# origin: MJ8 Table 4B notes pg 348 (light) and Appendix 12 pg 519 (medium)
# via: process_load_walls (color_multiplier)
WALL_COLOR_MULTIPLIER = {"light": 0.65, "medium": 0.83, "dark": 1.0}

# origin: MJ8 Figure A12-16 (base CLTD for roof-joist-ceiling sandwiches, F)
# via: process_load_roofs; (max assembly R-value, CLTD), last entry is "above R-30"
ROOF_CLTD_BY_R = ((6.0, 50.0), (13.0, 45.0), (15.0, 38.0), (21.0, 31.0), (30.0, 30.0), (float("inf"), 27.0))

# origin: MJ8 Figure A12-14 (unconditioned attic cooling design temperatures, F,
#         at a 95 F outdoor design temperature)
# via: get_design_temp_cooling
ATTIC_UNVENTED_TEMP_F = {False: 150.0, True: 130.0}  # keyed by radiant barrier
# Vented attic: keyed [radiant_barrier][roof material class][color class]
ATTIC_VENTED_TEMP_F = {
    False: {
        "shingles": {"dark": 130.0, "medium": 120.0, "white": 120.0},
        "wood": {"dark": 120.0, "medium": 120.0, "white": 120.0},
        "metal": {"dark": 130.0, "medium": 120.0, "white": 95.0},
        "tile": {"dark": 110.0, "medium": 105.0, "white": 95.0},
    },
    True: {
        "shingles": {"dark": 120.0, "medium": 110.0, "white": 110.0},
        "wood": {"dark": 110.0, "medium": 110.0, "white": 110.0},
        "metal": {"dark": 120.0, "medium": 110.0, "white": 95.0},
        "tile": {"dark": 105.0, "medium": 100.0, "white": 95.0},
    },
}
# Roof type -> material class used by the attic table above.
ROOF_MATERIAL_CLASS = {
    "asphalt_shingles": "shingles", "shingles": "shingles", "wood_shingles": "wood",
    "metal": "metal", "plastic_rubber": "metal", "eps": "metal",
    "clay_tile": "tile", "concrete": "tile",
}
# Roof color -> color class.
ROOF_COLOR_CLASS = {
    "dark": "dark", "medium_dark": "dark", "medium": "medium", "medium_light": "medium",
    "light": "medium", "white": "white", "reflective": "white",
}

# origin: MJ8 Table 4C (closed garage temperature rise over outdoor design, F);
#         (garage under conditioned space, garage not under), by daily range
# via: get_design_temp_cooling / get_design_temp_heating
GARAGE_COOL_ADDER_F = ((11.0, 22.0), (6.0, 17.0), (1.0, 12.0))
GARAGE_HEAT_ADDER_UNDER_CONDITIONED_F = 5.0

# origin: MJ8 Tables 5D/5E (stack and wind coefficients, wind speed footnotes)
# via: process_load_infiltration_ventilation
INFIL_STACK_COEFF_PER_STORY = 0.015
INFIL_WIND_COEFF_BASE = 0.0065
INFIL_WIND_COEFF_PER_SHIELD_CLASS = 0.00266
INFIL_WIND_STORY_EXPONENT = 0.4
INFIL_WINDSPEED_COOLING_MPH = 7.5
INFIL_WINDSPEED_HEATING_MPH = 15.0
FIREPLACE_HEATING_CFM = 20.0  # origin: OS-HPXML assumption, 1 fireplace of average leakiness

# origin: MJ8 Table 5A (default air changes per hour, single-family detached)
# via: get_mj_default_ach_values; rows by floor-area bin (<=900, <=1500, <=2000, <=3000, >3000 ft2)
ACH_FLOOR_AREA_BINS_FT2 = (900.0, 1500.0, 2000.0, 3000.0)
ACH_SFD_HEATING = (
    {"very_tight": (0.21, 0.16, 0.14, 0.11, 0.10), "tight": (0.41, 0.31, 0.26, 0.22, 0.19),
     "average": (0.61, 0.45, 0.38, 0.32, 0.28), "leaky": (0.95, 0.70, 0.59, 0.49, 0.43),
     "very_leaky": (1.29, 0.94, 0.80, 0.66, 0.58)},  # single story
    {"very_tight": (0.27, 0.20, 0.18, 0.15, 0.13), "tight": (0.53, 0.39, 0.34, 0.28, 0.25),
     "average": (0.79, 0.58, 0.50, 0.41, 0.37), "leaky": (1.23, 0.90, 0.77, 0.63, 0.56),
     "very_leaky": (1.67, 1.22, 1.04, 0.85, 0.75)},  # two story
)
ACH_SFD_COOLING = (
    {"very_tight": (0.11, 0.08, 0.07, 0.06, 0.05), "tight": (0.22, 0.16, 0.14, 0.11, 0.10),
     "average": (0.32, 0.23, 0.20, 0.16, 0.15), "leaky": (0.50, 0.36, 0.31, 0.25, 0.23),
     "very_leaky": (0.67, 0.49, 0.42, 0.34, 0.30)},
    {"very_tight": (0.14, 0.11, 0.09, 0.08, 0.07), "tight": (0.28, 0.21, 0.18, 0.15, 0.13),
     "average": (0.41, 0.30, 0.26, 0.21, 0.19), "leaky": (0.64, 0.47, 0.40, 0.33, 0.29),
     "very_leaky": (0.87, 0.64, 0.54, 0.44, 0.39)},
)
# origin: MJ8 Table 5B (attached / multifamily)
ACH_MF_HEATING = {"very_tight": (0.24, 0.18, 0.15, 0.13, 0.12), "tight": (0.47, 0.34, 0.29, 0.25, 0.22),
                  "average": (0.69, 0.50, 0.43, 0.36, 0.32), "leaky": (1.08, 0.78, 0.67, 0.55, 0.49),
                  "very_leaky": (1.46, 1.06, 0.91, 0.74, 0.65)}
ACH_MF_COOLING = {"very_tight": (0.13, 0.09, 0.08, 0.07, 0.06), "tight": (0.25, 0.18, 0.16, 0.13, 0.12),
                  "average": (0.36, 0.27, 0.23, 0.19, 0.17), "leaky": (0.57, 0.42, 0.36, 0.29, 0.26),
                  "very_leaky": (0.77, 0.56, 0.48, 0.39, 0.34)}

# origin: MJ8 Table 3D-4 (interior shading coefficients); columns are dark/medium/light
#         blinds, dark/medium/light shades, dark/medium/light curtains
# via: get_window_interior_shading_coefficient
INTERIOR_SHADING_COLUMNS = (
    "dark_blinds", "medium_blinds", "light_blinds", "dark_shades", "medium_shades",
    "light_shades", "dark_curtains", "medium_curtains", "light_curtains",
)
INTERIOR_SHADING_COEFF = {
    "1P Clear": (0.68, 0.60, 0.51, 0.80, 0.55, 0.40, 0.80, 0.60, 0.35),
    "1P Heat Absorbing": (0.81, 0.75, 0.69, 0.66, 0.52, 0.44, 0.81, 0.66, 0.52),
    "1P Reflective": (0.78, 0.71, 0.64, 0.89, 0.73, 0.61, 1.00, 0.75, 0.58),
    "2P Clear": (0.64, 0.59, 0.54, 0.80, 0.57, 0.46, 0.86, 0.63, 0.34),
    "2P Low-e Option 1": (0.68, 0.62, 0.57, 0.87, 0.60, 0.47, 0.93, 0.67, 0.33),
    "2P Low-e Option 2": (0.72, 0.65, 0.59, 0.77, 0.62, 0.54, 0.77, 0.62, 0.54),
    "2P Low-e Option 3": (0.85, 0.76, 0.66, 0.87, 0.77, 0.66, 0.89, 0.78, 0.67),
    "2P Heat Absorbing": (0.66, 0.59, 0.51, 0.69, 0.52, 0.43, 0.86, 0.69, 0.60),
    "2P Reflective": (0.85, 0.76, 0.66, 0.87, 0.77, 0.66, 0.89, 0.78, 0.67),
    "3P Clear": (0.64, 0.58, 0.53, 0.81, 0.56, 0.44, 0.87, 0.62, 0.31),
    "3P Heat Absorbing": (0.85, 0.74, 0.64, 0.87, 0.62, 0.50, 1.00, 0.87, 0.75),
    "3P Reflective": (0.85, 0.74, 0.64, 0.86, 0.75, 0.63, 0.87, 0.75, 0.62),
}
BLINDS_HALF_OPEN_MULTIPLIER = 1.175  # origin: MJ8 Table 3D-4 note 3

# origin: MJ8 (people gains, Btu/h per occupant); via: process_load_internal_gains
OCCUPANT_SENSIBLE_BTUH = 230.0
OCCUPANT_LATENT_BTUH = 200.0

# origin: MJ8 air-load constants (Btu/h per cfm-F and per cfm-grain), corrected for
# altitude by ACF = 1 - 0.0000308 * elevation_ft (MJ8 Table 10A equation)
# via: process_load_infiltration_ventilation, process_site_calcs_and_design_temps
SENSIBLE_AIR_FACTOR = 1.1
LATENT_AIR_FACTOR = 0.68
ALTITUDE_CORRECTION_PER_FT = 0.0000308

# origin: MJ8 Table 4A footnote (radiant floors: add 25 F to the heating
# temperature difference); via: process_load_floors, process_load_slabs
RADIANT_FLOOR_HTD_ADDER_F = 25.0

# origin: MJ8 Figure A12-6/A12-17 (crawlspace/basement partition temperature
# differences); via: process_load_floors
CRAWL_FLOOR_FACTOR = 4.0
CRAWL_VENTED_WALL_ADDER = 0.11

# origin: MJ8 AED procedure (excursion limit = 1.3 x daily average load)
# via: calculate_aed_excursion
AED_EXCURSION_LIMIT = 1.3

# origin: OS-HPXML duct regain factors (MJ8 pg 204 and Walker 1998, "Technical
# background for default values used for forced air systems in proposed ASHRAE
# Std. 152"); via: get_duct_regain_factor
# keyed [space kind][(ceiling_insulated, walls_insulated)]
DUCT_REGAIN = {
    "basement_unconditioned": {(False, False): 0.50, (False, True): 0.75, (True, False): 0.30, (True, True): 0.30},
    "crawlspace_vented": {(False, False): 0.50, (False, True): 0.66, (True, False): 0.12, (True, True): 0.17},
    "crawlspace_unvented": {(False, False): 0.60, (False, True): 0.76, (True, False): 0.16, (True, True): 0.30},
}
DUCT_REGAIN_ATTIC = 0.10
DUCT_REGAIN_GARAGE = 0.05

# origin: OS-HPXML hvac.rb (RESNET default airflow, cfm per ton of capacity)
CFM_PER_TON_FURNACE = 240.0
CFM_PER_TON_DX = 360.0

# origin: OS-HPXML airflow.rb
INFIL_PRESSURE_EXPONENT = 0.65
UNVENTED_SPACE_ACH = 0.1  # natural air changes per hour, assumption
REFERENCE_HEIGHT_FT = 8.202  # ASHRAE 62.2 reference height
