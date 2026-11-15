"""Read a defaulted HPXML file (the reference engine's ``in.xml``) into a RightTon
``Building``.

This is validation plumbing, not load math: it only moves inputs across. Where
the reference engine derives an input from HPXML-specific data (soil type ->
conductivity, buffer-space volumes), the same derivation is done here and cites
the OpenStudio-HPXML function it mirrors.

Anything the RightTon core does not model raises ``Unsupported`` with the reason,
so the comparison can report the house as skipped instead of silently comparing
different things.
"""

from __future__ import annotations

import gzip
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from rightton import model as M  # noqa: E402
from rightton import psychro, weather  # noqa: E402


class Unsupported(Exception):
    pass


ROOM_LOCATIONS = {"conditioned space": False, "basement - conditioned": True}
BUFFER_LOCATIONS = {
    "attic - vented": "attic_vented",
    "attic - unvented": "attic_unvented",
    "crawlspace - vented": "crawlspace_vented",
    "crawlspace - unvented": "crawlspace_unvented",
    "basement - unconditioned": "basement_unconditioned",
    "garage": "garage",
}
# Conditioned by someone else: surfaces to these carry no load in the reference
# (HPXML::conditioned_locations includes them).
ADIABATIC_LOCATIONS = {"other housing unit"}
# Mirrors Geometry.get_temperature_scheduled_space_values:
# (min temp F, indoor weight, outdoor weight, ground weight, duct regain)
WEIGHTED_LOCATIONS = {
    "other heated space": (68.0, 0.5, 0.5, 0.0, 0.0),
    "other multifamily buffer space": (50.0, 0.5, 0.5, 0.0, 0.0),
    "other non-freezing space": (40.0, 0.0, 1.0, 0.0, 0.0),
    "other housing unit": (None, 1.0, 0.0, 0.0, 0.0),  # as a duct location only
    "exterior wall": (None, 0.5, 0.5, 0.0, 0.5),
    "under slab": (None, 0.0, 0.0, 1.0, 0.83),
}

WALL_TYPES = {
    "WoodStud": "wood_stud", "SteelFrame": "steel_stud", "DoubleWoodStud": "double_wood_stud",
    "StructuralInsulatedPanel": "sip", "ConcreteMasonryUnit": "cmu", "StructuralBrick": "brick",
    "Adobe": "adobe", "SolidConcrete": "concrete", "Stone": "stone", "LogWall": "log",
    "InsulatedConcreteForms": "icf", "StrawBale": "straw_bale",
}
SIDING = {"brick veneer": "brick", "stone": "stone"}
FOUNDATION_WALL_TYPES = {
    "solid concrete": "solid_concrete", "double brick": "double_brick", "wood": "wood",
    "concrete block": "concrete_block", "concrete block solid core": "concrete_block_solid_core",
    "concrete block perlite core": "concrete_block_perlite_core",
    "concrete block foam core": "concrete_block_foam_core",
    "concrete block vermiculite core": "concrete_block_vermiculite_core",
}
ROOF_TYPES = {
    "asphalt or fiberglass shingles": "asphalt_shingles", "shingles": "shingles",
    "wood shingles or shakes": "wood_shingles", "metal surfacing": "metal",
    "plastic/rubber/synthetic sheeting": "plastic_rubber", "expanded polystyrene sheathing": "eps",
    "slate or tile shingles": "clay_tile", "concrete": "concrete",
}
GLASS_LAYERS = {"single-pane": 1, "double-pane": 2, "triple-pane": 3}
GLASS_TYPES = {
    "clear": "clear", "tinted": "tinted", "reflective": "reflective", "tinted/reflective": "tinted_reflective",
    "low-e": "low_e", "low-e, low-solar-gain": "low_e_low_solar", "low-e, high-solar-gain": "low_e_high_solar",
}
FAN_TYPES = {
    "supply only": "supply", "exhaust only": "exhaust", "balanced": "balanced",
    "energy recovery ventilator": "erv", "heat recovery ventilator": "hrv",
    "central fan integrated supply": "cfis",
}
LEAKINESS = {"very tight": "very_tight", "tight": "tight", "average": "average", "leaky": "leaky",
             "very leaky": "very_leaky"}


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _txt(el, path, default=None):
    if el is None:
        return default
    found = el.find(path)
    return default if found is None or found.text is None else found.text.strip()


def _num(el, path, default=None):
    value = _txt(el, path)
    return default if value is None else float(value)


def _bool(el, path, default=False):
    value = _txt(el, path)
    return default if value is None else value == "true"


def _is_defaulted(el, path):
    found = el.find(path)
    return found is not None and found.get("dataSource") == "software"


def load_weather(epw_dir, epw_name) -> weather.Weather:
    """Weather for a house: the EPW file if present, otherwise the JSON summary
    of it that the comparison snapshot stores (EPW files are large)."""
    epw = Path(epw_dir) / Path(epw_name).name
    if epw.exists():
        return weather.read_epw(epw)
    summary = epw.with_suffix(".json")
    if summary.exists():
        return weather.Weather(**json.loads(summary.read_text()))
    raise FileNotFoundError(f"No weather file or summary for {epw.name} in {epw_dir}")


def parse(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        return _strip_ns(ET.parse(f).getroot())


def load(path, epw_dir) -> M.Building:
    root = parse(path)
    buildings = root.findall("Building")
    if len(buildings) != 1:
        raise Unsupported("file holds more than one dwelling unit")
    b = buildings[0]
    details = b.find("BuildingDetails")
    summary = details.find("BuildingSummary")
    constr = summary.find("BuildingConstruction")
    enclosure = details.find("Enclosure")
    mj = summary.find("extension/HVACSizingControl/ManualJInputs")

    # --- Weather and design conditions ------------------------------------
    epw_name = _txt(details, "ClimateandRiskZones/WeatherStation/extension/EPWFilePath")
    wx = load_weather(epw_dir, epw_name)
    soil = summary.find("Site/Soil")
    conditions = M.DesignConditions(
        heating_design_temp_f=_num(mj, "HeatingDesignTemperature"),
        cooling_design_temp_f=_num(mj, "CoolingDesignTemperature"),
        daily_temp_range=_txt(mj, "DailyTemperatureRange"),
        humidity_difference_grains=_num(mj, "HumidityDifference"),
        latitude_deg=_num(b, "Site/GeoLocation/Latitude"),
        elevation_ft=_num(b, "Site/Elevation"),
        heating_setpoint_f=_num(mj, "HeatingSetpoint"),
        cooling_setpoint_f=_num(mj, "CoolingSetpoint"),
        humidity_setpoint_frac=_num(mj, "HumiditySetpoint"),
        ground_conductivity_btu_h_ft_f=_ground_conductivity(soil),
        cooling_humidity_ratio=wx.cooling_humidity_ratio,
        annual_avg_drybulb_f=wx.annual_avg_drybulb_f,
        ground_temp_winter_f=min(wx.shallow_ground_monthly_f),
        ground_temp_summer_f=max(wx.shallow_ground_monthly_f),
        wsf=wx.wsf,
    )

    if _num(constr, "NumberofUnits", 1) > 1:
        raise Unsupported("unit multiplier (reference reports loads for all identical units together)")
    cfa = _num(constr, "ConditionedFloorArea")
    bldg = M.Building(
        conditions=conditions, zones=[], rooms=[],
        stories_above_grade=_num(constr, "NumberofConditionedFloorsAboveGrade"),
        facility_type={"single-family detached": "single_family_detached"}.get(
            _txt(constr, "ResidentialFacilityType"), "attached"),
        conditioned_floor_area_ft2=cfa,
    )

    # --- Zones and rooms ------------------------------------------------------
    space_of = {}  # surface id -> space id (explicit HPXML Spaces)
    explicit = details.find("Zones") is not None
    if explicit:
        for z in details.findall("Zones/Zone"):
            if _txt(z, "ZoneType") != "conditioned":
                continue
            zid = z.find("SystemIdentifier").get("id")
            bldg.zones.append(M.Zone(zid))
            for s in z.findall("Spaces/Space"):
                mjs = s.find("extension/ManualJInputs")
                bldg.rooms.append(M.Room(
                    id=s.find("SystemIdentifier").get("id"), zone=zid, floor_area_ft2=_num(s, "FloorArea"),
                    ceiling_height_ft=_num(constr, "AverageCeilingHeight", 8.0),
                    occupants=_num(mjs, "NumberofOccupants", 0.0),
                    internal_sensible_btuh=_num(mjs, "InternalLoadsSensible", 0.0),
                    internal_latent_btuh=_num(mjs, "InternalLoadsLatent", 0.0)))
    else:
        bldg.zones.append(M.Zone("zone"))
        basement_area = sum(_num(s, "Area") for s in enclosure.findall("Slabs/Slab")
                            if _txt(s, "InteriorAdjacentTo") == "basement - conditioned")
        bldg.rooms.append(M.Room(
            id="conditioned space", zone="zone", floor_area_ft2=cfa - basement_area,
            ceiling_height_ft=_num(constr, "AverageCeilingHeight", 8.0),
            occupants=_num(mj, "NumberofOccupants", 0.0),
            internal_sensible_btuh=_num(mj, "InternalLoadsSensible", 0.0),
            internal_latent_btuh=_num(mj, "InternalLoadsLatent", 0.0)))
        if basement_area > 0 or _has_location(enclosure, "basement - conditioned"):
            bldg.rooms.append(M.Room(id="basement - conditioned", zone="zone", floor_area_ft2=basement_area,
                                     below_grade=True))

    def space_id(el):
        ref = el.find("AttachedToSpace")
        return None if ref is None else ref.get("idref")

    def resolve(el, location):
        """Map an HPXML location to a room id, a buffer id, OUTSIDE or GROUND."""
        if location in (None, "outside"):
            return M.OUTSIDE
        if location == "ground":
            return M.GROUND
        if location in ROOM_LOCATIONS:
            if explicit:
                sid = space_id(el)
                if sid is None:
                    raise Unsupported("surface next to conditioned space is not attached to a space")
                if ROOM_LOCATIONS[location]:
                    bldg.room(sid).below_grade = True
                return sid
            return location
        if location in BUFFER_LOCATIONS:
            if bldg.buffer(location) is None:
                bldg.buffer_spaces.append(M.BufferSpace(location, BUFFER_LOCATIONS[location]))
            return location
        if location in ADIABATIC_LOCATIONS:
            return M.ADIABATIC
        if location in WEIGHTED_LOCATIONS:
            return _weighted_space(bldg, location)
        raise Unsupported(f"location '{location}'")

    def sides(el, keep_interior=False):
        """(inside, outside) with the conditioned room, if any, on the inside."""
        inside = resolve(el, _txt(el, "InteriorAdjacentTo"))
        outside = resolve(el, _txt(el, "ExteriorAdjacentTo"))
        if inside == M.ADIABATIC:
            inside, outside = outside, inside
        if not bldg.is_room(inside) and bldg.is_room(outside):
            inside, outside = outside, inside
        if bldg.is_room(inside) and bldg.is_room(outside):
            # Between two conditioned rooms: no load in the reference. Foundation
            # walls are kept (as adiabatic) because basement geometry uses them.
            return (inside, M.ADIABATIC) if keep_interior else None
        return inside, outside

    def assembly_r(el):
        return _num(el, "Insulation/AssemblyEffectiveRValue")

    def sid(el):
        return el.find("SystemIdentifier").get("id")

    # --- Opaque surfaces ------------------------------------------------------
    for el in enclosure.findall("Walls/Wall") + enclosure.findall("RimJoists/RimJoist"):
        s = sides(el)
        if s is None:
            continue
        wall_type_el = el.find("WallType")
        wall_type = "wood_stud" if wall_type_el is None else WALL_TYPES[wall_type_el[0].tag]
        bldg.walls.append(M.Wall(
            id=sid(el), inside=s[0], outside=s[1], area_ft2=_num(el, "Area"), r_value=assembly_r(el),
            wall_type=wall_type, siding=SIDING.get(_txt(el, "Siding"), "light"),
            solar_absorptance=_num(el, "SolarAbsorptance", 0.7), is_rim_joist=el.tag == "RimJoist"))

    for el in enclosure.findall("FoundationWalls/FoundationWall"):
        s = sides(el, keep_interior=True)
        if s is None:
            continue
        height = _num(el, "Height")
        area = _num(el, "Area")
        length = _num(el, "Length")
        if area is None:
            area = length * height
        fw = M.FoundationWall(
            id=sid(el), inside=s[0], outside=s[1], area_ft2=area, r_value=assembly_r(el), height_ft=height,
            depth_below_grade_ft=_num(el, "DepthBelowGrade"), thickness_in=_num(el, "Thickness"),
            wall_type=FOUNDATION_WALL_TYPES[_txt(el, "Type")], azimuth_deg=_num(el, "Azimuth"), length_ft=length)
        for layer in el.findall("Insulation/Layer"):
            kind = _txt(layer, "InstallationType")
            r = _num(layer, "NominalRValue", 0.0)
            top = _num(layer, "DistanceToTopOfInsulation", 0.0)
            bottom = _num(layer, "DistanceToBottomOfInsulation", 0.0)
            if kind == "continuous - interior":
                fw.insulation_interior_r, fw.insulation_interior_top_ft, fw.insulation_interior_bottom_ft = r, top, bottom
            elif kind == "continuous - exterior":
                fw.insulation_exterior_r, fw.insulation_exterior_top_ft, fw.insulation_exterior_bottom_ft = r, top, bottom
        bldg.foundation_walls.append(fw)

    for el in enclosure.findall("Roofs/Roof"):
        inside = resolve(el, _txt(el, "InteriorAdjacentTo"))
        bldg.roofs.append(M.Roof(
            id=sid(el), inside=inside, outside=M.OUTSIDE, area_ft2=_num(el, "Area"), r_value=assembly_r(el),
            roof_type=ROOF_TYPES[_txt(el, "RoofType")], roof_color=_txt(el, "RoofColor").replace(" ", "_"),
            radiant_barrier=_bool(el, "RadiantBarrier"), pitch=_num(el, "Pitch")))

    for el in enclosure.findall("Floors/Floor"):
        s = sides(el)
        if s is None:
            continue
        bldg.floors.append(M.Floor(
            id=sid(el), inside=s[0], outside=s[1], area_ft2=_num(el, "Area"), r_value=assembly_r(el),
            is_ceiling=_is_ceiling(el)))

    for el in enclosure.findall("Slabs/Slab"):
        inside = resolve(el, _txt(el, "InteriorAdjacentTo"))
        under = el.find("UnderSlabInsulation")
        bldg.slabs.append(M.Slab(
            id=sid(el), inside=inside, area_ft2=_num(el, "Area"), exposed_perimeter_ft=_num(el, "ExposedPerimeter"),
            thickness_in=_num(el, "Thickness"),
            perimeter_insulation_r=_num(el, "PerimeterInsulation/Layer/NominalRValue", 0.0),
            perimeter_insulation_depth_ft=_num(el, "PerimeterInsulation/Layer/InsulationDepth", 0.0),
            under_slab_insulation_r=_num(under, "Layer/NominalRValue", 0.0),
            under_slab_insulation_width_ft=_num(under, "Layer/InsulationWidth", 0.0),
            under_slab_insulation_spans_slab=_bool(under, "Layer/InsulationSpansEntireSlab"),
            exterior_horizontal_insulation_r=_num(el, "ExteriorHorizontalInsulation/Layer/NominalRValue", 0.0),
            exterior_horizontal_insulation_width_ft=_num(el, "ExteriorHorizontalInsulation/Layer/InsulationWidth", 0.0),
            exterior_horizontal_insulation_depth_below_grade_ft=_num(
                el, "ExteriorHorizontalInsulation/Layer/InsulationDepthBelowGrade", 0.0)))

    # --- Openings -----------------------------------------------------------
    wall_ids = {w.id for w in [*bldg.walls, *bldg.foundation_walls]}
    for el in enclosure.findall("Windows/Window"):
        wall = el.find("AttachedToWall").get("idref")
        if wall not in wall_ids:
            continue
        shade = el.find("InteriorShading")
        ext = el.find("ExteriorShading")
        screen = el.find("InsectScreen")
        shade_type = _txt(shade, "Type")
        if shade_type is not None:
            shade_type = {"not present": "none"}.get(shade_type, shade_type.replace(" ", "_"))
        ext_type = _txt(ext, "Type")
        storm = _txt(el, "StormWindow/GlassType")
        bldg.windows.append(M.Window(
            id=sid(el), wall=wall, area_ft2=_num(el, "Area"), azimuth_deg=_num(el, "Azimuth"),
            u_factor=_num(el, "UFactor"), shgc=_num(el, "SHGC"),
            storm=None if storm is None else {"clear": "clear", "low-e": "low_e"}[storm],
            interior_shading_type=shade_type,
            interior_shading_coverage=_num(shade, "SummerFractionCovered", 0.5),
            blinds_position={"closed": "closed", "open": "open", "half open": "half_open"}.get(
                _txt(shade, "BlindsSummerClosedOrOpen"), "closed"),
            interior_shading_coefficient=_num(shade, "SummerShadingCoefficient", 1.0),
            glass_layers=GLASS_LAYERS.get(_txt(el, "GlassLayers")),
            glass_type=GLASS_TYPES.get(_txt(el, "GlassType"), "clear") if _txt(el, "GlassLayers") else None,
            exterior_shading_type={"solar screens": "solar_screens", "solar film": "solar_film"}.get(ext_type),
            exterior_shading_coefficient=_num(ext, "SummerShadingCoefficient"),
            insect_screen=None if screen is None else _txt(screen, "Location"),
            insect_screen_coverage=_num(screen, "SummerFractionCovered", 1.0),
            overhang_depth_ft=_num(el, "Overhangs/Depth", 0.0),
            overhang_to_window_top_ft=_num(el, "Overhangs/DistanceToTopOfWindow", 0.0),
            overhang_to_window_bottom_ft=_num(el, "Overhangs/DistanceToBottomOfWindow", 0.0)))

    for el in enclosure.findall("Skylights/Skylight"):
        floor_ref = el.find("AttachedToFloor")
        storm = _txt(el, "StormWindow/GlassType")
        bldg.skylights.append(M.Skylight(
            id=sid(el), roof=el.find("AttachedToRoof").get("idref"), area_ft2=_num(el, "Area"),
            azimuth_deg=_num(el, "Azimuth"), u_factor=_num(el, "UFactor"), shgc=_num(el, "SHGC"),
            ceiling=None if floor_ref is None else floor_ref.get("idref"),
            storm=None if storm is None else {"clear": "clear", "low-e": "low_e"}[storm],
            interior_shading_coefficient=_num(el, "InteriorShading/SummerShadingCoefficient", 1.0),
            curb_area_ft2=_num(el, "extension/Curb/Area"),
            curb_r_value=_num(el, "extension/Curb/AssemblyEffectiveRValue"),
            shaft_area_ft2=_num(el, "extension/Shaft/Area"),
            shaft_r_value=_num(el, "extension/Shaft/AssemblyEffectiveRValue")))

    for el in enclosure.findall("Doors/Door"):
        wall = el.find("AttachedToWall").get("idref")
        if wall in wall_ids:
            bldg.doors.append(M.Door(id=sid(el), wall=wall, area_ft2=_num(el, "Area"), r_value=_num(el, "RValue")))

    _set_buffer_volumes_and_vents(bldg, enclosure)
    _read_infiltration(bldg, details, enclosure, mj)
    _read_ventilation(bldg, details)
    _read_hvac(bldg, details)
    return bldg


def _weighted_space(bldg, location):
    if bldg.buffer(location) is None:
        min_temp, w_in, w_out, w_ground, regain = WEIGHTED_LOCATIONS[location]
        bldg.buffer_spaces.append(M.BufferSpace(location, "weighted", indoor_weight=w_in, outdoor_weight=w_out,
                                                ground_weight=w_ground, min_temp_f=min_temp, duct_regain=regain))
    return location


def _has_location(enclosure, location):
    return any(el.text == location for el in enclosure.iter() if el.tag in ("InteriorAdjacentTo", "ExteriorAdjacentTo"))


def _ground_conductivity(soil):
    """Mirrors process_site_calcs_and_design_temps: soil and moisture type, when
    both are known, override the conductivity value."""
    soil_type, moisture = _txt(soil, "SoilType"), _txt(soil, "MoistureType")
    if soil_type is not None and moisture is not None:
        if soil_type in ("clay", "unknown", "other") and moisture in ("wet", "mixed"):
            return 1.0 / 1.25
        if soil_type in ("sand", "gravel", "silt") and moisture == "dry":
            return 1.0 / 5.0
        return 1.0 / 2.0
    return _num(soil, "Conductivity")


def _is_ceiling(el):
    """Mirrors HPXML::Floor#is_ceiling / HPXML.is_floor_a_ceiling."""
    explicit = _txt(el, "FloorOrCeiling")
    if explicit is not None:
        return explicit == "ceiling"
    locations = (_txt(el, "InteriorAdjacentTo"), _txt(el, "ExteriorAdjacentTo"))
    return any(loc in ("attic - unconditioned", "attic - vented", "attic - unvented") for loc in locations)


def _set_buffer_volumes_and_vents(bldg, enclosure):
    """Mirrors Geometry.calculate_zone_volume / calculate_zone_height /
    calculate_height_and_footprint_of_roofs."""
    default_height = {"basement_unconditioned": 8.0, "crawlspace_unvented": 3.0, "crawlspace_vented": 3.0,
                      "garage": 8.0}
    for space in bldg.buffer_spaces:
        if space.kind == "weighted":
            continue
        if space.kind in ("attic_vented", "attic_unvented"):
            roofs = [r for r in bldg.roofs if r.inside == space.id]
            if not roofs:
                space.volume_ft3 = 0.01
                continue
            pitch = sum(r.pitch for r in roofs) / len(roofs)
            footprint = sum(r.area_ft2 for r in roofs) / math.sqrt((pitch / 12.0) ** 2 + 1)
            height = 0.5 * math.sin(math.atan(pitch / 12.0)) * math.sqrt(footprint) if pitch > 0 else 2.0
            space.volume_ft3 = max(footprint * height / 3.0, 0.01)
        else:
            floor_area = sum(s.area_ft2 for s in bldg.slabs if s.inside == space.id)
            heights = [fw.height_ft for fw in bldg.foundation_walls if fw.inside == space.id]
            space.volume_ft3 = floor_area * (max(heights) if heights else default_height[space.kind])
    for attic in enclosure.findall("Attics/Attic"):
        if _txt(attic, "AtticType/Attic/Vented") == "true" and bldg.buffer("attic - vented") is not None:
            rate, unit = _num(attic, "VentilationRate/Value"), _txt(attic, "VentilationRate/UnitofMeasure")
            if unit == "SLA":
                bldg.buffer("attic - vented").vent_sla = rate
            elif unit == "ACHnatural":
                bldg.buffer("attic - vented").vent_ach = rate
    for fnd in enclosure.findall("Foundations/Foundation"):
        if _txt(fnd, "FoundationType/Crawlspace/Vented") == "true" and bldg.buffer("crawlspace - vented") is not None:
            bldg.buffer("crawlspace - vented").vent_sla = _num(fnd, "VentilationRate/Value")


def _read_infiltration(bldg, details, enclosure, mj):
    """Mirrors Airflow.get_infiltration_measurement_of_interest."""
    method = {"blower door": "blower_door", "default infiltration table": "default_table"}[
        _txt(mj, "InfiltrationMethod")]
    infil = M.Infiltration(method=method, shielding_class=int(_num(mj, "InfiltrationShieldingClass", 4)))
    measurements = enclosure.findall("AirInfiltration/AirInfiltrationMeasurement")
    chosen = None
    if method == "blower_door":
        for m in measurements:
            unit, leak = _txt(m, "BuildingAirLeakage/UnitofMeasure"), _num(m, "BuildingAirLeakage/AirLeakage")
            if leak is not None:
                if unit in ("ACH", "CFM") and _num(m, "HousePressure") is not None:
                    chosen = m
                elif unit in ("ACHnatural", "CFMnatural"):
                    chosen = m
            elif _num(m, "EffectiveLeakageArea") is not None or _num(m, "extension/SpecificLeakageArea") is not None \
                    or _num(m, "SpecificLeakageArea") is not None:
                chosen = m
            if chosen is not None:
                break
        if chosen is None:
            raise Unsupported("no usable blower-door measurement")
        unit, leak = _txt(chosen, "BuildingAirLeakage/UnitofMeasure"), _num(chosen, "BuildingAirLeakage/AirLeakage")
        infil.volume_ft3 = _num(chosen, "InfiltrationVolume")
        infil.height_ft = _num(chosen, "InfiltrationHeight")
        infil.house_pressure_pa = _num(chosen, "HousePressure", 50.0)
        if unit == "ACH":
            infil.ach50 = leak
        elif unit == "CFM":
            infil.cfm50 = leak
        elif unit == "ACHnatural":
            infil.natural_ach = leak
        elif unit == "CFMnatural":
            infil.natural_ach = leak * 60.0 / infil.volume_ft3
        elif _num(chosen, "EffectiveLeakageArea") is not None:
            infil.ela_in2 = _num(chosen, "EffectiveLeakageArea")
        else:
            infil.sla = _num(chosen, "extension/SpecificLeakageArea", _num(chosen, "SpecificLeakageArea"))
        if _txt(chosen, "TypeOfInfiltrationLeakage") == "unit total":
            infil.exterior_fraction = _num(chosen, "extension/Aext", 1.0)
    else:
        chosen = next((m for m in measurements if _txt(m, "LeakinessDescription")), None)
        if chosen is None:
            raise Unsupported("no leakiness description")
        infil.leakiness = LEAKINESS[_txt(chosen, "LeakinessDescription")]
        # Mirrors HPXML::Building#above_grade_conditioned_volume
        volume = _num(details, "BuildingSummary/BuildingConstruction/ConditionedBuildingVolume")
        walls = [fw for fw in bldg.foundation_walls if fw.outside == M.GROUND and bldg.is_room(fw.inside)
                 and bldg.room(fw.inside).below_grade]
        floor_area = sum(s.area_ft2 for s in bldg.slabs if bldg.is_room(s.inside) and bldg.room(s.inside).below_grade)
        if floor_area > 0:
            perimeter = sum(fw.area_ft2 / fw.height_ft for fw in walls)
            volume -= sum(fw.depth_below_grade_ft * fw.area_ft2 / fw.height_ft for fw in walls) / perimeter * floor_area
        bldg.above_grade_volume_ft3 = volume
    has_fireplace = any(_txt(fl, "FuelLoadType") == "fireplace" for fl in details.iter("FuelLoad"))
    has_fireplace |= any(hs.find("HeatingSystemType/Fireplace") is not None for hs in details.iter("HeatingSystem"))
    infil.has_fireplace = has_fireplace
    summary = details.find("BuildingSummary")
    infil.unit_height_above_grade_ft = _num(summary, "BuildingConstruction/UnitHeightAboveGrade", 0.0)
    infil.site_shielding = {"normal": "normal", "exposed": "exposed", "well-shielded": "well_shielded"}[
        _txt(summary, "Site/ShieldingofHome", "normal")]
    bldg.infiltration = infil


def _read_ventilation(bldg, details):
    for fan in details.iter("VentilationFan"):
        if not _bool(fan, "UsedForWholeBuildingVentilation"):
            continue
        if _bool(fan, "CFISControls/SupplementalFan") or fan.find("CFISControls/SupplementalFan") is not None:
            pass
        flow = None
        for tag in ("RatedFlowRate", "CalculatedFlowRate", "TestedFlowRate", "DeliveredVentilation"):
            flow = _num(fan, tag) if flow is None else flow
        hours = _num(fan, "HoursInOperation", 24.0)
        if not flow or not hours:
            continue
        kind = FAN_TYPES[_txt(fan, "FanType")]
        if kind in ("erv", "hrv"):
            raise Unsupported("ERV/HRV (rated-efficiency to effectiveness conversion not ported)")
        if kind == "cfis":
            raise Unsupported("central-fan-integrated ventilation (CFIS)")
        if _bool(fan, "IsSharedSystem"):
            raise Unsupported("shared ventilation system")
        bldg.ventilation_fans.append(M.VentilationFan(kind, flow * hours / 24.0))


def _read_hvac(bldg, details):
    hvac = details.find("Systems/HVAC")
    if hvac is None:
        return
    plant = hvac.find("HVACPlant")
    if plant is None:
        return
    distributions = {d.find("SystemIdentifier").get("id"): d for d in hvac.findall("HVACDistribution")}

    def zone_id(el):
        ref = el.find("AttachedToZone")
        return bldg.zones[0].id if ref is None else ref.get("idref")

    def dist_id(el):
        ref = el.find("DistributionSystem")
        return None if ref is None else ref.get("idref")

    def cfm_per_ton(el, flow_tag, capacity_tag, default):
        flow, capacity = _num(el, flow_tag), _num(el, capacity_tag)
        if flow is not None and capacity and not _is_defaulted(el, flow_tag) and not _is_defaulted(el, capacity_tag):
            return flow / (capacity / 12000.0)
        return default

    for zone in bldg.zones:
        heating = [e for e in plant.findall("HeatingSystem") if zone_id(e) == zone.id]
        cooling = [e for e in plant.findall("CoolingSystem") if zone_id(e) == zone.id]
        pumps = [e for e in plant.findall("HeatPump") if zone_id(e) == zone.id]
        if len(heating) + len(pumps) > 1 or len(cooling) + len(pumps) > 1:
            raise Unsupported("more than one heating or cooling system in a zone")
        for el in heating + cooling + pumps:
            for tag in ("FractionHeatLoadServed", "FractionCoolLoadServed"):
                frac = _num(el, tag)
                if frac is not None and 0 < frac < 1 and len(bldg.zones) == 1:
                    raise Unsupported("HVAC system serving part of the load")
            if _num(el, "IntegratedHeatingSystemFractionHeatLoadServed") is not None:
                raise Unsupported("cooling system with integrated heating")
        for el in heating:
            if _txt(el, "HeatingSystemType/ElectricResistance/ElectricDistribution") == "radiant floor":
                zone.has_radiant_floor = True
            d = distributions.get(dist_id(el))
            if d is not None and _txt(
                    d, "DistributionSystemType/HydronicDistribution/HydronicDistributionType") == "radiant floor":
                zone.has_radiant_floor = True

        heat_el = (heating + pumps)[0] if heating + pumps else None
        cool_el = (cooling + pumps)[0] if cooling + pumps else None
        # A system that serves none of the load gets no duct load in the reference
        if heat_el is not None and _num(heat_el, "FractionHeatLoadServed", 1.0) == 0:
            heat_el = None
        if cool_el is not None and _num(cool_el, "FractionCoolLoadServed", 1.0) == 0:
            cool_el = None
        if cool_el is not None and _txt(cool_el, "CoolingSystemType") == "evaporative cooler":
            raise Unsupported("evaporative cooler")
        if heat_el is not None and heat_el.tag == "HeatPump" and _txt(heat_el, "HeatPumpType") == "water-loop-to-air":
            raise Unsupported("water-loop heat pump")
        systems = {}
        for el, mode in ((heat_el, "heat"), (cool_el, "cool")):
            if el is None or dist_id(el) is None:
                continue
            system = systems.get(dist_id(el))
            if system is None:
                system = _read_distribution(bldg, distributions[dist_id(el)], zone)
                system.has_heating = system.has_cooling = False
                systems[dist_id(el)] = system
            if mode == "heat":
                system.has_heating = True
                default = 240.0
                if el.tag == "HeatPump":
                    default = cfm_per_ton(el, "extension/CoolingDesignAirflowCFM", "CoolingCapacity", 360.0)
                system.heating_cfm_per_ton = cfm_per_ton(el, "extension/HeatingDesignAirflowCFM", "HeatingCapacity",
                                                         default)
            else:
                system.has_cooling = True
                default = 360.0
                if el.tag == "HeatPump":
                    default = cfm_per_ton(el, "extension/HeatingDesignAirflowCFM", "HeatingCapacity", 360.0)
                system.cooling_cfm_per_ton = cfm_per_ton(el, "extension/CoolingDesignAirflowCFM", "CoolingCapacity",
                                                         default)
        bldg.distribution_systems.extend(systems.values())


def _read_distribution(bldg, d, zone):
    air = d.find("DistributionSystemType/AirDistribution")
    hydronic = d.find("DistributionSystemType/HydronicDistribution")
    system = M.DistributionSystem(zone=zone.id)
    if hydronic is not None:
        system.piping_btuh = _num(hydronic, "extension/ManualJInputs/HotWaterPipingBtuh", 0.0)
    if air is None:
        return system
    if air.find("extension/ManualJInputs/DefaultTableDuctLoad") is not None:
        raise Unsupported("tabulated default duct loads")
    system.blower_heat_btuh = _num(air, "extension/ManualJInputs/BlowerFanHeatBtuh", 0.0)
    units = set()
    for m in air.findall("DuctLeakageMeasurement"):
        if _txt(m, "DuctLeakage/TotalOrToOutside") != "to outside":
            continue
        duct_type, value, unit = _txt(m, "DuctType"), _num(m, "DuctLeakage/Value"), _txt(m, "DuctLeakage/Units")
        if duct_type not in ("supply", "return"):
            continue
        units.add(unit)
        if duct_type == "supply":
            system.supply_leakage += value
        else:
            system.return_leakage += value
    if len(units) > 1:
        raise Unsupported("mixed duct leakage units")
    if units:
        system.leakage_units = {"CFM25": "cfm25", "CFM50": "cfm50", "Percent": "fraction"}[units.pop()]
    for duct in air.findall("Ducts"):
        location = _txt(duct, "DuctLocation")
        if location in ROOM_LOCATIONS:
            location = bldg.zone_rooms(zone.id)[0].id
        elif location == "outside":
            location = M.OUTSIDE
        elif location in BUFFER_LOCATIONS:
            if bldg.buffer(location) is None:
                raise Unsupported(f"ducts in '{location}', which has no surfaces")
        elif location in WEIGHTED_LOCATIONS:
            _weighted_space(bldg, location)
        else:
            raise Unsupported(f"duct location '{location}'")
        system.ducts.append(M.Duct(
            duct_type=_txt(duct, "DuctType"), location=location, surface_area_ft2=_num(duct, "DuctSurfaceArea"),
            effective_r_value=_num(duct, "DuctEffectiveRValue"),
            area_multiplier=_num(duct, "extension/DuctSurfaceAreaMultiplier", 1.0)))
    return system
