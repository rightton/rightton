"""Infiltration and ventilation airflows: hand calculations."""

import pytest
from conftest import approx
from rightton import airflow
from rightton.model import (Building, DesignConditions, Infiltration, Room, VentilationFan, Zone)


def test_leakage_at_pressure():
    # 100 cfm at 25 Pa -> at 50 Pa: 100 * (50/25)^0.65 = 100 * 1.56917 = 156.917
    assert airflow.leakage_at_pressure(100.0, 25.0, 50.0) == approx(156.917)


def test_sla_from_ach50():
    # ACH50 = 3, average ceiling height 8 ft:
    # numerator   = 3 * 0.283316 * 4^0.65 = 3 * 0.283316 * 2.46229 = 2.09283
    # denominator = 50^0.65 * 60 * 144 / 8 = 12.7154 * 1080 = 13,732.6
    # SLA = 0.00015240
    assert airflow.sla_from_ach50(3.0, 8.0) == approx(0.00015240)


def test_natural_ach_and_sla_round_trip():
    # SLA 0.0003, infiltration height 16.4 ft (2 x reference height), ceiling 8 ft, WSF 0.5:
    # NL = 1000 * 0.0003 * 2^0.4 = 0.3 * 1.31951 = 0.395852
    # ACH = 0.395852 * 0.5 * 8.202 / 8 = 0.202924
    assert airflow.natural_ach_from_sla(0.0003, 16.404, 8.0, 0.5) == approx(0.202924)
    assert airflow.sla_from_natural_ach(0.202924, 16.404, 8.0, 0.5) == approx(0.0003, rel=1e-4)


def test_stack_and_wind_coefficients():
    # One story, shielding class 4: Cs = 0.015; Cw = 0.0065 - 0.00266 * 1 = 0.00384
    assert airflow.stack_wind_coefficients(1, 4) == (approx(0.015), approx(0.00384))
    # Two stories, class 3: Cs = 0.030; Cw = 0.0065 * 2^0.4 = 0.0065 * 1.31951 = 0.0085768
    assert airflow.stack_wind_coefficients(2, 3) == (approx(0.030), approx(0.0085768))


def test_design_infiltration_cfm():
    # ELA 100 in2, heating: dT 60 F, 15 mph: 100 * sqrt(0.015 * 60 + 0.00384 * 225)
    # = 100 * sqrt(0.9 + 0.864) = 100 * 1.32816 = 132.816 cfm
    assert airflow.design_infiltration_cfm(100.0, 0.015, 0.00384, 60.0, 15.0) == approx(132.816)


def test_default_table_ach():
    assert airflow.default_table_ach("average", 2000.0, 1, True) == (0.38, 0.20)   # 1501-2000 ft2 column
    assert airflow.default_table_ach("leaky", 3500.0, 2, True) == (0.56, 0.29)     # > 3000 ft2 column
    assert airflow.default_table_ach("tight", 800.0, 1, False) == (0.47, 0.25)     # attached, <= 900 ft2
    assert airflow.default_table_ach("average", 900.0, 1, True) == (0.61, 0.32)    # boundary is inclusive


def test_net_infiltration_with_ventilation_imbalance():
    assert airflow.net_infiltration_cfm(80.0, 0.0) == 80.0
    # Exhaust-only 50 cfm: (80^1.5 + 50^1.5)^0.67 = (715.542 + 353.553)^0.67 = 107.014
    assert airflow.net_infiltration_cfm(80.0, 50.0) == approx(107.014)
    # Supply-only 50 cfm: (715.542 - 353.553)^0.67 = 361.989^0.67 = 51.799
    assert airflow.net_infiltration_cfm(80.0, -50.0) == approx(51.799)
    # Supply larger than infiltration: the house is pressurized, no infiltration
    assert airflow.net_infiltration_cfm(80.0, -100.0) == 0.0


def test_ventilation_data():
    # Supply 60 + exhaust 20: imbalance = 20 - 60 = -40 (pressurized); outdoor air load = 60 cfm
    v = airflow.ventilation_data([VentilationFan("supply", 60.0), VentilationFan("exhaust", 20.0)])
    assert (v.q_imbalance_cfm, v.q_outdoor_air_cfm) == (-40.0, 60.0)
    # Balanced 50: no imbalance, 50 cfm outdoor air, no recovery
    v = airflow.ventilation_data([VentilationFan("balanced", 50.0)])
    assert (v.q_imbalance_cfm, v.q_outdoor_air_cfm, v.heating_sensible_eff) == (0.0, 50.0, 0.0)
    # ERV 80 cfm, 70 % sensible, 40 % latent
    v = airflow.ventilation_data([VentilationFan("erv", 80.0, 0.7, 0.4)])
    assert (v.q_outdoor_air_cfm, v.heating_sensible_eff, v.cooling_sensible_eff, v.cooling_latent_eff) == (
        80.0, approx(0.7), approx(0.7), approx(0.4))
    # Air-handler-integrated supply: pressurizes, but is not a room load
    v = airflow.ventilation_data([VentilationFan("cfis", 40.0)])
    assert (v.q_imbalance_cfm, v.q_outdoor_air_cfm) == (-40.0, 0.0)
    # Exhaust only: depressurizes, no supply air load
    v = airflow.ventilation_data([VentilationFan("exhaust", 30.0)])
    assert (v.q_imbalance_cfm, v.q_outdoor_air_cfm) == (30.0, 0.0)
    assert airflow.ventilation_data([]).q_outdoor_air_cfm == 0.0


def house(infiltration, stories=1.0, facility="single_family_detached"):
    cond = DesignConditions(heating_design_temp_f=10.0, cooling_design_temp_f=95.0, daily_temp_range="medium",
                            humidity_difference_grains=30.0, latitude_deg=40.0, wsf=0.5)
    return Building(conditions=cond, zones=[Zone("z")], rooms=[Room("r", "z", 2000.0, 8.0)],
                    infiltration=infiltration, stories_above_grade=stories, facility_type=facility)


def test_blower_door_to_design_airflow():
    # 2000 ft2, 8 ft ceilings (16,000 ft3), ACH50 = 5, one story, shielding class 4.
    # SLA = 5 * 0.283316 * 2.46229 / (12.7154 * 60 * 144 / 8) = 3.48804 / 13,732.6 = 0.00025400
    # ELA = 0.000254 * 2000 ft2 * 144 = 73.151 in2
    # Heating (dT 60, 15 mph): 73.151 * sqrt(0.015 * 60 + 0.00384 * 225) = 73.151 * 1.32816 = 97.157 cfm
    # Cooling (dT 20, 7.5 mph): 73.151 * sqrt(0.3 + 0.00384 * 56.25) = 73.151 * sqrt(0.516) = 52.547 cfm
    res = airflow.infiltration_airflows(house(Infiltration(ach50=5.0)), 60.0, 20.0)
    assert res.sla == approx(0.00025400)
    assert res.ela_in2 == approx(73.151, rel=2e-4)
    assert res.heating_cfm == approx(97.157, rel=2e-4)
    assert res.cooling_cfm == approx(52.547, rel=2e-4)


def test_cfm50_input_gives_same_result_as_ach50():
    # 1333.33 cfm50 in 16,000 ft3 = 1333.33 * 60 / 16000 = 5.0 ACH50
    a = airflow.infiltration_airflows(house(Infiltration(cfm50=16000.0 * 5.0 / 60.0)), 60.0, 20.0)
    assert a.ach50 == approx(5.0)
    assert a.heating_cfm == approx(97.157, rel=2e-4)


def test_blower_door_at_other_test_pressure():
    # 3.1865 ACH at 25 Pa -> 3.1865 * 2^0.65 = 5.0 ACH50
    a = airflow.infiltration_airflows(house(Infiltration(ach50=5.0 / 1.56917, house_pressure_pa=25.0)), 60.0, 20.0)
    assert a.ach50 == approx(5.0, rel=1e-4)


def test_leakage_area_inputs():
    # ELA 72 in2 on 2000 ft2: SLA = 72 / 144 / 2000 = 0.00025
    a = airflow.infiltration_airflows(house(Infiltration(ela_in2=72.0)), 60.0, 20.0)
    assert a.sla == approx(0.00025)
    assert a.ela_in2 == approx(72.0)
    b = airflow.infiltration_airflows(house(Infiltration(sla=0.00025)), 60.0, 20.0)
    assert b.ela_in2 == approx(72.0)


def test_natural_ach_input():
    # 0.2 ACH natural, height 8 ft, ceiling 8 ft, WSF 0.5:
    # SLA = 0.2 * (8 / 8.202) / (1000 * 0.5 * (8 / 8.202)^0.4) = 0.195075 / (500 * 0.990086) = 0.00039406
    a = airflow.infiltration_airflows(house(Infiltration(natural_ach=0.2, height_ft=8.0)), 60.0, 20.0)
    assert a.sla == approx(0.00039406, rel=2e-4)


def test_exterior_fraction_scales_leakage_area():
    a = airflow.infiltration_airflows(house(Infiltration(ela_in2=72.0, exterior_fraction=0.5)), 60.0, 20.0)
    assert a.ela_in2 == approx(36.0)


def test_fireplace_adds_20_cfm_in_heating_only():
    a = airflow.infiltration_airflows(house(Infiltration(ach50=5.0, has_fireplace=True)), 60.0, 20.0)
    assert a.heating_cfm == approx(117.157, rel=2e-4)
    assert a.cooling_cfm == approx(52.547, rel=2e-4)


def test_default_table_method():
    # "average", 2000 ft2, one story: 0.38 ACH heating, 0.20 cooling on 16,000 ft3
    # heating 0.38 * 16000 / 60 = 101.333 cfm; cooling 0.20 * 16000 / 60 = 53.333 cfm
    a = airflow.infiltration_airflows(house(Infiltration(method="default_table", leakiness="average")), 60.0, 20.0)
    assert a.heating_cfm == approx(101.333)
    assert a.cooling_cfm == approx(53.333)


def test_attached_unit_above_grade_scales_wind_speed():
    # Unit 16 ft above grade, infiltration height 8 ft: story = (16 + 8) / 8 = 3; normal shielding
    # exponent 0.22: 3^0.22 = 1.27341. Heating wind 15 * 1.27341 = 19.101 mph
    # ELA 72: 72 * sqrt(0.9 + 0.00384 * 19.101^2) = 72 * sqrt(0.9 + 1.40103) = 72 * 1.51691 = 109.218 cfm
    infil = Infiltration(ela_in2=72.0, height_ft=8.0, unit_height_above_grade_ft=16.0)
    a = airflow.infiltration_airflows(house(infil, facility="apartment"), 60.0, 20.0)
    assert a.heating_cfm == approx(109.218, rel=3e-4)
    # A detached house ignores the unit height
    b = airflow.infiltration_airflows(house(infil), 60.0, 20.0)
    assert b.heating_cfm == approx(72.0 * 1.32816, rel=1e-4)


def test_missing_leakage_input_is_an_error():
    with pytest.raises(ValueError):
        airflow.infiltration_airflows(house(Infiltration()), 60.0, 20.0)


def test_no_infiltration_object():
    assert airflow.infiltration_airflows(house(None), 60.0, 20.0).heating_cfm == 0.0
