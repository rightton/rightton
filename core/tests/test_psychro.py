"""Moist-air properties: hand calculations."""

import math

from conftest import approx
from rightton import psychro


def test_standard_pressure_sea_level_psi():
    # (1 - 0)^5.2559 atm = 1 atm = 14.692 psi (the reference's conversion factor)
    assert psychro.standard_pressure_psi(0.0) == approx(14.692)


def test_standard_pressure_at_5000_ft_psi():
    # (1 - 6.8754e-6 * 5000) = 0.965623; 0.965623^5.2559 = 0.832051 atm; x 14.692 = 12.2245 psi
    assert psychro.standard_pressure_psi(5000.0) == approx(12.2245)


def test_saturation_pressure_at_boiling_and_freezing_psi():
    # Water boils at 212 F at one standard atmosphere (14.696 psi); steam-table
    # value at 32 F is 0.0886 psi.
    assert psychro.saturation_pressure_psi(212.0) == approx(14.696, rel=2e-3)
    assert psychro.saturation_pressure_psi(32.0) == approx(0.0886, rel=5e-3)


def test_saturation_pressure_at_75_f_psi():
    # Steam-table value at 75 F: 0.4298 psi
    assert psychro.saturation_pressure_psi(75.0) == approx(0.4298, rel=2e-3)


def test_humidity_ratio_from_rh_lb_per_lb():
    # 75 F, 50 % RH, 14.692 psi: pw = 0.5 * 0.4298 = 0.2149 psi
    # w = 0.62198 * 0.2149 / (14.692 - 0.2149) = 0.009233 lb/lb
    assert psychro.humidity_ratio_from_rh(75.0, 0.5, 14.692) == approx(0.009233, rel=2e-3)


def test_humidity_ratio_from_wetbulb_at_saturation():
    # When wetbulb = drybulb the air is saturated: w = (18.02/28.97) * pws / (p - pws)
    # At 75 F: 0.62202 * 0.4298 / (14.692 - 0.4298) = 0.018745 lb/lb
    assert psychro.humidity_ratio_from_wetbulb(75.0, 75.0, 14.692) == approx(0.018745, rel=2e-3)


def test_humidity_ratio_from_wetbulb_below_saturation():
    # 95 F drybulb, 75 F wetbulb, 14.692 psi. w* (saturated at 75 F) = 0.018745.
    # numerator   = (1055 - (0.9991 - 0.4495) * 75) * 0.018745 - 0.2399 * (95 - 75)
    #             = (1055 - 41.22) * 0.018745 - 4.798 = 19.0033 - 4.798 = 14.2053
    # denominator = 1055 + 0.4495 * 95 - 0.9991 * 75 = 1055 + 42.7025 - 74.9325 = 1022.77
    # w = 14.2053 / 1022.77 = 0.013889 lb/lb
    assert psychro.humidity_ratio_from_wetbulb(95.0, 75.0, 14.692) == approx(0.013889, rel=3e-3)


def test_wetbulb_inverts_humidity_ratio():
    w = psychro.humidity_ratio_from_wetbulb(95.0, 75.0, 14.692)
    assert psychro.wetbulb_f(95.0, w, 14.692) == approx(75.0, rel=1e-6)


def test_wetbulb_of_saturated_air_is_drybulb():
    w_sat = psychro.humidity_ratio_from_rh(60.0, 1.0, 14.692)
    assert psychro.wetbulb_f(60.0, w_sat, 14.692) == approx(60.0, rel=1e-3)


def test_enthalpy_btu_per_lb():
    # 75 F = 23.889 C, w = 0.0093:
    # h = 1000 * (1.006 * 23.889 + 0.0093 * (2501 + 1.86 * 23.889)) = 47,705 J/kg
    # x 9.4782e-4 Btu/J x 0.45359 kg/lb = 20.509 Btu/lb (zero at 0 C, as in the reference)
    assert psychro.enthalpy_btu_per_lb(75.0, 0.0093) == approx(20.509)


def test_air_density_lb_per_ft3():
    # 1 atm, 70 F: 2.719 Btu/ft3 / ((1.9858 / 28.97) Btu/lb-R * 529.67 R) = 0.07489 lb/ft3
    assert psychro.air_density_lb_per_ft3(14.692, 70.0) == approx(0.07489, rel=2e-4)


def test_design_grains():
    # (0.012 - 0.009) lb/lb * 7000 grains/lb = 21 grains
    assert psychro.design_grains(0.012, 0.009) == approx(21.0)


def test_temperature_conversions():
    assert psychro.f_to_c(212.0) == approx(100.0)
    assert psychro.c_to_f(-40.0) == approx(-40.0)
    assert psychro.f_to_r(0.0) == approx(459.67)
    assert math.isclose(psychro.PSYCH_MASS_RATIO, 18.02 / 28.97)
