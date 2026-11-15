# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/weather.rb (process_epw,
# get_design_info_from_epw, calc_design_info, calc_shallow_ground_temperatures,
# calc_ashrae_622_wsf) and defaults.rb (Manual-J-input defaults).
"""Design conditions from an EPW weather file."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import psychro
from .model import DesignConditions

_WSF_CSV = Path(__file__).resolve().parents[2] / "data" / "ashrae622_wsf.csv"


@dataclass
class Weather:
    city: str
    wmo: str
    latitude_deg: float
    longitude_deg: float
    elevation_ft: float
    heating_drybulb_f: float  # 99 % heating design drybulb
    cooling_drybulb_f: float  # 1 % cooling design drybulb
    daily_temp_range_f: float
    cooling_humidity_ratio: float  # lb/lb at cooling design drybulb and coincident wetbulb
    annual_avg_drybulb_f: float
    monthly_avg_drybulb_f: list[float]
    shallow_ground_monthly_f: list[float]
    wsf: float


def daily_range_class(daily_temp_range_f: float) -> str:
    """Source: HVACSizing.determine_daily_temperature_range_class."""
    if daily_temp_range_f < 16.0:
        return "low"
    return "high" if daily_temp_range_f > 25.0 else "medium"


def shallow_ground_temps_f(annual_avg_f: float, monthly_avg_f: list[float], latitude_deg: float) -> list[float]:
    """Monthly shallow ground temperatures (F). Source: calc_shallow_ground_temperatures."""
    amon = [15.0, 46.0, 74.0, 95.0, 135.0, 166.0, 196.0, 227.0, 258.0, 288.0, 319.0, 349.0]
    po, dif, p = 0.6, 0.025, 8760.0
    beta = math.sqrt(math.pi / (p * dif)) * 10.0
    x, s, co = math.exp(-beta), math.sin(beta), math.cos(beta)
    gm = math.sqrt((x**2 - 2.0 * x * co + 1.0) / (2.0 * beta**2))
    phi = math.atan((1.0 - x * (co + s)) / (1.0 - x * (co - s)))
    bo = (max(monthly_avg_f) - min(monthly_avg_f)) * 0.5
    temps = []
    for day in amon:
        theta = day * 24.0
        # "+ 460.0 ... R to F" reproduces the reference (a 0.33 F offset).
        temps.append(annual_avg_f - bo * math.cos(2.0 * math.pi / p * theta - po - phi) * gm + 460.0 - 459.67)
    if latitude_deg < 0:
        temps = temps[6:] + temps[:6]
    return temps


def calc_wsf(drybulb_c: list[float], windspeed_m_s: list[float]) -> float:
    """ASHRAE 62.2 weather and shielding factor computed from hourly data, for
    stations not in the lookup table. Source: calc_ashrae_622_wsf."""
    c_d, t_indoor, n, s, delta_p, u_min = 1.0, 22.0, 0.67, 0.7, 4.0, 1.0
    ela, cfa, h, g, c_s, c_w, roe = 0.074, 185.0, 2.5, 0.48, 0.069, 0.142, 1.2
    c = c_d * ela * (2 / roe) ** 0.5 * delta_p ** (0.5 - n)
    taus, prev = [], 0.0
    for db, ws in zip(drybulb_c, windspeed_m_s):
        q_s = c * c_s * abs(t_indoor - db) ** n
        q_w = c * c_w * (s * g * max(ws, u_min)) ** (2 * n)
        ach = 3600.0 * (q_s**2 + q_w**2) ** 0.5 / (h * cfa)
        prev = (1 - math.exp(-ach)) / ach + prev * math.exp(-ach)
        taus.append(prev)
    tau = sum(taus) / len(taus)
    return round((cfa / ela) / (1000.0 * tau), 2)


def lookup_wsf(wmo: str, csv_path: Path = _WSF_CSV) -> Optional[float]:
    if not csv_path.exists():
        return None
    wsf = None
    with open(csv_path, newline="") as f:
        for row in csv.reader(f):
            if row and row[0] == wmo:
                wsf = float(row[1])
    return None if wsf is None else round(wsf, 2)


def read_epw(path) -> Weather:
    """Read an EPW file. Source: WeatherFile#process_epw."""
    with open(path, newline="", encoding="latin-1") as f:
        rows = list(csv.reader(f))
    loc = rows[0]
    city, wmo = loc[1], loc[5]
    latitude, longitude, elevation_ft = float(loc[6]), float(loc[7]), float(loc[9]) / 0.3048
    data = [r for r in rows[8:] if len(r) > 21]
    months = [int(r[1]) for r in data]
    db = [float(r[6]) for r in data]
    rh = [float(r[8]) / 100.0 for r in data]
    ws = [float(r[21]) for r in data]

    annual_avg_f = psychro.c_to_f(sum(db) / len(db))
    monthly_f = []
    for m in range(1, 13):
        vals = [t for t, mm in zip(db, months) if mm == m]
        monthly_f.append(psychro.c_to_f(sum(vals) / len(vals)))
    p_psi = psychro.standard_pressure_psi(elevation_ft)

    design = _design_from_header(rows[1])
    if design is not None:
        heat_c, cool_c, range_c, mcwb_c = design
        heating_f, cooling_f, dtr_f = psychro.c_to_f(heat_c), psychro.c_to_f(cool_c), range_c * 1.8
        w_cool = psychro.humidity_ratio_from_wetbulb(cooling_f, psychro.c_to_f(mcwb_c), p_psi)
    else:
        # [CONFIRM] Fallback from hourly data (calc_design_info) is not ported: it needs
        # the wetbulb solver and monthly high/low averages.
        raise ValueError("EPW file has no usable DESIGN CONDITIONS header.")

    wsf = lookup_wsf(wmo)
    if wsf is None:
        wsf = calc_wsf(db, ws)
    _ = rh
    return Weather(city=city, wmo=wmo, latitude_deg=latitude, longitude_deg=longitude, elevation_ft=elevation_ft,
                   heating_drybulb_f=heating_f, cooling_drybulb_f=cooling_f, daily_temp_range_f=dtr_f,
                   cooling_humidity_ratio=w_cool, annual_avg_drybulb_f=annual_avg_f,
                   monthly_avg_drybulb_f=monthly_f,
                   shallow_ground_monthly_f=shallow_ground_temps_f(annual_avg_f, monthly_f, latitude), wsf=wsf)


def _design_from_header(row: list[str]):
    """(99 % heating DB, 1 % cooling DB, cooling DB range, 1 % coincident WB), all C.

    Source: get_design_info_from_epw (first design-condition set in the EPW header).
    """
    try:
        h = row.index("Heating")
        c = row.index("Cooling")
        return float(row[h + 3]), float(row[c + 5]), float(row[c + 2]), float(row[c + 6])
    except (ValueError, IndexError):
        return None


def design_conditions(weather: Weather, *, heating_setpoint_f: float = 70.0, cooling_setpoint_f: float = 75.0,
                      humidity_setpoint_frac: Optional[float] = None,
                      ground_conductivity_btu_h_ft_f: float = 1.0) -> DesignConditions:
    """Default design conditions for a site. Source: defaults.rb (Manual J inputs).

    Indoor humidity defaults to 50 %, or 45 % in a dry-summer climate (outdoor air
    drier than indoor air at design). Values are rounded as the reference rounds them.
    """
    p_psi = psychro.standard_pressure_psi(weather.elevation_ft)
    if humidity_setpoint_frac is None:
        humidity_setpoint_frac = 0.5
        w_in = psychro.humidity_ratio_from_rh(cooling_setpoint_f, humidity_setpoint_frac, p_psi)
        if psychro.design_grains(weather.cooling_humidity_ratio, w_in) < 0:
            humidity_setpoint_frac = 0.45
    w_in = psychro.humidity_ratio_from_rh(cooling_setpoint_f, humidity_setpoint_frac, p_psi)
    return DesignConditions(
        heating_design_temp_f=round(weather.heating_drybulb_f, 2),
        cooling_design_temp_f=round(weather.cooling_drybulb_f, 2),
        daily_temp_range=daily_range_class(weather.daily_temp_range_f),
        humidity_difference_grains=round(psychro.design_grains(weather.cooling_humidity_ratio, w_in), 1),
        latitude_deg=weather.latitude_deg,
        elevation_ft=weather.elevation_ft,
        heating_setpoint_f=heating_setpoint_f,
        cooling_setpoint_f=cooling_setpoint_f,
        humidity_setpoint_frac=humidity_setpoint_frac,
        ground_conductivity_btu_h_ft_f=ground_conductivity_btu_h_ft_f,
        cooling_humidity_ratio=weather.cooling_humidity_ratio,
        annual_avg_drybulb_f=weather.annual_avg_drybulb_f,
        ground_temp_winter_f=min(weather.shallow_ground_monthly_f),
        ground_temp_summer_f=max(weather.shallow_ground_monthly_f),
        wsf=weather.wsf,
    )
