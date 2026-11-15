# Ported from OpenStudio-HPXML (BSD-style license; see core/NOTICE-OpenStudio-HPXML.md).
# OpenStudio(R) HPXML, Copyright (c) 2008-2026, Alliance for Energy Innovation, LLC,
# and other contributors. All rights reserved.
#
# Source: HPXMLtoOpenStudio/resources/hvac_sizing.rb (HVACSizing.calculate and the
# process_load_* / apply_hvac_* functions named in the comments below).
"""Design-load calculation: rooms -> zones -> building.

``calculate(building)`` returns a ``Results`` object holding a ``Loads`` record
(Btu/h by component) for every room, every zone and the whole building, plus
per-surface details and the intermediate values a report needs to show.

Differences from the reference engine (each is also listed in
validation/RESULTS.md):

* Rooms get latent loads and a share of ventilation load; the reference reports
  only sensible loads for rooms and assigns ventilation to zones only.
* Partitions between rooms of zones with different setpoints carry a
  zone-to-zone transfer load; the reference has a single setpoint and no such
  load. With equal setpoints the transfer is zero and results are identical.
* Not ported (v1): heat pumps, geothermal, equipment selection, the tabulated
  default duct loads, ventilation through the air handler (CFIS), multifamily
  shared spaces and shared ventilation systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Optional

from . import airflow, ducts, envelope, fenestration as fen, psychro, spaces, tables as T
from .foundation import (basement_slab_u, foundation_wall_above_grade_u, foundation_wall_below_grade_u,
                         slab_f_value)
from .model import GROUND, OUTSIDE, Building, FoundationWall

HEAT_COMPONENTS = ("heat_windows", "heat_skylights", "heat_doors", "heat_walls", "heat_roofs", "heat_floors",
                   "heat_slabs", "heat_ceilings", "heat_infiltration", "heat_ventilation", "heat_interzone",
                   "heat_piping", "heat_ducts")
COOL_SENS_COMPONENTS = ("cool_windows", "cool_skylights", "cool_doors", "cool_walls", "cool_roofs", "cool_floors",
                        "cool_slabs", "cool_ceilings", "cool_infiltration_sens", "cool_ventilation_sens",
                        "cool_internal_sens", "cool_interzone", "cool_blower_heat", "cool_aed_excursion",
                        "cool_ducts_sens")
COOL_LAT_COMPONENTS = ("cool_infiltration_lat", "cool_ventilation_lat", "cool_internal_lat", "cool_ducts_lat")


@dataclass
class Loads:
    """Design loads in Btu/h. Totals are filled in by ``update_totals``."""

    heat_windows: float = 0.0
    heat_skylights: float = 0.0
    heat_doors: float = 0.0
    heat_walls: float = 0.0
    heat_roofs: float = 0.0
    heat_floors: float = 0.0
    heat_slabs: float = 0.0
    heat_ceilings: float = 0.0
    heat_infiltration: float = 0.0
    heat_ventilation: float = 0.0
    heat_interzone: float = 0.0
    heat_piping: float = 0.0
    heat_ducts: float = 0.0
    heat_total: float = 0.0

    cool_windows: float = 0.0
    cool_skylights: float = 0.0
    cool_doors: float = 0.0
    cool_walls: float = 0.0
    cool_roofs: float = 0.0
    cool_floors: float = 0.0
    cool_slabs: float = 0.0
    cool_ceilings: float = 0.0
    cool_infiltration_sens: float = 0.0
    cool_ventilation_sens: float = 0.0
    cool_internal_sens: float = 0.0
    cool_interzone: float = 0.0
    cool_blower_heat: float = 0.0
    cool_aed_excursion: float = 0.0
    cool_ducts_sens: float = 0.0
    cool_sensible: float = 0.0

    cool_infiltration_lat: float = 0.0
    cool_ventilation_lat: float = 0.0
    cool_internal_lat: float = 0.0
    cool_ducts_lat: float = 0.0
    cool_latent: float = 0.0

    cool_total: float = 0.0
    hourly_fenestration: list[float] = field(default_factory=lambda: [0.0] * fen.HOURS)  # hours 8..19

    def update_totals(self) -> None:
        """Source: aggregate_loads_to_totals."""
        self.heat_total = sum(getattr(self, c) for c in HEAT_COMPONENTS)
        self.cool_sensible = sum(getattr(self, c) for c in COOL_SENS_COMPONENTS)
        self.cool_latent = sum(getattr(self, c) for c in COOL_LAT_COMPONENTS)
        self.cool_total = self.cool_sensible + self.cool_latent

    def add(self, other: "Loads") -> None:
        for f in fields(self):
            if f.name == "hourly_fenestration":
                self.hourly_fenestration = [a + b for a, b in zip(self.hourly_fenestration, other.hourly_fenestration)]
            else:
                setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))

    @property
    def cool_tons(self) -> float:
        return self.cool_total / psychro.BTUH_PER_TON

    @property
    def sensible_heat_ratio(self) -> float:
        return self.cool_sensible / self.cool_total if self.cool_total else 0.0


@dataclass
class SurfaceDetail:
    """One line of the component breakdown."""

    kind: str  # windows, skylights, doors, walls, walls_below_grade, roofs, ceilings, floors, slabs, interzone
    id: str
    room: str
    area_ft2: float  # for near-grade slabs this is exposed perimeter in ft
    heat_htm: float  # Btu/h per ft2 (per ft for near-grade slabs)
    cool_htm: float
    heat_btuh: float
    cool_btuh: float


@dataclass
class Results:
    building: Loads
    zones: dict[str, Loads]
    rooms: dict[str, Loads]
    room_peak_cool_sensible: dict[str, float]  # each room at its own peak fenestration hour
    surfaces: list[SurfaceDetail]
    infiltration: airflow.InfiltrationResult
    heating_design_temps: dict[str, float]  # by buffer space id
    cooling_design_temps: dict[str, float]
    room_wall_area_ratio: dict[str, float]  # share of whole-house infiltration
    htd_f: float
    ctd_f: float


@dataclass
class _Site:
    htd: float
    ctd: float
    dr: int
    acf: float
    p_psi: float
    indoor_enthalpy: float
    indoor_air_density: float
    outside_air_density: float


def _site(bldg: Building) -> _Site:
    """Source: process_site_calcs_and_design_temps."""
    c = bldg.conditions
    p_psi = psychro.standard_pressure_psi(c.elevation_ft)
    w_in = psychro.humidity_ratio_from_rh(c.cooling_setpoint_f, c.humidity_setpoint_frac, p_psi)
    return _Site(
        htd=max(c.heating_setpoint_f - c.heating_design_temp_f, 0.0),
        ctd=max(c.cooling_design_temp_f - c.cooling_setpoint_f, 0.0),
        dr=T.DAILY_RANGE_INDEX[c.daily_temp_range],
        acf=1.0 - T.ALTITUDE_CORRECTION_PER_FT * c.elevation_ft,
        p_psi=p_psi,
        indoor_enthalpy=psychro.enthalpy_btu_per_lb(c.cooling_setpoint_f, w_in),
        indoor_air_density=psychro.air_density_lb_per_ft3(p_psi, (c.cooling_setpoint_f + c.heating_setpoint_f) / 2.0),
        outside_air_density=psychro.air_density_lb_per_ft3(p_psi, c.annual_avg_drybulb_f),
    )


def calculate(bldg: Building) -> Results:
    bldg.validate()
    c = bldg.conditions
    site = _site(bldg)

    heat_temps = {b.id: spaces.heating_design_temp(bldg, b, site.outside_air_density) for b in bldg.buffer_spaces}
    cool_temps = {b.id: spaces.cooling_design_temp(bldg, b, site.outside_air_density) for b in bldg.buffer_spaces}

    rooms = {r.id: Loads() for r in bldg.rooms}
    details: list[SurfaceDetail] = []
    exposed_wall_area = {r.id: 0.0 for r in bldg.rooms}
    hourly_windows = {r.id: [0.0] * fen.HOURS for r in bldg.rooms}
    hourly_skylights = {r.id: [0.0] * fen.HOURS for r in bldg.rooms}

    def zone_of(room_id):
        return bldg.zone(bldg.room(room_id).zone)

    def heat_setpoint(room_id):
        z = zone_of(room_id)
        return c.heating_setpoint_f if z.heating_setpoint_f is None else z.heating_setpoint_f

    def cool_setpoint(room_id):
        z = zone_of(room_id)
        return c.cooling_setpoint_f if z.cooling_setpoint_f is None else z.cooling_setpoint_f

    def htd(room_id):
        return max(heat_setpoint(room_id) - c.heating_design_temp_f, 0.0)

    def ctd(room_id):
        return max(c.cooling_design_temp_f - cool_setpoint(room_id), 0.0)

    def add(kind, sid, room_id, area, heat_htm, cool_htm, heat_attr, cool_attr):
        heat, cool = heat_htm * area, cool_htm * area
        loads = rooms[room_id]
        setattr(loads, heat_attr, getattr(loads, heat_attr) + heat)
        if cool_attr:
            setattr(loads, cool_attr, getattr(loads, cool_attr) + cool)
        details.append(SurfaceDetail(kind, sid, room_id, area, heat_htm, cool_htm, heat, cool))

    def is_boundary(s):  # conditioned room on the inside, anything but a room outside
        return bldg.is_room(s.inside) and not bldg.is_room(s.outside)

    # --- Windows (process_load_windows_skylights) ----------------------------
    for w in bldg.windows:
        wall = bldg.wall_by_id(w.wall)
        if not (is_boundary(wall) and wall.outside == OUTSIDE):
            continue
        room = wall.inside
        u, shgc = fen.storm_adjusted(w.u_factor, w.shgc, w.storm)
        isc = fen.interior_shading_coefficient(w)
        esc, screen_sc = fen.exterior_shading(w)
        kw = dict(latitude=c.latitude_deg, azimuth_deg=w.azimuth_deg, u_factor=u, shgc=shgc, isc=isc, esc=esc,
                  screen_sc=screen_sc, ctd_f=ctd(room), daily_range_index=site.dr,
                  overhang_depth_ft=w.overhang_depth_ft, overhang_to_top_ft=w.overhang_to_window_top_ft,
                  overhang_to_bottom_ft=w.overhang_to_window_bottom_ft)
        add("windows", w.id, room, w.area_ft2, u * htd(room), fen.window_cooling_htm(**kw),
            "heat_windows", "cool_windows")
        for hr in range(fen.HOURS):
            load = fen.window_cooling_htm(hr=hr, **kw) * w.area_ft2
            rooms[room].hourly_fenestration[hr] += load
            hourly_windows[room][hr] += load

    # --- Skylights -----------------------------------------------------------
    for s in bldg.skylights:
        roof = bldg.roof_by_id(s.roof)
        ceiling = next((f for f in bldg.floors if f.id == s.ceiling), None) if s.ceiling else None
        if ceiling is not None and is_boundary(ceiling):
            room = ceiling.inside
        elif is_boundary(roof):
            room = roof.inside
        else:
            continue
        u_eff = fen.skylight_u_effective(s)
        _, shgc = fen.storm_adjusted(s.u_factor, s.shgc, s.storm)
        kw = dict(latitude=c.latitude_deg, azimuth_deg=s.azimuth_deg, pitch=roof.pitch, u_effective=u_eff,
                  shgc=shgc, isc=s.interior_shading_coefficient, ctd_f=ctd(room), daily_range_index=site.dr)
        add("skylights", s.id, room, s.area_ft2, u_eff * htd(room), fen.skylight_cooling_htm(**kw),
            "heat_skylights", "cool_skylights")
        for hr in range(fen.HOURS):
            load = fen.skylight_cooling_htm(hr=hr, **kw) * s.area_ft2
            rooms[room].hourly_fenestration[hr] += load
            hourly_skylights[room][hr] += load

    # --- Doors (process_load_doors) ------------------------------------------
    for d in bldg.doors:
        wall = bldg.wall_by_id(d.wall)
        if not is_boundary(wall):
            continue
        room = wall.inside
        u = 1.0 / d.r_value
        if wall.outside == OUTSIDE:
            heat_td, cool_td = htd(room), envelope.door_cltd(ctd(room), site.dr)
        else:  # door to a buffer space
            heat_td = heat_setpoint(room) - heat_temps[wall.outside]
            cool_td = cool_temps[wall.outside] - cool_setpoint(room)
        add("doors", d.id, room, d.area_ft2, u * heat_td, u * cool_td, "heat_doors", "cool_doors")

    # --- Walls, rim joists, foundation walls (process_load_walls) ------------
    for wall in [*bldg.walls, *bldg.foundation_walls]:
        if not is_boundary(wall):
            continue
        room = wall.inside
        is_fnd = isinstance(wall, FoundationWall)
        net_area = bldg.net_area_ft2(wall)
        if is_fnd and wall.depth_below_grade_ft == wall.height_ft:
            gross = None  # entirely below grade: no above-grade load
        elif is_fnd and wall.depth_below_grade_ft >= 2:
            gross = wall.above_grade_area_ft2
            net_area = net_area - wall.below_grade_area_ft2
        else:  # walls, and foundation walls under 2 ft deep (treated as all above grade)
            gross = wall.area_ft2
        if gross is not None:
            u = foundation_wall_above_grade_u(wall, True) if is_fnd else wall.u
            if wall.outside == OUTSIDE or (is_fnd and wall.outside == GROUND):
                exposed_wall_area[room] += gross
                if is_fnd:
                    group = envelope.foundation_wall_group(wall.wall_type, wall.thickness_in, u)
                    color = "medium"
                else:
                    group = envelope.wall_group(wall.wall_type, wall.siding, u)
                    color = envelope.wall_color(wall.solar_absorptance)
                cool_td = envelope.wall_cltd(group, color, ctd(room), c.cooling_design_temp_f, site.dr)
                heat_td = htd(room)
            else:  # partition wall to a buffer space
                cool_td = cool_temps[wall.outside] - cool_setpoint(room)
                heat_td = heat_setpoint(room) - heat_temps[wall.outside]
            add("walls", wall.id, room, net_area, u * heat_td, u * cool_td, "heat_walls", "cool_walls")
        if is_fnd and wall.depth_below_grade_ft >= 2:
            u_bg = foundation_wall_below_grade_u(wall, True, c.ground_conductivity_btu_h_ft_f)
            add("walls_below_grade", wall.id, room, wall.below_grade_area_ft2, u_bg * htd(room), 0.0,
                "heat_walls", None)

    # --- Roofs over conditioned rooms (process_load_roofs) -------------------
    for roof in bldg.roofs:
        if not bldg.is_room(roof.inside):
            continue
        room = roof.inside
        cltd = envelope.roof_cltd(roof.r, roof.roof_type, roof.roof_color, c.cooling_design_temp_f, site.dr)
        add("roofs", roof.id, room, bldg.net_area_ft2(roof), roof.u * htd(room), roof.u * cltd,
            "heat_roofs", "cool_roofs")

    # --- Ceilings and floors (process_load_ceilings, process_load_floors) ----
    for f in bldg.floors:
        if not is_boundary(f):
            continue
        room = f.inside
        radiant = zone_of(room).has_radiant_floor and not f.is_ceiling
        radiant_add = T.RADIANT_FLOOR_HTD_ADDER_F if radiant else 0.0
        other = bldg.buffer(f.outside)
        if f.outside == OUTSIDE:
            cool_td = envelope.exposed_horizontal_ctd(ctd(room), site.dr)
            heat_td = htd(room) + radiant_add
        elif (not f.is_ceiling and other is not None
              and other.kind in ("crawlspace_vented", "crawlspace_unvented", "basement_unconditioned")):
            u_wall = _enclosing_wall_u(bldg, other.id)
            vented = other.kind == "crawlspace_vented"
            cool_td = envelope.floor_over_enclosed_space_td(ctd(room), f.u, u_wall, vented)
            heat_td = envelope.floor_over_enclosed_space_td(htd(room) + radiant_add, f.u, u_wall, vented)
        else:
            cool_td = cool_temps[f.outside] - cool_setpoint(room)
            heat_td = heat_setpoint(room) - heat_temps[f.outside] + radiant_add
        kind = "ceilings" if f.is_ceiling else "floors"
        add(kind, f.id, room, bldg.net_area_ft2(f), f.u * heat_td, f.u * cool_td, f"heat_{kind}", f"cool_{kind}")

    # --- Slabs (process_load_slabs) ------------------------------------------
    for slab in bldg.slabs:
        if not bldg.is_room(slab.inside):
            continue
        room = slab.inside
        td = htd(room) + (T.RADIANT_FLOOR_HTD_ADDER_F if zone_of(room).has_radiant_floor else 0.0)
        basement = _basement_floor_geometry(bldg) if bldg.room(room).below_grade else None
        if basement is None:  # slab near grade: loss per foot of exposed edge
            f_value = slab_f_value(slab, c.ground_conductivity_btu_h_ft_f)
            add("slabs", slab.id, room, slab.exposed_perimeter_ft, f_value * td, 0.0, "heat_slabs", None)
        else:  # basement floor 2 ft or more below grade: loss per ft2
            depth, shortest_width = basement
            insulated = ((slab.under_slab_insulation_width_ft > 0 and slab.under_slab_insulation_r > 0)
                         or (slab.perimeter_insulation_depth_ft > 0 and slab.perimeter_insulation_r > 0)
                         or (slab.under_slab_insulation_spans_slab and slab.under_slab_insulation_r > 0)
                         or (slab.exterior_horizontal_insulation_width_ft > 0
                             and slab.exterior_horizontal_insulation_r > 0))
            u = basement_slab_u(insulated, depth, shortest_width, c.ground_conductivity_btu_h_ft_f)
            add("slabs", slab.id, room, slab.area_ft2, u * td, 0.0, "heat_slabs", None)

    # --- Zone-to-zone transfer (RightTon extension, not in the reference) ----
    for s in [*bldg.walls, *bldg.floors]:
        if not (bldg.is_room(s.inside) and bldg.is_room(s.outside)):
            continue
        a, b = s.inside, s.outside
        area = bldg.net_area_ft2(s)
        for this, that in ((a, b), (b, a)):
            heat_htm = s.u * (heat_setpoint(this) - heat_setpoint(that))
            cool_htm = s.u * (cool_setpoint(that) - cool_setpoint(this))
            if heat_htm or cool_htm:
                add("interzone", s.id, this, area, heat_htm, cool_htm, "heat_interzone", "cool_interzone")

    # --- Infiltration and ventilation (process_load_infiltration_ventilation) -
    infil = airflow.infiltration_airflows(bldg, site.htd, site.ctd)
    vent = airflow.ventilation_data(bldg.ventilation_fans)
    infil.net_heating_cfm = airflow.net_infiltration_cfm(infil.heating_cfm, vent.q_imbalance_cfm)
    infil.net_cooling_cfm = airflow.net_infiltration_cfm(infil.cooling_cfm, vent.q_imbalance_cfm)
    grains = c.humidity_difference_grains
    sens_k, lat_k = T.SENSIBLE_AIR_FACTOR * site.acf, T.LATENT_AIR_FACTOR * site.acf
    infil_heat = sens_k * infil.net_heating_cfm * site.htd
    infil_cool_sens = sens_k * infil.net_cooling_cfm * site.ctd
    infil_cool_lat = lat_k * infil.net_cooling_cfm * grains
    q_oa = vent.q_outdoor_air_cfm
    vent_heat = sens_k * q_oa * (1.0 - vent.heating_sensible_eff) * site.htd
    vent_cool_sens = sens_k * q_oa * (1.0 - vent.cooling_sensible_eff) * site.ctd
    vent_cool_lat = lat_k * q_oa * (1.0 - vent.cooling_latent_eff) * grains

    total_exposed = sum(exposed_wall_area.values())
    cfa = bldg.cfa_ft2
    wall_ratio = {}
    for r in bldg.rooms:
        loads = rooms[r.id]
        ratio = exposed_wall_area[r.id] / total_exposed if total_exposed else 0.0
        wall_ratio[r.id] = ratio
        loads.heat_infiltration = infil_heat * ratio  # by exposed wall area
        loads.cool_infiltration_sens = infil_cool_sens * ratio
        loads.cool_infiltration_lat = infil_cool_lat * ratio
        area_share = r.floor_area_ft2 / cfa  # ventilation by floor area
        loads.heat_ventilation = vent_heat * area_share
        loads.cool_ventilation_sens = vent_cool_sens * area_share
        loads.cool_ventilation_lat = vent_cool_lat * area_share
        # --- Internal gains (process_load_internal_gains) ---------------------
        loads.cool_internal_sens = r.internal_sensible_btuh + T.OCCUPANT_SENSIBLE_BTUH * r.occupants
        loads.cool_internal_lat = r.internal_latent_btuh + T.OCCUPANT_LATENT_BTUH * r.occupants

    # --- Totals, then zone-level items ----------------------------------------
    room_peak = {}
    for r in bldg.rooms:
        loads = rooms[r.id]
        loads.update_totals()
        # The room on its own: peak-hour fenestration instead of the daily average
        room_peak[r.id] = (loads.cool_sensible - loads.cool_windows - loads.cool_skylights
                           + max(hourly_windows[r.id]) + max(hourly_skylights[r.id]))

    zones = {}
    for z in bldg.zones:
        zl = Loads()
        zone_rooms = bldg.zone_rooms(z.id)
        for r in zone_rooms:
            zl.add(rooms[r.id])
        zl.cool_aed_excursion = fen.aed_excursion(zl.hourly_fenestration)
        zl.update_totals()
        for system in (s for s in bldg.distribution_systems if s.zone == z.id):
            _apply_distribution(bldg, system, site, zl, [rooms[r.id] for r in zone_rooms],
                                heat_temps, cool_temps,
                                c.heating_setpoint_f if z.heating_setpoint_f is None else z.heating_setpoint_f,
                                c.cooling_setpoint_f if z.cooling_setpoint_f is None else z.cooling_setpoint_f)
        zl.update_totals()
        zones[z.id] = zl

    for r in bldg.rooms:
        ducts_sens_before = rooms[r.id].cool_sensible
        rooms[r.id].update_totals()
        room_peak[r.id] += rooms[r.id].cool_sensible - ducts_sens_before

    building = Loads()
    for zl in zones.values():
        building.add(zl)
    building.update_totals()

    return Results(building=building, zones=zones, rooms=rooms, room_peak_cool_sensible=room_peak,
                   surfaces=details, infiltration=infil, heating_design_temps=heat_temps,
                   cooling_design_temps=cool_temps, room_wall_area_ratio=wall_ratio,
                   htd_f=site.htd, ctd_f=site.ctd)


def _enclosing_wall_u(bldg: Building, space_id: str) -> float:
    """Area-weighted U-factor of the walls around a crawlspace or unconditioned
    basement. Source: process_load_floors (sum_ua_wall / sum_a_wall)."""
    ua = area = 0.0
    for fw in bldg.foundation_walls:
        if fw.inside == space_id and fw.outside == GROUND:
            fw_ua, fw_area = spaces._foundation_wall_ua(fw, bldg, bldg.conditions.ground_conductivity_btu_h_ft_f)
            ua += fw_ua
            area += fw_area
    for w in bldg.walls:
        if w.inside == space_id and w.outside == OUTSIDE:
            net = bldg.net_area_ft2(w)
            ua += w.u * net
            area += net
    if area <= 0:
        raise ValueError(f"Space '{space_id}' has no exterior walls.")
    return ua / area


def _basement_floor_geometry(bldg: Building) -> Optional[tuple[float, float]]:
    """(average depth below grade, width of shortest side) of the conditioned
    basement, or None if it is less than 2 ft deep on average.

    Source: process_load_slabs.
    """
    walls = [fw for fw in bldg.foundation_walls if bldg.is_room(fw.inside) and bldg.room(fw.inside).below_grade]
    if not walls:
        return None

    def length(fw):
        return fw.length_ft if fw.length_ft is not None else fw.area_ft2 / fw.height_ft

    perimeter = sum(fw.area_ft2 / fw.height_ft for fw in walls)
    depth = sum(fw.depth_below_grade_ft * (fw.area_ft2 / fw.height_ft) for fw in walls) / perimeter
    if depth < 2:
        return None
    by_azimuth: dict[float, float] = {}
    for fw in walls:
        # A wall with no orientation is assumed to be spread evenly over four sides
        azimuths = [fw.azimuth_deg] if fw.azimuth_deg is not None else [0.0, 90.0, 180.0, 270.0]
        for az in azimuths:
            by_azimuth[az] = by_azimuth.get(az, 0.0) + length(fw) / len(azimuths)
    return depth, min(by_azimuth.values())


def _apply_distribution(bldg, system, site, zone_loads: Loads, room_loads: list[Loads], heat_temps, cool_temps,
                        heat_setpoint_f, cool_setpoint_f) -> None:
    """Duct, blower-heat and piping loads for one zone.

    Source: apply_hvac_duct_loads, apply_hvac_blower_heat_load, apply_hvac_piping_load.
    The system is assumed to serve the whole zone load.
    """
    c = bldg.conditions
    heat_design = dict(heat_temps)
    heat_design[OUTSIDE] = c.heating_design_temp_f
    cool_design = dict(cool_temps)
    cool_design[OUTSIDE] = c.cooling_design_temp_f

    duct_heat = duct_cool_sens = duct_cool_lat = 0.0
    if system.ducts and system.has_heating and zone_loads.heat_total > 0:
        duct_heat = ducts.heating_duct_load(bldg=bldg, system=system, load_btuh=zone_loads.heat_total,
                                            design_temps=heat_design, setpoint_f=heat_setpoint_f,
                                            air_density=site.indoor_air_density)
    if system.ducts and system.has_cooling and zone_loads.cool_sensible > 0:
        lat = ducts.leaving_air_temp_f(zone_loads.cool_sensible, zone_loads.cool_total)
        duct_cool_sens, duct_cool_lat = ducts.cooling_duct_load(
            bldg=bldg, system=system, load_sens_btuh=zone_loads.cool_sensible, load_lat_btuh=zone_loads.cool_latent,
            design_temps=cool_design, setpoint_f=cool_setpoint_f, air_density=site.indoor_air_density,
            leaving_air_temp=lat, cooling_humidity_ratio=c.cooling_humidity_ratio,
            indoor_enthalpy=site.indoor_enthalpy, altitude_factor=site.acf,
            design_grains=c.humidity_difference_grains)

    # Share duct loads among rooms in proportion to each room's load
    zone_heat = sum(r.heat_total for r in room_loads)
    zone_cool_sens = sum(r.cool_sensible for r in room_loads)
    for r in room_loads:
        if zone_heat:
            r.heat_ducts += duct_heat * r.heat_total / zone_heat
        if zone_cool_sens:
            share = r.cool_sensible / zone_cool_sens
            r.cool_ducts_sens += duct_cool_sens * share
            r.cool_ducts_lat += duct_cool_lat * share  # RightTon extension (reference: zone only)
    zone_loads.heat_ducts += duct_heat
    zone_loads.cool_ducts_sens += duct_cool_sens
    zone_loads.cool_ducts_lat += duct_cool_lat
    zone_loads.cool_blower_heat += system.blower_heat_btuh
    zone_loads.heat_piping += system.piping_btuh
