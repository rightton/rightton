"""Layer-by-layer assembly R-values (parallel-path method).

This module is RightTon's own (it is not ported): the reference engine takes a
finished assembly R-value as input, while RightTon lets the user build the
assembly from layers so that old-house constructions (plaster on lath, board
sheathing, empty balloon-frame cavities) can be described as they are.

Method: the isothermal-planes-free "parallel path" method described in the
ASHRAE Handbook of Fundamentals (chapter on heat, air and moisture control in
building assemblies): heat flows through the framing path and the cavity path
side by side, each path being its layers in series including air films, and the
two path U-factors are area-weighted by the framing fraction.

Air film R-values (hr-ft2-F/Btu) are the ones the reference engine uses, which it
cites as ASHRAE Handbook of Fundamentals 2005, chapter 25, Table 1
(OS-HPXML materials.rb, Material.AirFilm*).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# origin: OS-HPXML materials.rb -> ASHRAE HoF 2005 F25.2 Table 1
FILM_INDOOR_WALL = 0.68  # vertical surface, still air
FILM_INDOOR_FLOOR_DOWN = 0.92  # horizontal surface, heat flow down
FILM_INDOOR_HORIZ_UP = 0.61  # horizontal surface, heat flow up
FILM_INDOOR_HORIZ_AVERAGE = (FILM_INDOOR_FLOOR_DOWN + FILM_INDOOR_HORIZ_UP) / 2.0
FILM_OUTDOOR_WINTER = 0.17  # 15 mph wind
FILM_OUTDOOR_SUMMER = 0.25  # 7.5 mph wind
FILM_OUTDOOR = (FILM_OUTDOOR_WINTER + FILM_OUTDOOR_SUMMER) / 2.0  # year-round value used by the reference

# Interior film by surface position; the film on the far side is FILM_OUTDOOR
# when exposed to wind, otherwise the same still-air film as the near side.
_INDOOR_FILM = {
    "wall": FILM_INDOOR_WALL,
    "ceiling": FILM_INDOOR_HORIZ_AVERAGE,
    "floor": FILM_INDOOR_FLOOR_DOWN,
    "roof": FILM_INDOOR_HORIZ_AVERAGE,  # flat roof; sloped roofs use roof_interior_film_r()
}


def roof_interior_film_r(pitch_rise_per_12: float) -> float:
    """Interior air film R-value (hr-ft2-F/Btu) under a roof of the given pitch.

    Source: OpenStudio-HPXML materials.rb, Material.AirFilmIndoorRoof (BSD-style
    license, see core/NOTICE-OpenStudio-HPXML.md): correlations NREL fitted to the
    still-air film values of ASHRAE Handbook of Fundamentals 2005, chapter 25,
    table 1, which lists 0, 45 and 90 degrees. The average of heat flow up and
    heat flow down is used, since the roof can be hotter or colder than the room.
    At 0 degrees this is (0.61 + 0.92) / 2 = 0.765, the flat-ceiling value.
    """
    angle_deg = math.degrees(math.atan(pitch_rise_per_12 / 12.0))
    r_up = 0.002 * math.exp(0.0398 * angle_deg) + 0.608  # 0.62 at 45 degrees
    r_down = 0.32 * math.exp(-0.0154 * angle_deg) + 0.6  # 0.76 at 45 degrees
    return (r_up + r_down) / 2.0


@dataclass
class Layer:
    """One layer of an assembly, listed from inside to outside.

    Give the thermal resistance either as ``r_per_inch`` (with ``thickness_in``)
    or as a fixed ``r_value`` (e.g. an air space or a rated product).
    A framed layer also has ``framing_r_per_inch``: the material that replaces
    the cavity fill over the framing fraction of the area.
    """

    name: str
    thickness_in: float = 0.0
    r_per_inch: Optional[float] = None
    r_value: Optional[float] = None
    framing_r_per_inch: Optional[float] = None
    source: str = ""  # where the R-value came from (shown in reports)

    @property
    def cavity_r(self) -> float:
        if self.r_value is not None:
            return self.r_value
        if self.r_per_inch is None:
            raise ValueError(f"Layer '{self.name}' needs r_per_inch or r_value.")
        return self.r_per_inch * self.thickness_in

    @property
    def framing_r(self) -> float:
        if self.framing_r_per_inch is None:
            return self.cavity_r
        return self.framing_r_per_inch * self.thickness_in


@dataclass
class Assembly:
    name: str
    layers: list[Layer] = field(default_factory=list)
    position: str = "wall"  # wall, ceiling, floor, roof
    framing_fraction: float = 0.0  # share of area that is framing (0..1)
    exposed_to_wind: bool = True  # False when the far side is an attic, crawlspace, etc.
    roof_pitch_rise_per_12: float = 0.0  # roofs only: sets the interior air film

    @property
    def film_inside_r(self) -> float:
        if self.position == "roof":
            return roof_interior_film_r(self.roof_pitch_rise_per_12)
        return _INDOOR_FILM[self.position]

    @property
    def film_outside_r(self) -> float:
        return FILM_OUTDOOR if self.exposed_to_wind else self.film_inside_r

    def path_r_values(self) -> tuple[float, float]:
        """(cavity path R, framing path R), each including both air films."""
        films = self.film_inside_r + self.film_outside_r
        r_cavity = films + sum(layer.cavity_r for layer in self.layers)
        r_framing = films + sum(layer.framing_r for layer in self.layers)
        return r_cavity, r_framing

    def u_factor(self) -> float:
        """Area-weighted U-factor (Btu/h-ft2-F): U = ff/R_framing + (1-ff)/R_cavity."""
        r_cavity, r_framing = self.path_r_values()
        ff = self.framing_fraction
        if not 0.0 <= ff < 1.0:
            raise ValueError("framing_fraction must be in [0, 1).")
        return ff / r_framing + (1.0 - ff) / r_cavity

    def r_value(self) -> float:
        """Effective assembly R-value (hr-ft2-F/Btu), air films included."""
        return 1.0 / self.u_factor()


# Leftover depth in a split cavity is modeled as a closed air space of this R-value.
# origin: OS-HPXML materials.rb Material.AirCavityClosed (R-1.0 for any enclosed gap), the same
# value as the air_space_closed material. [CONFIRM] The real resistance of a gap beside insulation
# depends on its width, the surface emissivities and the direction of heat flow, and a batt
# usually lofts into part of the gap; R-1.0 is a simple middle value.
LEFTOVER_AIR_SPACE_R = 1.0


def split_cavity(depth_in: float, fills: list[Layer], framing_r_per_inch: float,
                 tolerance_in: float = 0.01) -> list[Layer]:
    """Layers for one framed cavity holding several fills (e.g. foam then batt).

    Each fill becomes its own framed layer: the cavity path runs through every fill
    in series (sum of fill R-values), and the framing path runs through the member
    for the full cavity depth (framing R per inch * depth), because the stacked
    layers share one framing member. Depth the fills leave unused becomes a closed
    air space (``LEFTOVER_AIR_SPACE_R``). Fills thicker than the cavity raise ValueError.
    """
    used_in = sum(f.thickness_in for f in fills)
    if used_in > depth_in + tolerance_in:
        raise ValueError(f"The fills are {used_in:g} in thick but the cavity is only {depth_in:g} in deep.")
    layers = [Layer(f.name, thickness_in=f.thickness_in, r_per_inch=f.r_per_inch, r_value=f.r_value,
                    framing_r_per_inch=framing_r_per_inch, source=f.source) for f in fills]
    leftover_in = depth_in - used_in
    if leftover_in > tolerance_in:
        layers.append(Layer("air space (rest of cavity)", thickness_in=leftover_in, r_value=LEFTOVER_AIR_SPACE_R,
                            framing_r_per_inch=framing_r_per_inch, source="OS-HPXML Material.AirCavityClosed"))
    return layers
