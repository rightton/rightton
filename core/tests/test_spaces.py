"""Buffer-space design temperatures: hand calculations."""

import math

from conftest import approx
from rightton import spaces
from rightton.model import (GROUND, OUTSIDE, BufferSpace, Building, Ceiling, DesignConditions, Floor,
                            FoundationWall, Roof, Room, Slab, Wall, Zone)


def conditions(**kw):
    d = dict(heating_design_temp_f=10.0, cooling_design_temp_f=95.0, daily_temp_range="medium",
             humidity_difference_grains=30.0, latitude_deg=40.0, ground_conductivity_btu_h_ft_f=0.8,
             ground_temp_winter_f=45.0, ground_temp_summer_f=65.0, wsf=0.5)
    d.update(kw)
    return DesignConditions(**d)


def building(buffer, **kw):
    return Building(conditions=kw.pop("conditions", conditions()), zones=[Zone("z")],
                    rooms=[Room("room", "z", 1000.0)], buffer_spaces=[buffer], **kw)


def test_average_r_value():
    # 100 ft2 at R-10 and 100 ft2 at R-30: UA = 10 + 3.333 = 13.333; 200 / 13.333 = R-15
    surfaces = [Wall("a", "x", area_ft2=100.0, r_value=10.0), Wall("b", "x", area_ft2=100.0, r_value=30.0)]
    assert spaces.average_r_value(surfaces) == approx(15.0)
    assert math.isnan(spaces.average_r_value([]))


def test_balance_temperature():
    # UA 50 to outdoors at 0 F, 25 to ground at 45 F, 25 to rooms at 70 F:
    # (0 + 1125 + 1750) / 100 = 28.75 F
    ua = {"outside": 50.0, "ground": 25.0, "conditioned": 25.0}
    assert spaces.balance_temperature(ua, 70.0, 0.0, 45.0) == approx(28.75)


def test_insulated_unvented_attic_cooling_temp():
    # Setpoint 75: range 80..125 F. A quarter of the UA goes to the rooms: 125 - 0.25 * 45 = 113.75 F
    ua = {"outside": 75.0, "ground": 0.0, "conditioned": 25.0}
    assert spaces.insulated_unvented_attic_cooling_temp(ua, 75.0) == approx(113.75)


def test_weighted_space():
    # Duct chase in an exterior wall: half indoor (70), half outdoor (10) -> 40 F
    wall_chase = BufferSpace("chase", "weighted", indoor_weight=0.5, outdoor_weight=0.5)
    assert spaces.weighted_temperature(wall_chase, 70.0, 10.0, 45.0) == approx(40.0)
    # Neighboring heated space never below 68 F
    heated = BufferSpace("hall", "weighted", indoor_weight=0.5, outdoor_weight=0.5, min_temp_f=68.0)
    assert spaces.weighted_temperature(heated, 70.0, 10.0, 45.0) == approx(68.0)
    # Under the slab: ground temperature
    under = BufferSpace("under", "weighted", outdoor_weight=0.0, ground_weight=1.0)
    assert spaces.weighted_temperature(under, 75.0, 95.0, 65.0) == approx(65.0)


def attic_house(kind, ceiling_r, roof_r, **roof_kw):
    attic = BufferSpace("attic", kind, volume_ft3=2000.0)
    return building(attic,
                    floors=[Ceiling("ceiling", "room", "attic", 1000.0, r_value=ceiling_r)],
                    roofs=[Roof("roof", "attic", OUTSIDE, 1118.0, r_value=roof_r, **roof_kw)]), attic


def test_vented_attic_insulated_at_ceiling():
    # Dark asphalt shingles, no radiant barrier: 130 F on a 95 F medium-range day; heating = outdoor
    b, attic = attic_house("attic_vented", 38.0, 2.0, roof_color="dark")
    assert spaces.cooling_design_temp(b, attic, 0.075) == approx(130.0)
    assert spaces.heating_design_temp(b, attic, 0.075) == approx(10.0)


def test_vented_attic_table_adjustments():
    # Light metal roof with a radiant barrier: 110 F; 100 F design day: +5; low daily range: +4 -> 119 F
    b, attic = attic_house("attic_vented", 38.0, 2.0, roof_type="metal", roof_color="light", radiant_barrier=True)
    b.conditions.cooling_design_temp_f = 100.0
    b.conditions.daily_temp_range = "low"
    assert spaces.cooling_design_temp(b, attic, 0.075) == approx(119.0)


def test_unvented_attic_insulated_at_ceiling():
    # 150 F without a radiant barrier
    b, attic = attic_house("attic_unvented", 38.0, 2.0)
    assert spaces.cooling_design_temp(b, attic, 0.075) == approx(150.0)
    assert spaces.heating_design_temp(b, attic, 0.075) == approx(10.0)


def test_vented_attic_insulated_at_roof():
    # Ceiling R-2 < roof R-30: treated as encapsulated but vented: outdoor + 40 = 135 F; heating = outdoor
    b, attic = attic_house("attic_vented", 2.0, 30.0)
    assert spaces.cooling_design_temp(b, attic, 0.075) == approx(135.0)
    assert spaces.heating_design_temp(b, attic, 0.075) == approx(10.0)


def test_unvented_attic_insulated_at_roof():
    # UA to rooms: 1000 / 2 = 500. UA to outdoors: roof 1118 / 30 = 37.267 plus air leakage
    # 0.1 ACH * 2000 ft3 / 60 = 3.3333 cfm * 0.075 lb/ft3 * 0.2399 * 60 = 3.5985 -> 40.865
    b, attic = attic_house("attic_unvented", 2.0, 30.0)
    ua = spaces.space_ua_values(b, attic, 0.075)
    assert ua["conditioned"] == approx(500.0)
    assert ua["outside"] == approx(40.865, rel=2e-4)
    # Cooling: share to rooms = 500 / 540.865 = 0.92444; 125 - 0.92444 * 45 = 83.400 F
    assert spaces.cooling_design_temp(b, attic, 0.075) == approx(83.400, rel=2e-4)
    # Heating: (500 * 70 + 40.865 * 10) / 540.865 = 65.467 F
    assert spaces.heating_design_temp(b, attic, 0.075) == approx(65.467, rel=2e-4)


def test_vented_space_air_change_from_vent_area():
    # Vented attic, SLA 1/300, WSF 0.5: ACH = 1000 * (1/300) * 0.5 = 1.6667
    # 1.6667 / 60 * 2000 ft3 = 55.556 cfm * 0.075 * 0.2399 * 60 = 59.975 Btu/h-F, plus roof 1118/2 = 559
    b, attic = attic_house("attic_vented", 38.0, 2.0)
    assert spaces.space_ua_values(b, attic, 0.075)["outside"] == approx(559.0 + 59.975, rel=2e-4)
    attic.vent_ach = 3.0  # explicit: 3 / 60 * 2000 = 100 cfm -> 107.955
    assert spaces.space_ua_values(b, attic, 0.075)["outside"] == approx(559.0 + 107.955, rel=2e-4)


def basement_house(kind="basement_unconditioned"):
    space = BufferSpace("under", kind, volume_ft3=8000.0)
    return building(
        space,
        floors=[Floor("floor", "room", "under", 1000.0, r_value=20.0)],
        foundation_walls=[FoundationWall("fw", "under", GROUND, 1000.0, height_ft=8.0, depth_below_grade_ft=7.0)],
        slabs=[Slab("slab", "under", 1000.0, 130.0, thickness_in=4.0)],
    ), space


def test_unconditioned_basement_ua_and_temperatures():
    b, space = basement_house()
    ua = spaces.space_ua_values(b, space, 0.075)
    # To rooms: floor 1000 / 20 = 50
    assert ua["conditioned"] == approx(50.0)
    # To ground: wall 875 ft2 below grade at 1/1.32 = 0.75758 and 125 ft2 above at 1/1.53 = 0.65359
    #   = 662.88 + 81.70 = 744.58; bare 4 in slab 1000 / 0.32 = 3125 -> 3869.58
    assert ua["ground"] == approx(3869.58, rel=1e-4)
    # To outdoors: 0.1 ACH * 8000 / 60 = 13.333 cfm * 0.075 * 0.2399 * 60 = 14.394
    assert ua["outside"] == approx(14.394, rel=1e-4)
    # Heating: (14.394 * 10 + 3869.58 * 45 + 50 * 70) / 3933.98 = 45.190 F
    assert spaces.heating_design_temp(b, space, 0.075) == approx(45.190, rel=1e-4)
    # Cooling: (14.394 * 95 + 3869.58 * 65 + 50 * 75) / 3933.98 = 65.237 F
    assert spaces.cooling_design_temp(b, space, 0.075) == approx(65.237, rel=1e-4)


def test_crawlspace_ground_contact_counts_as_outdoor():
    # Same geometry as a crawlspace: ground-contact UA is assigned to outdoor temperature
    b, space = basement_house("crawlspace_unvented")
    ua = spaces.space_ua_values(b, space, 0.075)
    assert ua["ground"] == 0.0
    assert ua["outside"] == approx(3869.58 + 14.394, rel=1e-4)


def test_slab_ua_with_insulation_and_dirt_floor():
    b, space = basement_house()
    slab = b.slabs[0]
    # R-10 under a 4 ft band along 130 ft of edge: 520 ft2 at 1 / (0.32 + 10) = 50.388
    # R-5 perimeter insulation 2 ft deep: 260 ft2 at 1 / 5.32 = 48.872
    # Rest: 1000 - 520 - 260 = 220 ft2 at 1 / 0.32 = 687.5   -> 786.76
    slab.under_slab_insulation_r, slab.under_slab_insulation_width_ft = 10.0, 4.0
    slab.perimeter_insulation_r, slab.perimeter_insulation_depth_ft = 5.0, 2.0
    assert spaces.space_ua_values(b, space, 0.075)["ground"] == approx(744.58 + 786.76, rel=1e-4)
    # Dirt floor: U = 0.1 -> 100
    slab.thickness_in = 0.0
    assert spaces.space_ua_values(b, space, 0.075)["ground"] == approx(744.58 + 100.0, rel=1e-4)


def test_above_grade_garage():
    # Garage with a 400 ft2 floor of a room above it and a 200 ft2 roof of its own:
    # fraction under conditioned space = 400 / 600 = 0.6667
    garage = BufferSpace("garage", "garage")
    b = building(garage, floors=[Floor("f", "room", "garage", 400.0, r_value=19.0)],
                 roofs=[Roof("r", "garage", OUTSIDE, 200.0, r_value=2.0)])
    assert spaces.garage_fraction_under_conditioned(b, garage) == approx(0.66667)
    # Cooling, medium daily range: 95 + 6 * 0.6667 + 17 * 0.3333 = 95 + 4 + 5.667 = 104.667 F
    assert spaces.cooling_design_temp(b, garage, 0.075) == approx(104.667)
    # Heating: 10 + 5 * 0.6667 = 13.333 F
    assert spaces.heating_design_temp(b, garage, 0.075) == approx(13.333)


def test_garage_with_no_adjacent_surfaces_assumes_half():
    garage = BufferSpace("garage", "garage")
    assert spaces.garage_fraction_under_conditioned(building(garage), garage) == 0.5


def test_user_override_of_design_temperatures():
    space = BufferSpace("porch", "garage", heating_design_temp_f=40.0, cooling_design_temp_f=88.0)
    b = building(space)
    assert spaces.heating_design_temp(b, space, 0.075) == 40.0
    assert spaces.cooling_design_temp(b, space, 0.075) == 88.0
