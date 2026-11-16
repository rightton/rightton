"""Whole-house calculation: a small house worked by hand, component by component."""

import math

import pytest
from conftest import approx
from rightton.engine import calculate
from rightton.model import (ADIABATIC, GROUND, OUTSIDE, BufferSpace, Building, Ceiling, DesignConditions,
                            DistributionSystem, Door, Duct, Floor, FoundationWall, Infiltration, Roof, Room,
                            Skylight, Slab, VentilationFan, Wall, Window, Zone)


def conditions(**kw):
    # Heating: 70 - 10 = 60 F. Cooling: 95 - 75 = 20 F. Sea level (no altitude correction).
    d = dict(heating_design_temp_f=10.0, cooling_design_temp_f=95.0, daily_temp_range="medium",
             humidity_difference_grains=30.0, latitude_deg=40.0, ground_conductivity_btu_h_ft_f=1.0)
    d.update(kw)
    return DesignConditions(**d)


def one_room_house():
    return Building(
        conditions=conditions(),
        zones=[Zone("main")],
        rooms=[Room("living", "main", 1000.0, 8.0, occupants=2, internal_sensible_btuh=1200.0,
                    internal_latent_btuh=100.0)],
        buffer_spaces=[BufferSpace("attic", "attic_vented", volume_ft3=2000.0)],
        walls=[Wall("wall", "living", OUTSIDE, 400.0, r_value=20.0)],
        windows=[Window("window", "wall", 40.0, 90.0, 0.5, 0.6)],
        doors=[Door("door", "wall", 20.0, 5.0)],
        floors=[Ceiling("ceiling", "living", "attic", 1000.0, r_value=38.0)],
        roofs=[Roof("roof", "attic", OUTSIDE, 1118.0, r_value=2.0, roof_color="dark")],
        slabs=[Slab("slab", "living", 1000.0, 130.0)],
        infiltration=Infiltration(ach50=5.0),
    )


def slab_f(k):
    # Bare 4 in slab (see test_foundation): 5.52 under the slab, 1.14 films, soil arc (pi r - 1) / k
    return sum(sum(1.0 / ((0.0 if r == 0 else 5.52) + 1.14 + max(math.pi * r - 1.0, 0.0) / k)
                   for r in range(n + 1)) for n in range(8, 14)) / 6.0


def test_one_room_house_components():
    res = calculate(one_room_house())
    room = res.rooms["living"]

    # Window, east, 40 ft2, U 0.5, SHGC 0.6: heating 0.5 * 60 * 40 = 1200
    assert room.heat_windows == approx(1200.0)
    # cooling HTM 66.607 (see test_fenestration) * 40 = 2664.28
    assert room.cool_windows == approx(2664.28, rel=2e-4)

    # Door, 20 ft2, R-5: heating 0.2 * 60 * 20 = 240; cooling 0.2 * (20 + 11) * 20 = 124
    assert room.heat_doors == approx(240.0)
    assert room.cool_doors == approx(124.0)

    # Wall, R-20 (U 0.05 -> group C, base CLTD 20.5 x 0.83 medium = 17.015), net 400 - 40 - 20 = 340 ft2
    # heating 0.05 * 60 * 340 = 1020; cooling 0.05 * 17.015 * 340 = 289.255
    assert room.heat_walls == approx(1020.0)
    assert room.cool_walls == approx(289.255)

    # Ceiling R-38 under a vented attic (10 F in winter, 130 F in summer), 1000 ft2
    # heating (70 - 10) / 38 * 1000 = 1578.95; cooling (130 - 75) / 38 * 1000 = 1447.37
    assert res.heating_design_temps["attic"] == approx(10.0)
    assert res.cooling_design_temps["attic"] == approx(130.0)
    assert room.heat_ceilings == approx(1578.95, rel=1e-5)
    assert room.cool_ceilings == approx(1447.37, rel=1e-5)

    # Slab on grade: F * 60 F * 130 ft of exposed edge; no cooling load
    assert room.heat_slabs == approx(slab_f(1.0) * 60.0 * 130.0)
    assert room.cool_slabs == 0.0

    # Infiltration: ACH50 5, 8000 ft3, 1000 ft2 -> SLA 0.000254, ELA 36.576 in2
    # heating 36.576 * 1.32816 = 48.578 cfm -> 1.1 * 48.578 * 60 = 3206.2
    # cooling 36.576 * sqrt(0.516) = 26.273 cfm -> sensible 1.1 * 26.273 * 20 = 578.0
    #                                              latent 0.68 * 26.273 * 30 = 536.0
    assert res.infiltration.heating_cfm == approx(48.578, rel=3e-4)
    assert res.infiltration.cooling_cfm == approx(26.273, rel=3e-4)
    assert room.heat_infiltration == approx(3206.2, rel=3e-4)
    assert room.cool_infiltration_sens == approx(578.0, rel=3e-4)
    assert room.cool_infiltration_lat == approx(536.0, rel=3e-4)

    # Internal gains: 1200 + 2 people * 230 = 1660 sensible; 100 + 2 * 200 = 500 latent
    assert room.cool_internal_sens == approx(1660.0)
    assert room.cool_internal_lat == approx(500.0)


def test_one_room_house_excursion_and_totals():
    res = calculate(one_room_house())
    room, zone, bldg = res.rooms["living"], res.zones["main"], res.building

    # Hourly window HTM, 8:00..19:00 = 148.9655 * CLF_east + 0.5 * (20 + adjustment):
    hourly = [79.672, 89.910, 91.210, 81.983, 71.116, 64.467, 57.519, 53.200, 47.091, 42.122, 36.853, 29.845]
    assert room.hourly_fenestration == approx([h * 40.0 for h in hourly], rel=2e-4)
    # Average 62.082; limit 1.3 x = 80.707; peak 91.210 -> excursion 10.503 Btu/h-ft2 x 40 = 420.1
    assert zone.cool_aed_excursion == approx(420.1, rel=2e-3)
    assert room.cool_aed_excursion == approx(420.1, rel=2e-3)

    heat = 1200.0 + 240.0 + 1020.0 + 1578.95 + slab_f(1.0) * 7800.0 + 3206.2
    sens = 2664.28 + 124.0 + 289.255 + 1447.37 + 578.0 + 1660.0 + 420.1
    lat = 536.0 + 500.0
    for loads in (room, zone, bldg):
        assert loads.heat_total == approx(heat, rel=2e-4)
        assert loads.cool_sensible == approx(sens, rel=2e-4)
        assert loads.cool_latent == approx(lat, rel=2e-4)
        assert loads.cool_total == approx(sens + lat, rel=2e-4)
    assert bldg.cool_tons == approx((sens + lat) / 12000.0, rel=2e-4)
    assert bldg.sensible_heat_ratio == approx(sens / (sens + lat), rel=2e-4)

    # The room at its own peak hour: the 9:00-10:00 window load (91.210 * 40 = 3648.4)
    # replaces the average window load and the excursion.
    assert res.room_peak_cool_sensible["living"] == approx(sens - 2664.28 - 420.1 + 3648.4, rel=2e-4)
    assert res.room_wall_area_ratio == {"living": 1.0}
    assert (res.htd_f, res.ctd_f) == (60.0, 20.0)


def test_surface_details_list_every_component():
    res = calculate(one_room_house())
    by_id = {d.id: d for d in res.surfaces}
    assert set(by_id) == {"window", "door", "wall", "ceiling", "slab"}
    assert by_id["wall"].area_ft2 == approx(340.0)
    assert by_id["wall"].heat_htm == approx(3.0)        # 0.05 * 60
    assert by_id["window"].heat_btuh == approx(1200.0)
    assert by_id["slab"].area_ft2 == approx(130.0)      # exposed perimeter for near-grade slabs


def test_altitude_correction_applies_to_air_loads():
    # 5000 ft: factor 1 - 0.0000308 * 5000 = 0.846 on infiltration loads
    b = one_room_house()
    b.conditions.elevation_ft = 5000.0
    room = calculate(b).rooms["living"]
    assert room.heat_infiltration == approx(3206.2 * 0.846, rel=3e-4)
    assert room.cool_infiltration_lat == approx(536.0 * 0.846, rel=3e-4)


def test_roof_directly_over_room_and_skylight():
    # Cathedral ceiling: R-25 dark shingle roof, 500 ft2 gross with a 10 ft2 skylight.
    # Roof: heating 60 / 25 * 490 = 1176; cooling CLTD 30 -> 30 / 25 * 490 = 588
    # Skylight U 0.5, SHGC 0.6, south, 12-in-12 pitch: heating 0.5 * 60 * 10 = 300;
    # cooling HTM 116.846 (see test_fenestration) * 10 = 1168.46
    b = Building(conditions=conditions(), zones=[Zone("z")], rooms=[Room("loft", "z", 400.0)],
                 roofs=[Roof("roof", "loft", OUTSIDE, 500.0, r_value=25.0, roof_color="dark", pitch=12.0)],
                 skylights=[Skylight("sky", "roof", 10.0, 180.0, 0.5, 0.6)])
    room = calculate(b).rooms["loft"]
    assert room.heat_roofs == approx(1176.0)
    assert room.cool_roofs == approx(588.0)
    assert room.heat_skylights == approx(300.0)
    assert room.cool_skylights == approx(1168.46, rel=2e-4)


def test_exposed_floor_and_radiant_floor():
    # Floor over open air, 300 ft2, R-10: heating 60 / 10 * 300 = 1800; cooling (20 - 5 + 0) / 10 * 300 = 450
    b = Building(conditions=conditions(), zones=[Zone("z")], rooms=[Room("room", "z", 300.0)],
                 floors=[Floor("floor", "room", OUTSIDE, 300.0, r_value=10.0)])
    room = calculate(b).rooms["room"]
    assert room.heat_floors == approx(1800.0)
    assert room.cool_floors == approx(450.0)
    # Radiant floor heat: 25 F added to the heating difference: 85 / 10 * 300 = 2550
    b.zones[0].has_radiant_floor = True
    assert calculate(b).rooms["room"].heat_floors == approx(2550.0)


def crawlspace_house(kind):
    return Building(
        conditions=conditions(ground_conductivity_btu_h_ft_f=0.8), zones=[Zone("z")],
        rooms=[Room("room", "z", 1000.0)],
        buffer_spaces=[BufferSpace("crawl", kind, volume_ft3=3000.0)],
        floors=[Floor("floor", "room", "crawl", 1000.0, r_value=20.0)],
        # 3 ft crawlspace wall entirely above grade (U = 1/1.53 = 0.65359), 390 ft2
        foundation_walls=[FoundationWall("fw", "crawl", GROUND, 390.0, height_ft=3.0, depth_below_grade_ft=0.0)],
        # Rim joists are not part of the wall average
        walls=[Wall("rim", "crawl", OUTSIDE, 100.0, r_value=5.0, is_rim_joist=True)],
        slabs=[Slab("dirt", "crawl", 1000.0, 130.0, thickness_in=0.0)])


def test_floor_over_vented_crawlspace():
    # Floor U 0.05, wall U 0.65359: TD factor 1 / (1 + 0.2 / (0.65359 + 0.11)) = 1 / 1.26193 = 0.79244
    # heating 0.05 * 60 * 0.79244 * 1000 = 2377.3; cooling 0.05 * 20 * 0.79244 * 1000 = 792.4
    room = calculate(crawlspace_house("crawlspace_vented")).rooms["room"]
    assert room.heat_floors == approx(2377.3, rel=2e-4)
    assert room.cool_floors == approx(792.4, rel=2e-4)


def test_floor_over_sealed_crawlspace():
    # TD factor 0.65359 / (0.2 + 0.65359) = 0.76570: heating 2297.1; cooling 765.7
    room = calculate(crawlspace_house("crawlspace_unvented")).rooms["room"]
    assert room.heat_floors == approx(2297.1, rel=2e-4)
    assert room.cool_floors == approx(765.7, rel=2e-4)


def basement_house():
    # Conditioned basement room 30 x 40 ft, walls 8 ft high and 7 ft below grade, uninsulated.
    return Building(
        conditions=conditions(ground_conductivity_btu_h_ft_f=0.8), zones=[Zone("z")],
        rooms=[Room("basement", "z", 1200.0, below_grade=True)],
        foundation_walls=[
            FoundationWall("north", "basement", GROUND, 320.0, height_ft=8.0, depth_below_grade_ft=7.0, azimuth_deg=0),
            FoundationWall("south", "basement", GROUND, 320.0, height_ft=8.0, depth_below_grade_ft=7.0, azimuth_deg=180),
            FoundationWall("east", "basement", GROUND, 240.0, height_ft=8.0, depth_below_grade_ft=7.0, azimuth_deg=90),
            FoundationWall("west", "basement", ADIABATIC, 240.0, height_ft=8.0, depth_below_grade_ft=7.0,
                           azimuth_deg=270)],
        slabs=[Slab("slab", "basement", 1200.0, 110.0)])


def test_conditioned_basement_walls_and_floor():
    res = calculate(basement_house())
    room = res.rooms["basement"]
    # Above-grade strip: 1 ft of 8 -> 880 ft2 of exposed wall * 1/8 = 110 ft2 at U 0.65359
    #   heating 0.65359 * 60 * 110 = 4313.7
    #   cooling: 8 in concrete, U 0.654 -> group D (22 F) x 0.83 = 18.26 -> 0.65359 * 18.26 * 110 = 1312.8
    # Below-grade: 770 ft2. Strip U with soil (k 0.8): 1 / (1.32 + pi * d / 1.6) for d = 0.5 .. 6.5:
    #   0.43445 0.23445 0.16054 0.12207 0.09848 0.08253 0.07102 -> mean 0.171934, x 0.85 = 0.146144
    #   heating 0.146144 * 60 * 770 = 6751.9
    assert room.heat_walls == approx(4313.7 + 6751.9, rel=3e-4)
    assert room.cool_walls == approx(1312.8, rel=3e-4)
    # The party wall carries no load but counts for geometry: shortest side = 30 ft (east or west wall).
    # Floor: ln(15 + 3.5 + 0.37433) - ln(3.87433) = 2.93780 - 1.35437 = 1.58343
    #   U = 0.85 * (1.6 / (pi * 30)) * 1.58343 = 0.022849; heating 0.022849 * 60 * 1200 = 1645.1
    assert room.heat_slabs == approx(1645.1, rel=3e-4)
    # Exposed wall area for sharing infiltration: the 110 ft2 above grade only
    assert {d.kind for d in res.surfaces} == {"walls", "walls_below_grade", "slabs"}


def test_shallow_foundation_wall_is_all_above_grade():
    # Less than 2 ft below grade: whole wall treated as above grade, no below-grade term
    b = basement_house()
    for fw in b.foundation_walls:
        fw.depth_below_grade_ft = 1.0
    res = calculate(b)
    # 880 ft2 exposed at U 0.65359: 0.65359 * 60 * 880 = 34,509.6
    assert res.rooms["basement"].heat_walls == approx(34509.6, rel=2e-4)
    # Average depth under 2 ft: the floor is a near-grade slab (edge loss), not a basement floor
    assert next(d for d in res.surfaces if d.kind == "slabs").area_ft2 == approx(110.0)


def two_zone_house():
    return Building(
        conditions=conditions(), zones=[Zone("down"), Zone("up", heating_setpoint_f=65.0, cooling_setpoint_f=78.0)],
        rooms=[Room("first", "down", 600.0), Room("second", "up", 400.0)],
        walls=[Wall("w1", "first", OUTSIDE, 300.0, r_value=10.0), Wall("w2", "second", OUTSIDE, 100.0, r_value=10.0)],
        floors=[Floor("between", "first", "second", 500.0, r_value=5.0)])


def test_zone_to_zone_transfer():
    res = calculate(two_zone_house())
    first, second = res.rooms["first"], res.rooms["second"]
    # Partition U 0.2, 500 ft2. Winter: downstairs 70 F loses to upstairs 65 F: 0.2 * 500 * 5 = +500
    # Summer: upstairs at 78 F warms downstairs at 75 F: 0.2 * 500 * 3 = +300
    assert first.heat_interzone == approx(500.0)
    assert first.cool_interzone == approx(300.0)
    assert second.heat_interzone == approx(-500.0)
    assert second.cool_interzone == approx(-300.0)
    # Transfers cancel for the building
    assert res.building.heat_interzone == approx(0.0, abs_=1e-9)
    # Each zone's envelope uses its own setpoint: upstairs wall 0.1 * (65 - 10) * 100 = 550
    assert second.heat_walls == approx(550.0)
    assert first.heat_walls == approx(0.1 * 60.0 * 300.0)


def test_equal_setpoints_give_no_transfer():
    b = two_zone_house()
    b.zones[1].heating_setpoint_f = b.zones[1].cooling_setpoint_f = None
    res = calculate(b)
    assert res.rooms["first"].heat_interzone == 0.0
    assert not [d for d in res.surfaces if d.kind == "interzone"]


def test_infiltration_and_ventilation_are_shared_among_rooms():
    b = two_zone_house()
    b.zones[1].heating_setpoint_f = b.zones[1].cooling_setpoint_f = None
    b.infiltration = Infiltration(ela_in2=72.0)
    b.ventilation_fans = [VentilationFan("balanced", 60.0)]
    res = calculate(b)
    # Infiltration by exposed wall area: 300 and 100 ft2 -> 75 % and 25 %
    assert res.room_wall_area_ratio == {"first": 0.75, "second": 0.25}
    # Whole house: 72 in2 * 1.32816 = 95.628 cfm -> 1.1 * 95.628 * 60 = 6311.4 Btu/h
    assert res.rooms["first"].heat_infiltration == approx(6311.4 * 0.75, rel=2e-4)
    assert res.rooms["second"].heat_infiltration == approx(6311.4 * 0.25, rel=2e-4)
    # Ventilation, 60 cfm balanced: heating 1.1 * 60 * 60 = 3960; sensible 1.1 * 60 * 20 = 1320;
    # latent 0.68 * 60 * 30 = 1224; shared by floor area 600 : 400
    assert res.rooms["first"].heat_ventilation == approx(3960.0 * 0.6)
    assert res.rooms["second"].cool_ventilation_sens == approx(1320.0 * 0.4)
    assert res.building.cool_ventilation_lat == approx(1224.0)


def test_heat_recovery_and_exhaust_ventilation():
    b = one_room_house()
    # HRV 60 cfm at 70 % sensible effectiveness: heating 1.1 * 60 * 0.3 * 60 = 1188; latent unchanged 1224
    b.ventilation_fans = [VentilationFan("hrv", 60.0, sensible_effectiveness=0.7)]
    room = calculate(b).rooms["living"]
    assert room.heat_ventilation == approx(1188.0)
    assert room.cool_ventilation_lat == approx(1224.0)
    # Exhaust-only 50 cfm: no supply-air load, but infiltration rises:
    # heating (48.578^1.5 + 50^1.5)^0.67 = (338.58 + 353.55)^0.67 = 79.97 cfm -> 1.1 * 79.97 * 60 = 5278
    b.ventilation_fans = [VentilationFan("exhaust", 50.0)]
    res = calculate(b)
    assert res.rooms["living"].heat_ventilation == 0.0
    assert res.infiltration.net_heating_cfm == approx(79.97, rel=1e-3)
    assert res.rooms["living"].heat_infiltration == approx(5278.0, rel=1e-3)


def test_duct_blower_and_piping_loads():
    b = two_zone_house()
    b.zones = [Zone("down")]
    b.rooms[1].zone = "down"
    b.rooms[0].internal_sensible_btuh = 3000.0
    b.rooms[1].internal_latent_btuh = 600.0
    # All ducts inside, 10 % supply leakage to outside: delivery effectiveness 0.9 (see test_ducts)
    b.distribution_systems = [DistributionSystem(
        zone="down", ducts=[Duct("supply", "first", 100.0, 1.7)], supply_leakage=0.10, leakage_units="fraction",
        blower_heat_btuh=500.0, piping_btuh=300.0)]
    res = calculate(b)
    zone, first, second = res.zones["down"], res.rooms["first"], res.rooms["second"]
    # Heating without ducts: walls 0.1 * 60 * (300 + 100) = 2400 -> duct load 2400 / 0.9 - 2400 = 266.67
    assert zone.heat_ducts == approx(266.67, rel=1e-4)
    # shared in proportion to room loads 1800 : 600
    assert first.heat_ducts == approx(200.0, rel=1e-4)
    assert second.heat_ducts == approx(66.67, rel=1e-4)
    # Zone heating total: 2400 + 266.67 + 300 piping (piping and blower heat stay at zone level)
    assert zone.heat_total == approx(2966.67, rel=1e-4)
    assert first.heat_piping == 0.0
    # Cooling sensible without ducts: walls (U 0.1 is in the 0.086-0.110 band -> group F:
    #   31.9 x 0.83 = 26.477 F) 0.1 * 26.477 * 400 = 1059.08, plus 3000 internal = 4059.08
    #   -> ducts 4059.08 / 9 = 451.01
    assert zone.cool_ducts_sens == approx(451.01, rel=1e-4)
    # Latent 600 -> ducts 600 / 9 = 66.67
    assert zone.cool_ducts_lat == approx(66.67, rel=1e-4)
    assert zone.cool_blower_heat == 500.0
    assert zone.cool_sensible == approx(4059.08 + 451.01 + 500.0, rel=1e-4)
    assert first.cool_ducts_sens + second.cool_ducts_sens == approx(451.01, rel=1e-4)
    assert res.building.heat_total == approx(2966.67, rel=1e-4)


def test_heating_only_system_has_no_cooling_duct_load():
    b = two_zone_house()
    b.rooms[1].zone = "down"
    b.zones = [Zone("down")]
    b.distribution_systems = [DistributionSystem(zone="down", has_cooling=False,
                                                 ducts=[Duct("supply", "first", 100.0, 1.7)],
                                                 supply_leakage=0.10, leakage_units="fraction")]
    zone = calculate(b).zones["down"]
    assert zone.heat_ducts > 0
    assert zone.cool_ducts_sens == 0.0


def test_partition_wall_and_door_to_buffer_space():
    # Wall and door to a garage held (by override) at 30 F in winter and 100 F in summer.
    b = Building(conditions=conditions(), zones=[Zone("z")], rooms=[Room("room", "z", 500.0)],
                 buffer_spaces=[BufferSpace("garage", "garage", heating_design_temp_f=30.0,
                                            cooling_design_temp_f=100.0)],
                 walls=[Wall("gw", "room", "garage", 200.0, r_value=13.0)],
                 doors=[Door("gd", "gw", 20.0, 2.0)])
    res = calculate(b)
    room = res.rooms["room"]
    # Wall net 180 ft2: heating (70 - 30) / 13 * 180 = 553.85; cooling (100 - 75) / 13 * 180 = 346.15
    assert room.heat_walls == approx(553.85)
    assert room.cool_walls == approx(346.15)
    # Door: heating 40 / 2 * 20 = 400; cooling 25 / 2 * 20 = 250
    assert room.heat_doors == approx(400.0)
    assert room.cool_doors == approx(250.0)
    # A wall to a garage is not exposed wall for infiltration sharing
    assert res.room_wall_area_ratio["room"] == 0.0


def test_validation_errors():
    b = one_room_house()
    b.rooms[0].zone = "nowhere"
    with pytest.raises(ValueError):
        calculate(b)
    b = one_room_house()
    b.walls[0].outside = "nowhere"
    with pytest.raises(ValueError):
        calculate(b)
    b = one_room_house()
    b.walls[0].r_value = None
    with pytest.raises(ValueError):
        calculate(b)


def test_equipment_heat_is_reported_on_its_own_line():
    # A dehumidifier rejecting 1500 Btu/h of heat into the room and removing 900 Btu/h of moisture load
    b = one_room_house()
    base = calculate(b).building
    b.rooms[0].equipment_sensible_btuh = 1500.0
    b.rooms[0].equipment_latent_btuh = -900.0
    res = calculate(b).building
    assert res.cool_equipment_sens == 1500.0
    assert res.cool_equipment_lat == -900.0
    assert res.cool_internal_sens == base.cool_internal_sens      # people and appliances unchanged
    assert res.cool_sensible == approx(base.cool_sensible + 1500.0)
    assert res.cool_latent == approx(base.cool_latent - 900.0)


def test_user_assigned_infiltration_shares():
    b = two_zone_house()
    b.zones[1].heating_setpoint_f = b.zones[1].cooling_setpoint_f = None
    b.infiltration = Infiltration(ela_in2=72.0)
    # By wall area the split would be 75 / 25; the user assigns 2 : 3 instead -> 40 % / 60 %
    b.rooms[0].infiltration_share = 2.0
    b.rooms[1].infiltration_share = 3.0
    res = calculate(b)
    assert res.room_wall_area_ratio == {"first": approx(0.4), "second": approx(0.6)}
    # Whole house 6311.4 Btu/h (see test above)
    assert res.rooms["second"].heat_infiltration == approx(6311.4 * 0.6, rel=2e-4)


def test_window_behind_open_porch_is_fully_shaded():
    # Wall and single-pane window (U 1.0, SHGC 0.7) facing an open porch at outdoor temperature.
    porch = BufferSpace("porch", "weighted", outdoor_weight=1.0)
    b = Building(conditions=conditions(), zones=[Zone("z")], rooms=[Room("parlor", "z", 300.0)],
                 buffer_spaces=[porch],
                 walls=[Wall("pw", "parlor", "porch", 200.0, r_value=4.0)],
                 windows=[Window("pwin", "pw", 30.0, 180.0, 1.0, 0.7)])
    room = calculate(b).rooms["parlor"]
    # Heating: 1.0 * (70 - 10) * 30 = 1800
    assert room.heat_windows == approx(1800.0)
    # Cooling, shaded glass at 40 deg latitude: PSF north 35 * average CLF north 0.48 * 0.7 / 0.87 + 1.0 * 20
    # = 13.517 + 20 = 33.517 Btu/h-ft2 -> x 30 = 1005.5 (a sunlit south window would be 28.77 + 20 = 48.77)
    assert room.cool_windows == approx(1005.5, rel=2e-4)
    # The wall behind the porch sees outdoor air but no sun: (95 - 75) / 4 * 170 = 850
    assert room.cool_walls == approx(850.0)


def test_window_facing_a_garage_conducts_only():
    b = Building(conditions=conditions(), zones=[Zone("z")], rooms=[Room("room", "z", 300.0)],
                 buffer_spaces=[BufferSpace("garage", "garage", heating_design_temp_f=30.0,
                                            cooling_design_temp_f=100.0)],
                 walls=[Wall("gw", "room", "garage", 200.0, r_value=13.0)],
                 windows=[Window("gwin", "gw", 10.0, 0.0, 0.5, 0.6)])
    room = calculate(b).rooms["room"]
    # 0.5 * (70 - 30) * 10 = 200; 0.5 * (100 - 75) * 10 = 125
    assert room.heat_windows == approx(200.0)
    assert room.cool_windows == approx(125.0)
