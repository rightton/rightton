"""Weather processing: hand calculations on a small synthetic EPW file."""

import math

import pytest
from conftest import approx
from rightton import psychro, weather

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def write_epw(path, drybulb_c, rh_pct=50.0, wind=3.0, design_header=True, wmo="999999", elevation_m=304.8):
    """drybulb_c: function of the hour index (0..8759)."""
    lines = [f"LOCATION,Testville,XX,USA,TEST,{wmo},40.0,-90.0,-6.0,{elevation_m}"]
    if design_header:
        # 99 % heating -10 C; cooling: range 12 C, 1 % drybulb 33 C with 23 C coincident wetbulb
        lines.append("DESIGN CONDITIONS,1,Test,,Heating,1,-12,-10,0,0,0,0,0,0,0,0,0,0,0,0,"
                     "Cooling,7,12,34,24,33,23,32,22,0,0")
    else:
        lines.append("DESIGN CONDITIONS,0")
    lines += ["TYPICAL/EXTREME PERIODS,0", "GROUND TEMPERATURES,0", "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
              "COMMENTS 1,", "COMMENTS 2,", "DATA PERIODS,1,1,Data,Sunday,1/1,12/31"]
    i = 0
    for month, days in enumerate(DAYS_IN_MONTH, start=1):
        for day in range(1, days + 1):
            for hour in range(1, 25):
                row = [2001, month, day, hour, 0, "x", drybulb_c(i), 0, rh_pct, 101325] + [0] * 11 + [wind] + [0] * 13
                lines.append(",".join(str(v) for v in row))
                i += 1
    path.write_text("\n".join(lines) + "\n")
    return path


def test_daily_range_class():
    assert weather.daily_range_class(15.9) == "low"
    assert weather.daily_range_class(16.0) == "medium"
    assert weather.daily_range_class(25.0) == "medium"
    assert weather.daily_range_class(25.1) == "high"


def test_read_epw_with_design_header(tmp_path):
    wx = weather.read_epw(write_epw(tmp_path / "t.epw", lambda i: 10.0))
    assert (wx.city, wx.wmo, wx.latitude_deg) == ("Testville", "999999", 40.0)
    assert wx.elevation_ft == approx(1000.0)            # 304.8 m
    assert wx.heating_drybulb_f == approx(14.0)          # -10 C
    assert wx.cooling_drybulb_f == approx(91.4)          # 33 C
    assert wx.daily_temp_range_f == approx(21.6)         # 12 C x 1.8
    assert wx.annual_avg_drybulb_f == approx(50.0)       # constant 10 C
    assert wx.monthly_avg_drybulb_f == approx([50.0] * 12)
    # Humidity ratio at 91.4 F drybulb / 73.4 F wetbulb at the site pressure (formula tested in test_psychro)
    p = psychro.standard_pressure_psi(1000.0)
    assert wx.cooling_humidity_ratio == approx(psychro.humidity_ratio_from_wetbulb(91.4, 73.4, p))
    # No monthly swing: ground temperature = annual average, plus the reference's 0.33 F offset
    assert wx.shallow_ground_monthly_f == approx([50.33] * 12)


def test_shallow_ground_temperature_swing():
    # Monthly air temperatures 30..70 F -> amplitude 20 F, damped by the factor gm.
    # beta = sqrt(pi / (8760 * 0.025)) * 10 = 1.19773; x = exp(-beta) = 0.30188
    # gm = sqrt((x^2 - 2 x cos(beta) + 1) / (2 beta^2)) = sqrt((0.09113 - 0.21996 + 1) / 2.86911) = 0.55104
    # So ground temperatures swing +/- 20 * 0.55104 = 11.02 F about (50 + 0.33).
    monthly = [30, 34, 42, 50, 58, 66, 70, 66, 58, 50, 42, 34]
    temps = weather.shallow_ground_temps_f(50.0, monthly, 40.0)
    assert max(temps) <= 50.33 + 11.03
    assert min(temps) >= 50.33 - 11.03
    assert max(temps) - min(temps) == approx(2 * 11.02, rel=0.03)  # the 12 sample days nearly reach both extremes
    assert temps.index(min(temps)) in (0, 1, 2)   # coldest ground in late winter
    # Southern hemisphere: shifted six months
    assert weather.shallow_ground_temps_f(50.0, monthly, -30.0) == approx(temps[6:] + temps[:6])


def test_wsf_lookup_from_table():
    # Denver Intl AP (WMO 725650) and Miami Intl AP (722020) in data/ashrae622_wsf.csv
    assert weather.lookup_wsf("725650") == 0.59
    assert weather.lookup_wsf("722020") == 0.41
    assert weather.lookup_wsf("000000") is None


def test_wsf_calculated_for_one_hour():
    # One hour at 22 C (no stack effect) and 1 m/s wind:
    # c = 0.074 * sqrt(2 / 1.2) * 4^(0.5 - 0.67) = 0.074 * 1.29099 * 0.79004 = 0.075475
    # q_w = c * 0.142 * (0.7 * 0.48 * 1)^1.34 = 0.075475 * 0.142 * 0.231895 = 0.0024854 m3/s
    # ach = 3600 * 0.0024854 / (2.5 * 185) = 0.019345; tau = (1 - exp(-ach)) / ach = 0.990389 h
    # WSF = (185 / 0.074) / (1000 * 0.990389) = 2.5243 -> 2.52
    assert weather.calc_wsf([22.0], [1.0]) == 2.52


def test_station_not_in_table_gets_calculated_wsf(tmp_path):
    wx = weather.read_epw(write_epw(tmp_path / "t.epw", lambda i: 10.0))
    assert 0.2 < wx.wsf < 1.5


def test_design_conditions_from_hourly_data(tmp_path):
    # Drybulb rises 0.005 C every hour from -10 C; saturated air (RH 100 %) so wetbulb = drybulb.
    path = write_epw(tmp_path / "t.epw", lambda i: -10.0 + 0.005 * i, rh_pct=100.0, design_header=False)
    wx = weather.read_epw(path)
    # 99 % heating: 89th-lowest hour (index 88): -10 + 0.44 = -9.56 C = 14.792 F
    assert wx.heating_drybulb_f == approx(14.792)
    # 1 % cooling: index 8673: -10 + 43.365 = 33.365 C = 92.057 F
    assert wx.cooling_drybulb_f == approx(92.057)
    # Coincident wetbulb: mean over hours within 0.5 C of 33.365 C, i.e. indices 8574..8759
    # (the year ends before the upper bound): mean index 8666.5 -> 33.3325 C = 91.9985 F
    p = psychro.standard_pressure_psi(1000.0)
    assert wx.cooling_humidity_ratio == approx(psychro.humidity_ratio_from_wetbulb(92.057, 91.9985, p), rel=1e-3)
    # Warmest month is December; each day spans 23 steps of 0.005 C = 0.115 C = 0.207 F
    assert wx.daily_temp_range_f == approx(0.207, rel=1e-3)


def test_default_design_conditions(tmp_path):
    wx = weather.read_epw(write_epw(tmp_path / "t.epw", lambda i: 10.0))
    dc = weather.design_conditions(wx)
    assert dc.heating_design_temp_f == 14.0
    assert dc.cooling_design_temp_f == 91.4
    assert dc.daily_temp_range == "medium"          # 21.6 F
    assert dc.humidity_setpoint_frac == 0.5         # outdoor air is wetter than indoor air
    p = psychro.standard_pressure_psi(1000.0)
    w_in = psychro.humidity_ratio_from_rh(75.0, 0.5, p)
    assert dc.humidity_difference_grains == pytest.approx((wx.cooling_humidity_ratio - w_in) * 7000.0, abs=0.05)
    assert dc.ground_temp_winter_f == approx(50.33)
    assert dc.latitude_deg == 40.0


def test_dry_climate_uses_45_percent_indoor_humidity(tmp_path):
    wx = weather.read_epw(write_epw(tmp_path / "t.epw", lambda i: 10.0))
    wx.cooling_humidity_ratio = 0.004  # very dry outdoor air
    dc = weather.design_conditions(wx)
    assert dc.humidity_setpoint_frac == 0.45
    assert dc.humidity_difference_grains < 0
    assert math.isclose(weather.design_conditions(wx, humidity_setpoint_frac=0.5).humidity_setpoint_frac, 0.5)
