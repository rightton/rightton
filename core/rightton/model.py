"""Input data model for the RightTon calculation core.

Everything is a plain dataclass in IP units; unit suffixes are in the field
names (``_ft2``, ``_f``, ``_btuh``, ``_cfm``). R-values are hr-ft2-F/Btu and
include air films unless stated otherwise.

Adjacency. Every surface names what is on each side of it:

* ``inside``  - the id of a conditioned ``Room`` or of a ``BufferSpace``;
* ``outside`` - ``OUTSIDE``, ``GROUND``, ``ADIABATIC`` (no heat flow), the id of
  a ``BufferSpace``, or the id of another ``Room`` (a partition between rooms,
  used for zone-to-zone transfer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .assemblies import Assembly

OUTSIDE = "outside"
GROUND = "ground"
ADIABATIC = "adiabatic"  # e.g. a party wall to a neighbor kept at the same temperature

BUFFER_KINDS = (
    "attic_vented",
    "attic_unvented",
    "crawlspace_vented",
    "crawlspace_unvented",
    "basement_unconditioned",
    "garage",
    "weighted",  # temperature is a fixed blend of indoor, outdoor and ground temperatures
)


@dataclass
class DesignConditions:
    """Outdoor and indoor design conditions for one site."""

    heating_design_temp_f: float
    cooling_design_temp_f: float
    daily_temp_range: str  # "low" (<16 F), "medium", or "high" (>25 F)
    humidity_difference_grains: float  # outdoor minus indoor humidity ratio, grains/lb
    latitude_deg: float
    elevation_ft: float = 0.0
    heating_setpoint_f: float = 70.0
    cooling_setpoint_f: float = 75.0
    humidity_setpoint_frac: float = 0.5
    ground_conductivity_btu_h_ft_f: float = 1.0
    # Weather-derived values used for buffer spaces and duct loads:
    cooling_humidity_ratio: float = 0.0  # lb/lb, outdoor air at cooling design
    annual_avg_drybulb_f: float = 55.0
    ground_temp_winter_f: float = 45.0  # coldest monthly shallow ground temperature
    ground_temp_summer_f: float = 65.0  # warmest monthly shallow ground temperature
    wsf: float = 0.5  # ASHRAE 62.2 weather and shielding factor


@dataclass
class Zone:
    id: str
    # Optional per-zone setpoints (default: the building design conditions).
    heating_setpoint_f: Optional[float] = None
    cooling_setpoint_f: Optional[float] = None
    has_radiant_floor: bool = False


@dataclass
class Room:
    id: str
    zone: str
    floor_area_ft2: float
    ceiling_height_ft: float = 8.0
    occupants: float = 0.0
    internal_sensible_btuh: float = 0.0  # appliances, lighting, equipment
    internal_latent_btuh: float = 0.0
    below_grade: bool = False  # room is in a conditioned basement
    # Heat from equipment reported on its own line (e.g. a dehumidifier's heat output)
    equipment_sensible_btuh: float = 0.0
    equipment_latent_btuh: float = 0.0
    # Share of whole-house infiltration assigned to this room. If any room has a
    # share, shares are used (normalized) instead of exposed wall area.
    infiltration_share: Optional[float] = None


@dataclass
class BufferSpace:
    """An unconditioned space next to conditioned rooms (attic, crawlspace, ...)."""

    id: str
    kind: str  # one of BUFFER_KINDS
    volume_ft3: float = 0.0
    vent_sla: Optional[float] = None  # vent area / floor area, vented spaces
    vent_ach: Optional[float] = None  # alternative to vent_sla (vented attics)
    # kind == "weighted" only (e.g. ducts in an exterior wall or under a slab, or a
    # neighboring heated space): T = indoor*w_in + outdoor*w_out + ground*w_ground,
    # not below min_temp_f. duct_regain is the share of duct loss recovered.
    indoor_weight: float = 0.0
    outdoor_weight: float = 1.0
    ground_weight: float = 0.0
    min_temp_f: Optional[float] = None
    duct_regain: float = 0.0
    # Optional user overrides of the calculated design temperatures:
    heating_design_temp_f: Optional[float] = None
    cooling_design_temp_f: Optional[float] = None

    def __post_init__(self):
        if self.kind not in BUFFER_KINDS:
            raise ValueError(f"Unknown buffer space kind: {self.kind}")


@dataclass
class _Surface:
    id: str
    inside: str
    outside: str = OUTSIDE
    area_ft2: float = 0.0  # gross area
    r_value: Optional[float] = None  # assembly R-value incl. films
    assembly: Optional[Assembly] = None  # alternative to r_value

    @property
    def r(self) -> float:
        if self.r_value is not None:
            return self.r_value
        if self.assembly is not None:
            return self.assembly.r_value()
        raise ValueError(f"Surface '{self.id}' needs r_value or assembly.")

    @property
    def u(self) -> float:
        return 1.0 / self.r


@dataclass
class Wall(_Surface):
    """Above-grade wall or rim joist."""

    wall_type: str = "wood_stud"  # wood_stud, steel_stud, double_wood_stud, sip, cmu,
    # brick, adobe, concrete, stone, log, icf, straw_bale
    siding: str = "wood"  # "brick"/"stone" matter; anything else is light cladding
    solar_absorptance: float = 0.7
    is_rim_joist: bool = False


@dataclass
class FoundationWall(_Surface):
    """Basement or crawlspace wall, partly or wholly below grade."""

    outside: str = GROUND
    height_ft: float = 8.0
    depth_below_grade_ft: float = 0.0
    thickness_in: float = 8.0
    wall_type: str = "solid_concrete"  # solid_concrete, double_brick, wood,
    # concrete_block, concrete_block_solid_core, concrete_block_perlite_core,
    # concrete_block_foam_core, concrete_block_vermiculite_core
    insulation_interior_r: float = 0.0
    insulation_interior_top_ft: float = 0.0  # distance from top of wall
    insulation_interior_bottom_ft: float = 0.0
    insulation_exterior_r: float = 0.0
    insulation_exterior_top_ft: float = 0.0
    insulation_exterior_bottom_ft: float = 0.0
    azimuth_deg: Optional[float] = None
    length_ft: Optional[float] = None

    @property
    def above_grade_area_ft2(self) -> float:
        return self.area_ft2 * (self.height_ft - self.depth_below_grade_ft) / self.height_ft

    @property
    def below_grade_area_ft2(self) -> float:
        return self.area_ft2 - self.above_grade_area_ft2


@dataclass
class Roof(_Surface):
    roof_type: str = "asphalt_shingles"  # see tables.ROOF_MATERIAL_CLASS
    roof_color: str = "medium"  # see tables.ROOF_COLOR_CLASS
    radiant_barrier: bool = False
    pitch: float = 6.0  # rise per 12 run


@dataclass
class Floor(_Surface):
    """Horizontal partition: a ceiling (``is_ceiling=True``) or a floor, seen
    from the conditioned room on its ``inside``."""

    is_ceiling: bool = False


def Ceiling(*args, **kwargs) -> Floor:
    kwargs["is_ceiling"] = True
    return Floor(*args, **kwargs)


@dataclass
class Slab:
    id: str
    inside: str
    area_ft2: float
    exposed_perimeter_ft: float
    thickness_in: float = 4.0  # 0 means a dirt floor
    perimeter_insulation_r: float = 0.0
    perimeter_insulation_depth_ft: float = 0.0
    under_slab_insulation_r: float = 0.0
    under_slab_insulation_width_ft: float = 0.0
    under_slab_insulation_spans_slab: bool = False
    exterior_horizontal_insulation_r: float = 0.0
    exterior_horizontal_insulation_width_ft: float = 0.0
    exterior_horizontal_insulation_depth_below_grade_ft: float = 0.0
    outside: str = GROUND


@dataclass
class Window:
    id: str
    wall: str  # id of the Wall it is in
    area_ft2: float
    azimuth_deg: float  # compass: 0 = north, 90 = east, 180 = south
    u_factor: float
    shgc: float
    storm: Optional[str] = None  # None, "clear", or "low_e"
    # Interior shading: either a named type (looked up) or a direct coefficient.
    interior_shading_type: Optional[str] = None  # e.g. "light_curtains", "none"
    interior_shading_coverage: float = 0.5  # fraction of window covered in summer
    blinds_position: str = "closed"  # "closed", "half_open", "open"
    interior_shading_coefficient: float = 1.0  # used when no type is given
    glass_layers: Optional[int] = None  # 1, 2, 3 (else estimated from U and SHGC)
    glass_type: Optional[str] = None  # clear, tinted, reflective, low_e,
    # low_e_low_solar, low_e_high_solar
    exterior_shading_type: Optional[str] = None  # "solar_screens" or "solar_film"
    exterior_shading_coefficient: Optional[float] = None
    insect_screen: Optional[str] = None  # "interior" or "exterior"
    insect_screen_coverage: float = 1.0
    overhang_depth_ft: float = 0.0
    overhang_to_window_top_ft: float = 0.0
    overhang_to_window_bottom_ft: float = 0.0


@dataclass
class Skylight:
    id: str
    roof: str  # id of the Roof it is in
    area_ft2: float
    azimuth_deg: float
    u_factor: float
    shgc: float
    ceiling: Optional[str] = None  # id of the ceiling (Floor) it lights through a shaft, if the roof is over an attic
    storm: Optional[str] = None
    interior_shading_coefficient: float = 1.0
    curb_area_ft2: Optional[float] = None
    curb_r_value: Optional[float] = None
    shaft_area_ft2: Optional[float] = None
    shaft_r_value: Optional[float] = None


@dataclass
class Door:
    id: str
    wall: str
    area_ft2: float
    r_value: float


@dataclass
class Infiltration:
    """Whole-house air leakage. Give exactly one leakage quantity."""

    method: str = "blower_door"  # or "default_table"
    ach50: Optional[float] = None  # air changes per hour at house_pressure_pa
    cfm50: Optional[float] = None  # cfm at house_pressure_pa
    house_pressure_pa: float = 50.0
    natural_ach: Optional[float] = None
    ela_in2: Optional[float] = None  # effective leakage area at 4 Pa
    sla: Optional[float] = None  # specific leakage area (ELA / floor area)
    leakiness: Optional[str] = None  # default_table: very_tight ... very_leaky
    volume_ft3: Optional[float] = None  # default: sum of room volumes
    height_ft: Optional[float] = None  # infiltration height, for natural ACH
    shielding_class: int = 4  # 1 (no shielding) .. 5 (very heavy)
    exterior_fraction: float = 1.0  # share of envelope exposed to outside (attached units)
    unit_height_above_grade_ft: float = 0.0  # attached units and apartments only
    site_shielding: str = "normal"  # "normal", "exposed", "well_shielded" (attached units only)
    has_fireplace: bool = False


@dataclass
class VentilationFan:
    """Whole-house mechanical ventilation (average flow while the house is occupied)."""

    fan_type: str  # supply, exhaust, balanced, erv, hrv, cfis
    flow_cfm: float
    sensible_effectiveness: float = 0.0  # apparent, ERV/HRV only
    latent_effectiveness: float = 0.0  # ERV only


@dataclass
class Duct:
    duct_type: str  # "supply" or "return"
    location: str  # room id, buffer space id, or OUTSIDE
    surface_area_ft2: float
    effective_r_value: float
    area_multiplier: float = 1.0


@dataclass
class DistributionSystem:
    """The air (or hydronic) distribution system serving one zone."""

    zone: str
    has_heating: bool = True
    has_cooling: bool = True
    heating_cfm_per_ton: float = 240.0  # furnace default; heat pumps use 360
    cooling_cfm_per_ton: float = 360.0
    ducts: list[Duct] = field(default_factory=list)
    supply_leakage: float = 0.0
    return_leakage: float = 0.0
    leakage_units: str = "cfm25"  # "cfm25", "cfm50" or "fraction" (of system airflow)
    blower_heat_btuh: float = 0.0
    piping_btuh: float = 0.0  # hydronic piping loss


@dataclass
class Building:
    conditions: DesignConditions
    zones: list[Zone]
    rooms: list[Room]
    buffer_spaces: list[BufferSpace] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)
    foundation_walls: list[FoundationWall] = field(default_factory=list)
    roofs: list[Roof] = field(default_factory=list)
    floors: list[Floor] = field(default_factory=list)  # floors and ceilings
    slabs: list[Slab] = field(default_factory=list)
    windows: list[Window] = field(default_factory=list)
    skylights: list[Skylight] = field(default_factory=list)
    doors: list[Door] = field(default_factory=list)
    infiltration: Optional[Infiltration] = None
    ventilation_fans: list[VentilationFan] = field(default_factory=list)
    distribution_systems: list[DistributionSystem] = field(default_factory=list)
    stories_above_grade: float = 1.0
    facility_type: str = "single_family_detached"
    conditioned_floor_area_ft2: Optional[float] = None  # default: sum of rooms
    above_grade_volume_ft3: Optional[float] = None  # default: above-grade room volumes

    # --- lookups -----------------------------------------------------------
    def room(self, rid: str) -> Optional[Room]:
        return next((r for r in self.rooms if r.id == rid), None)

    def buffer(self, bid: str) -> Optional[BufferSpace]:
        return next((b for b in self.buffer_spaces if b.id == bid), None)

    def zone(self, zid: str) -> Zone:
        return next(z for z in self.zones if z.id == zid)

    def is_room(self, ref: str) -> bool:
        return self.room(ref) is not None

    def zone_rooms(self, zid: str) -> list[Room]:
        return [r for r in self.rooms if r.zone == zid]

    @property
    def cfa_ft2(self) -> float:
        if self.conditioned_floor_area_ft2 is not None:
            return self.conditioned_floor_area_ft2
        return sum(r.floor_area_ft2 for r in self.rooms)

    @property
    def opaque_surfaces(self) -> list:
        return [*self.roofs, *self.walls, *self.foundation_walls, *self.floors, *self.slabs]

    def wall_by_id(self, wid: str):
        return next(w for w in [*self.walls, *self.foundation_walls] if w.id == wid)

    def roof_by_id(self, rid: str) -> Roof:
        return next(r for r in self.roofs if r.id == rid)

    def net_area_ft2(self, surface) -> float:
        """Gross area minus the windows/doors/skylights set into the surface.

        Source: HPXML::Wall#net_area etc. in OS-HPXML hpxml.rb.
        """
        area = surface.area_ft2
        if isinstance(surface, (Wall, FoundationWall)):
            area -= sum(w.area_ft2 for w in self.windows if w.wall == surface.id)
            area -= sum(d.area_ft2 for d in self.doors if d.wall == surface.id)
        elif isinstance(surface, Roof):
            area -= sum(s.area_ft2 for s in self.skylights if s.roof == surface.id)
        elif isinstance(surface, Floor):
            area -= sum(s.area_ft2 for s in self.skylights if s.ceiling == surface.id)
        if area < -1e-9:
            raise ValueError(f"Negative net area for surface '{surface.id}'.")
        return area

    def validate(self) -> None:
        ids = [r.id for r in self.rooms] + [b.id for b in self.buffer_spaces]
        if len(ids) != len(set(ids)):
            raise ValueError("Room and buffer space ids must be unique.")
        zone_ids = {z.id for z in self.zones}
        for r in self.rooms:
            if r.zone not in zone_ids:
                raise ValueError(f"Room '{r.id}' is in unknown zone '{r.zone}'.")
        known = set(ids) | {OUTSIDE, GROUND, ADIABATIC}
        for s in self.opaque_surfaces:
            if s.inside not in ids:
                raise ValueError(f"Surface '{s.id}': unknown inside '{s.inside}'.")
            if s.outside not in known:
                raise ValueError(f"Surface '{s.id}': unknown outside '{s.outside}'.")
