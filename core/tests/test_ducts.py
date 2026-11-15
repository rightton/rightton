"""Duct loads (ASHRAE 152 delivery effectiveness): hand calculations."""

import math

import pytest
from conftest import approx
from rightton import ducts
from rightton.model import (GROUND, OUTSIDE, BufferSpace, Building, Ceiling, DesignConditions, DistributionSystem,
                            Duct, Floor, FoundationWall, Room, Zone)


def test_airflow_cfm():
    # 240 cfm/ton * 30,000 / 12,000 = 600 cfm; 360 * 25,000 / 12,000 = 750 cfm
    assert ducts.airflow_cfm(240.0, 30000.0) == 600.0
    assert ducts.airflow_cfm(360.0, 25000.0) == 750.0
    # Rounded to a whole cfm: 360 * 10,010 / 12,000 = 300.3 -> 300
    assert ducts.airflow_cfm(360.0, 10010.0) == 300.0


def test_leaving_air_temp():
    assert ducts.leaving_air_temp_f(7500.0, 10000.0) == 54.0   # SHR 0.75
    assert ducts.leaving_air_temp_f(8250.0, 10000.0) == approx(56.0)  # SHR 0.825: halfway 54..58
    assert ducts.leaving_air_temp_f(9000.0, 10000.0) == 58.0   # SHR 0.90
    assert ducts.leaving_air_temp_f(9000.0, 8000.0) == 58.0    # negative latent: SHR capped at 1


def test_conduction_fractions():
    # 100 ft2 of R-4 duct, 600 cfm, air 0.075 lb/ft3, cp 0.2399:
    # exp(-100 / (60 * 600 * 0.075 * 0.2399 * 4)) = exp(-100 / 2590.92) = exp(-0.038596) = 0.96214
    b_s, b_r = ducts.conduction_fractions(100.0, 0.0, 4.0, math.inf, 600.0, 0.075)
    assert b_s == approx(0.96214)
    assert b_r == 1.0  # no return duct outside conditioned space


def test_leakage_factors():
    # 60 cfm supply leak and 30 cfm return leak on 600 cfm: 0.90 and 0.95
    assert ducts.leakage_factors(60.0, 30.0, 600.0) == (approx(0.9), approx(0.95))


def test_de_heating():
    # a_s 0.9, B_s 0.96, a_r 0.95, B_r 0.98, dT_s 50, dT_r 40, dT_e 55:
    # 0.864 - 0.864 * (1 - 0.931) * (40/55) - 0.9 * 0.04 * (50/55)
    # = 0.864 - 0.043357 - 0.032727 = 0.787916
    assert ducts.de_heating(0.9, 0.96, 0.95, 0.98, 50.0, 40.0, 55.0) == approx(0.787916)


def test_de_cooling():
    # a_s 0.9, 800 cfm, total load 24,000, a_r 0.95, h_r 40, h_in 28, B_r 0.98, dT_r -45,
    # B_s 0.96, leaving air 56 F, supply ducts in 120 F air, density 0.075:
    # factor  = 0.9 * 60 * 800 * 0.075 / -24000 = -0.135
    # bracket = -24000 / 3600 + 0.05 * 12 + 0.95 * 0.2399 * (-0.02) * (-45) + 0.2399 * (-0.04) * (56 - 120)
    #         = -6.66667 + 0.6 + 0.205115 + 0.614144 = -5.247408
    # DE = -0.135 * -5.247408 = 0.708400
    de = ducts.de_cooling(0.9, 800.0, 24000.0, 0.95, 40.0, 0.98, -45.0, 0.96, 56.0, 120.0, 0.075, 28.0)
    assert de == approx(0.708400)


def test_de_corrected_for_regain_and_limits():
    # DE 0.787916, regain 0.1 supply and return, B_r 0.98, a_r 0.95, dT_r 40, dT_e 55:
    # 0.787916 + 0.1 * 0.212084 - (0 - 0.98 * (0.095 - 0.1)) * 40/55 = 0.809124 - 0.003564 = 0.805561
    assert ducts.de_corrected(0.787916, 0.1, 0.1, 0.98, 0.95, 40.0, 55.0) == approx(0.805561)
    assert ducts.de_corrected(0.1, 0.0, 0.0, 1.0, 1.0, 40.0, 55.0) == 0.25   # floor
    assert ducts.de_corrected(1.2, 0.0, 0.0, 1.0, 1.0, 40.0, 55.0) == 1.0    # ceiling


def test_delivery_effectiveness_heating_assembles_the_pieces():
    # 600 cfm, 30,000 Btu/h, density 0.075: dT_e = 30000 / (60 * 600 * 0.075 * 0.2399) = 46.315 F
    # Supply: 100 ft2 R-4 in 10 F air (dT_s 60), 10 % leak -> a_s 0.9, B_s 0.96214. No return losses.
    # DE = 0.9 * 0.96214 - 0 - 0.9 * (1 - 0.96214) * 60 / 46.315 = 0.865926 - 0.044142 = 0.821784
    de = ducts.delivery_effectiveness_heating(q_s=60.0, q_r=0.0, cfm=600.0, load_sens=30000.0, t_amb_s=10.0,
                                              t_amb_r=70.0, area_s=100.0, area_r=0.0, t_setpoint=70.0,
                                              f_regain_s=0.0, f_regain_r=0.0, r_s=4.0, r_r=math.inf,
                                              air_density=0.075)
    assert de == approx(0.821784, rel=2e-4)


def system(**kw):
    return DistributionSystem(zone="z", **kw)


def test_duct_leakage_units():
    assert ducts.duct_leakage_cfm(system(supply_leakage=60.0, return_leakage=20.0), 800.0) == (60.0, 20.0)
    # Fraction of system airflow: 10 % and 5 % of 800 cfm
    s = system(supply_leakage=0.10, return_leakage=0.05, leakage_units="fraction")
    assert ducts.duct_leakage_cfm(s, 800.0) == (approx(80.0), approx(40.0))
    # CFM50 -> CFM25: 100 * 0.5^0.65 = 63.728
    s = system(supply_leakage=100.0, leakage_units="cfm50")
    assert ducts.duct_leakage_cfm(s, 800.0)[0] == approx(63.728)
    with pytest.raises(ValueError):
        ducts.duct_leakage_cfm(system(leakage_units="percent"), 800.0)


def house(buffers=(), **kw):
    cond = DesignConditions(heating_design_temp_f=10.0, cooling_design_temp_f=95.0, daily_temp_range="medium",
                            humidity_difference_grains=30.0, latitude_deg=40.0)
    return Building(conditions=cond, zones=[Zone("z")], rooms=[Room("room", "z", 1000.0)],
                    buffer_spaces=list(buffers), **kw)


def test_duct_regain_factors():
    attic = BufferSpace("attic", "attic_vented")
    garage = BufferSpace("garage", "garage")
    crawl = BufferSpace("crawl", "crawlspace_vented")
    chase = BufferSpace("chase", "weighted", duct_regain=0.5)
    b = house([attic, garage, crawl, chase],
              floors=[Floor("f", "room", "crawl", 1000.0, r_value=19.0)],
              foundation_walls=[FoundationWall("fw", "crawl", GROUND, 400.0, height_ft=3.0,
                                               depth_below_grade_ft=1.0)])
    assert ducts.duct_regain_factor(b, OUTSIDE) == 0.0
    assert ducts.duct_regain_factor(b, "room") == 1.0
    assert ducts.duct_regain_factor(b, "attic") == 0.10
    assert ducts.duct_regain_factor(b, "garage") == 0.05
    assert ducts.duct_regain_factor(b, "chase") == 0.5
    # Vented crawlspace, insulated floor above (R-19 > 4), bare walls: 0.12
    assert ducts.duct_regain_factor(b, "crawl") == 0.12
    # Bare floor above: 0.50
    b.floors[0].r_value = 2.0
    assert ducts.duct_regain_factor(b, "crawl") == 0.50
    # Bare floor, insulated walls (R-10 interior): 0.66
    b.foundation_walls[0].insulation_interior_r = 10.0
    assert ducts.duct_regain_factor(b, "crawl") == 0.66


def test_duct_conduction_values_area_weighting():
    attic = BufferSpace("attic", "attic_vented")
    b = house([attic], floors=[Ceiling("c", "room", "attic", 1000.0, r_value=38.0)])
    s = system(ducts=[Duct("supply", "attic", 150.0, 8.0), Duct("supply", OUTSIDE, 50.0, 4.0),
                      Duct("supply", "room", 500.0, 1.7), Duct("return", "attic", 40.0, 6.0, area_multiplier=2.0)])
    v = ducts.duct_conduction_values(b, s, {"attic": 130.0, OUTSIDE: 95.0})
    # Supply outside the rooms: 150 + 50 = 200 ft2 (the 500 ft2 inside is ignored)
    assert v.area_s == approx(200.0)
    # U = 0.75 / 8 + 0.25 / 4 = 0.15625 -> R = 6.4
    assert v.r_s == approx(6.4)
    # Ambient: 0.75 * 130 + 0.25 * 95 = 121.25 F; regain: 0.75 * 0.10 + 0.25 * 0 = 0.075
    assert v.t_amb_s == approx(121.25)
    assert v.f_regain_s == approx(0.075)
    # Return: 40 ft2 x multiplier 2 = 80 ft2, R-6, attic
    assert (v.area_r, v.r_r, v.t_amb_r, v.f_regain_r) == (approx(80.0), approx(6.0), approx(130.0), approx(0.10))


def test_no_ducts_outside_uses_outdoor_temperature():
    b = house()
    v = ducts.duct_conduction_values(b, system(ducts=[Duct("supply", "room", 100.0, 1.7)]), {OUTSIDE: 10.0})
    assert (v.area_s, v.t_amb_s, v.f_regain_s) == (0.0, 10.0, 0.0)
    assert math.isinf(v.r_s)


LEAK_ONLY = dict(ducts=[Duct("supply", "room", 100.0, 1.7)], supply_leakage=0.10, leakage_units="fraction")


def test_heating_duct_load_leakage_only():
    # All ducts inside, but 10 % of supply air leaks to outside: a_s = 0.9, B = 1, no return loss
    # -> DE = 0.9 whatever the airflow. Load 30,000 / 0.9 = 33,333; duct load = 3,333.3 Btu/h
    b = house()
    load = ducts.heating_duct_load(bldg=b, system=system(**LEAK_ONLY), load_btuh=30000.0,
                                   design_temps={OUTSIDE: 10.0}, setpoint_f=70.0, air_density=0.075)
    assert load == approx(3333.33, rel=1e-4)


def test_cooling_duct_load_leakage_only():
    # Same system in cooling: DE = a_s = 0.9 for both sensible and latent.
    # Sensible 18,000 / 0.9 - 18,000 = 2,000; latent 3,000 / 0.9 - 3,000 = 333.33
    b = house()
    sens, lat = ducts.cooling_duct_load(
        bldg=b, system=system(**LEAK_ONLY), load_sens_btuh=18000.0, load_lat_btuh=3000.0,
        design_temps={OUTSIDE: 95.0}, setpoint_f=75.0, air_density=0.075, leaving_air_temp=56.0,
        cooling_humidity_ratio=0.014, indoor_enthalpy=28.0, altitude_factor=1.0, design_grains=30.0)
    assert sens == approx(2000.0, rel=1e-4)
    assert lat == approx(333.33, rel=1e-4)


def test_heating_duct_load_converges_to_fixed_point():
    # With conduction losses the load and airflow depend on each other. At the answer,
    # total = load / DE(total), with DE evaluated at the airflow for that total.
    attic = BufferSpace("attic", "attic_vented")
    b = house([attic], floors=[Ceiling("c", "room", "attic", 1000.0, r_value=38.0)])
    s = system(ducts=[Duct("supply", "attic", 200.0, 6.0), Duct("return", "attic", 80.0, 6.0)],
               supply_leakage=40.0, return_leakage=20.0)
    temps = {"attic": 10.0, OUTSIDE: 10.0}
    load = ducts.heating_duct_load(bldg=b, system=s, load_btuh=30000.0, design_temps=temps, setpoint_f=70.0,
                                   air_density=0.075)
    total = 30000.0 + load
    cfm = ducts.airflow_cfm(240.0, total)
    de = ducts.delivery_effectiveness_heating(q_s=40.0, q_r=20.0, cfm=cfm, load_sens=total, t_amb_s=10.0,
                                              t_amb_r=10.0, area_s=200.0, area_r=80.0, t_setpoint=70.0,
                                              f_regain_s=0.10, f_regain_r=0.10, r_s=6.0, r_r=6.0, air_density=0.075)
    assert 30000.0 / de == approx(total, rel=5e-3)
    assert 0.5 < de < 0.95
