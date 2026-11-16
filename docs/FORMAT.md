# RightTon house file format, version 1.0

A RightTon house file describes one house for heating and cooling load calculation.
It is an open format: any tool may write or edit it (a CAD exporter, the RightTon
web app, a script, or a language model given
[FORMAT-GUIDE-FOR-LLMS.md](FORMAT-GUIDE-FOR-LLMS.md) and a description of a house).
The format is a public contract and does not depend on the RightTon app.

- Machine-readable definition: [`schema/rightton-house.schema.json`](../schema/rightton-house.schema.json) (JSON Schema, draft 2020-12).
- This document is the human reference. Its field tables are generated from the schema
  (`python tools/gen_format_docs.py`), and a test fails if the two disagree.
- Examples: [`examples/`](../examples).

## Files and encoding

| | |
| --- | --- |
| Canonical encoding | JSON, UTF-8. The RightTon app always saves JSON. |
| Also accepted | YAML, for writing by hand. Same data model, same schema; converting either way loses nothing except YAML comments. |
| File names | `*.rtn.json`, `*.rtn.yaml` |
| Units | US units only. Every quantity has its unit in its field name. |

## Rules of the data model

1. **Units are in field names.** `area_ft2`, `height_ft`, `thickness_in`, `r_value_hr_ft2_f_btu`,
   `u_factor_btu_hr_ft2_f`, `azimuth_deg`, `airflow_cfm`, `sensible_heat_btu_hr`. Fractions end in
   `_frac` and are written 0 to 1, never as percent. Temperatures are Fahrenheit (`_f`).
2. **Everything has an `id`, and references are by id.** A window names its wall (`surface`), a wall names
   the room it belongs to (`inside`) and its construction (`assembly`). Ids are lowercase letters, digits,
   hyphens and underscores, and are unique across the whole file. `outdoors`, `ground` and `adiabatic`
   are reserved words, not ids.
3. **Assemblies are defined once** in `assemblies` and reused by id.
4. **Numbers can carry their source.** Any numeric input may be a bare number, or
   `{ "value": 14, "source": "blower door test", "confidence": "measured" }`. Confidence is
   `measured`, `estimated` or `default`; a bare number counts as `default`.
5. **Areas drive the calculation.** A surface needs `area_ft2` (gross, including its windows and doors).
   It may also carry an outline polygon (`outline_ft`) for CAD tools; the engine ignores it.
6. **No personal data.** Location is a weather station, never an address. There is no owner field.
7. **Left-out inputs get documented defaults.** See [Defaults](#defaults); every default that was applied is
   listed with the results.

## How a house is put together

```
zones ── rooms ──┐
                 ├── surfaces (inside: a room or space; outside: outdoors / ground / adiabatic / a space / a room)
spaces ──────────┘        │                    └── assembly ──> assemblies
                          └── openings (surface: the wall or roof they are in)
air:  infiltration (whole house), ventilation fans, ducts (per hvac system; each segment has a location)
hvac: systems (one per zone; which rooms have supply registers and returns)
equipment: heat sources reported on their own line (dehumidifier)
scenarios: lists of changes against everything above
```

- A **room** is conditioned, lived-in space. A **zone** is a group of rooms on one thermostat.
- A **space** is anything else that surfaces can border: attic, crawlspace, unconditioned basement, garage,
  open porch, or a `conditioned` space that is inside the insulation but not lived in (a sealed attic).
- A wall between a room and the outdoors has `inside: <room>` and no `outside` (it defaults to `outdoors`).
  A ceiling under an attic has `inside: <room>`, `outside: <attic>`. The attic's own roof has
  `inside: <attic>`. A wall behind an open porch has `outside: <porch>`.
- A surface between two rooms matters only when the rooms are in zones with different setpoints
  (zone-to-zone heat transfer). Interior partitions can be left out.

## Scenarios

A scenario is a short list of changes applied to a copy of the baseline:

| Change | Fields | Effect |
| --- | --- | --- |
| `set` | `path`, `value` | Replace one field (or one whole item). |
| `add` | `section`, `item` | Append an item to a list. |
| `remove` | `path` | Delete an item or a field. |

A path is `section/id/field`, continuing into nested fields: `air/infiltration/air_changes_per_hr_at_50pa`,
`surfaces/north-wall/assembly`, `openings/w1/overhang/depth_ft`. Items without an id (assembly layers, duct
segments) are addressed by position, counting from 0: `assemblies/wall-old/layers/1`.
`includes` lists other scenarios whose changes are applied first, which is how scenarios are stacked.
A scenario may carry `cost_usd`, entered by the user.

## Extensions

Tools keep their own data under `extensions.<tool-name>`. A reader must keep extensions it does not
understand and write them back unchanged.

## Versions

`format_version` is `MAJOR.MINOR.PATCH`. Readers accept any file with the same major version, including
older minor versions. A breaking change raises the major version and ships with a converter.

## Checking a file

```bash
python -m rightton.validate house.rtn.json
```

The validator checks the schema and then the things a schema cannot express: references resolve, ids are
unique, windows fit in their walls, every room belongs to a zone, scenarios apply cleanly. Messages say
where the problem is and how to fix it. `--json` prints the findings as JSON. Third-party tools can
validate with any JSON Schema library; the custom keywords `x-unit`, `x-min` and `x-max` (unit and range
of numeric inputs) and `x-discriminator` are extra information that such libraries ignore.

## Field reference

<!-- BEGIN GENERATED: field-reference -->
| Top-level field | Required | Meaning |
| --- | --- | --- |
| `format_version` | yes | Version of this format the file was written for, as MAJOR.MINOR.PATCH. This schema is 1.0.0. Readers accept any 1.x file. |
| `project` |  | About the project. Never put a street address, an owner's name or other personal details here. |
| `location` |  | Where the house is, as a weather station. There is no address field. |
| `assemblies` |  | Library of constructions (walls, roofs, ceilings, floors), each defined once and used by id from surfaces. |
| `zones` | yes | Zones: groups of rooms served and controlled together (one thermostat). At least one. |
| `rooms` | yes | Conditioned rooms. At least one. |
| `spaces` |  | Spaces that are not lived-in rooms: attics, crawlspaces, unconditioned basements, garages, porches, and conditioned-but-unoccupied spaces such as a sealed attic. |
| `surfaces` |  | Walls, roofs, ceilings, floors and slabs: of rooms, and of unconditioned spaces (an attic's roof, a crawlspace's walls and floor). |
| `openings` |  | Windows, doors and skylights, each set into a surface. |
| `air` |  | Air leakage, mechanical ventilation and ducts. |
| `equipment` |  | Heat-producing equipment reported on its own line in the results, e.g. a dehumidifier. |
| `hvac` |  | Heating and cooling systems. Equipment sizes are not inputs: the calculation says what is needed. |
| `scenarios` |  | What-if variations, each a short list of changes against the baseline house above. |
| `extensions` |  | Data owned by other tools, each under its own key (e.g. extensions.my-cad-tool). Readers must keep extensions they do not understand when re-saving. |

### project

About the project. Never put a street address, an owner's name or other personal details here.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `name` |  | text | Short project name. |
| `description` |  | text | What this file describes. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `bedroom_count` |  | whole number (at least 0) | Number of bedrooms. Only used to default the number of occupants (bedrooms + 1). |
| `created_with` |  | text | Tool that wrote the file. |

### location

Where the house is, as a weather station. There is no address field.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `weather_station_id` |  | text | WMO number of the weather station, as text (e.g. "725650"). Supplies design conditions; see the station list in docs/FORMAT.md. Optional if design_conditions gives everything marked 'needed without a station'. |
| `weather_station_name` |  | text | Station name, for people. |
| `design_conditions` |  | object | Design conditions. Each value given here overrides the weather station's. |

#### location > design_conditions

Design conditions. Each value given here overrides the weather station's.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `heating_outdoor_temp_f` |  | number (F) | Outdoor temperature the heating system must cope with (99 % design drybulb). Needed without a station. |
| `cooling_outdoor_temp_f` |  | number (F) | Outdoor temperature the cooling system must cope with (1 % design drybulb). Needed without a station. |
| `daily_temp_range` |  | one of: `low`, `medium`, `high` | Typical summer day-night temperature swing: "low" (under 16 F), "medium" (16 to 25 F), "high" (over 25 F). Needed without a station. |
| `humidity_difference_gr_lb` |  | number (grains/lb) | Outdoor minus indoor moisture content at cooling design conditions, in grains of water per pound of dry air. Negative in dry climates. Needed without a station. |
| `latitude_deg` |  | number (deg, -90 to 90) | Latitude, positive north. Needed without a station. |
| `elevation_ft` |  | number (ft) | Elevation above sea level. Default 0 without a station. |
| `heating_setpoint_f` |  | number (F) | Indoor temperature in winter. Default 70. |
| `cooling_setpoint_f` |  | number (F) | Indoor temperature in summer. Default 75. |
| `cooling_indoor_humidity_frac` |  | number (0-1, 0 to 1) | Indoor relative humidity in summer, as a fraction. Default 0.5 (0.45 in dry climates). |
| `ground_conductivity_btu_hr_ft_f` |  | number (Btu/h-ft-F, at least 0) | Soil thermal conductivity. Default 0.8. |
| `cooling_outdoor_humidity_ratio_lb_lb` |  | number (lb/lb, at least 0) | Moisture content of outdoor air at cooling design, pounds of water per pound of dry air. Used for duct loads. |
| `annual_average_temp_f` |  | number (F) | Annual average outdoor temperature. |
| `ground_temp_winter_f` |  | number (F) | Coldest monthly shallow-ground temperature. |
| `ground_temp_summer_f` |  | number (F) | Warmest monthly shallow-ground temperature. |
| `weather_shielding_factor` |  | number (at least 0) | ASHRAE 62.2 weather and shielding factor of the station (no unit, about 0.4 to 0.7). |

### assemblies

Library of constructions (walls, roofs, ceilings, floors), each defined once and used by id from surfaces.

#### assemblies (each item)

One construction. Give either layers (R-value is calculated, air films added automatically) or r_value_hr_ft2_f_btu for the whole assembly.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `type` | yes | one of: `wall`, `roof`, `ceiling`, `floor` | What the assembly is used for. It sets which air films are added. |
| `r_value_hr_ft2_f_btu` |  | number (hr-ft2-F/Btu, at least 0) | R-value of the whole assembly INCLUDING air films, when layers are not given. |
| `layers` |  | list | Layers from the inside face to the outside face. Do not include air films. |
| `framing_frac` |  | number (0-1, 0 to 0.99) | Share of the area taken up by framing members, for assemblies with a framed layer (0.25 is typical for 16-in stud spacing with plates and headers). Default 0. |
| `construction` |  | one of: `wood_stud`, `steel_stud`, `double_wood_stud`, `sip`, `cmu`, `brick`, `adobe`, `concrete`, `stone`, `log`, `icf`, `straw_bale` | Walls: structural type, used to estimate how slowly the wall passes summer heat. Default "wood_stud". |
| `cladding` |  | one of: `wood`, `vinyl`, `aluminum`, `fiber_cement`, `stucco`, `shingle`, `brick`, `stone`, `other`, `none` | Walls: exterior finish. Only "brick" and "stone" change the calculation. Default "wood". |
| `solar_absorptance_frac` |  | number (0-1, 0 to 1) | Walls: share of sunlight the exterior absorbs: about 0.3 white, 0.5 light, 0.7 medium, 0.9 dark. Default 0.7. |
| `roofing` |  | one of: `asphalt_shingles`, `wood_shingles`, `metal`, `clay_tile`, `concrete`, `plastic_rubber`, `eps`, `shingles` | Roofs: roofing material. Default "asphalt_shingles". |
| `roof_color` |  | one of: `dark`, `medium_dark`, `medium`, `medium_light`, `light`, `white`, `reflective` | Roofs: color. Default "medium". |
| `radiant_barrier` |  | true / false | Roofs: true if there is a radiant barrier under the roof deck. |

##### assemblies (each item) > layers (each item)

One layer, listed from the inside face to the outside face. Give material (with thickness_in unless the material has a fixed R-value), or r_per_inch_hr_ft2_f_btu_in with thickness_in, or r_value_hr_ft2_f_btu.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `name` |  | text | Name shown to people. |
| `material` |  | text | Id of a material in the materials list (docs/FORMAT.md), which supplies the R-value per inch. |
| `thickness_in` |  | number (in, at least 0) | Layer thickness. |
| `r_per_inch_hr_ft2_f_btu_in` |  | number (hr-ft2-F/Btu per in, at least 0) | R-value per inch of thickness. |
| `r_value_hr_ft2_f_btu` |  | number (hr-ft2-F/Btu, at least 0) | R-value of the whole layer (e.g. a rated batt or an air space). |
| `framing_material` |  | text | For a framed layer: id of the material of the framing members (usually softwood). |
| `framing_r_per_inch_hr_ft2_f_btu_in` |  | number (hr-ft2-F/Btu per in, at least 0) | For a framed layer: R per inch of the framing members, as an alternative to framing_material. |
| `source` |  | text | Where the R-value came from. |

### zones

Zones: groups of rooms served and controlled together (one thermostat). At least one.

#### zones (each item)

One zone.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `heating_setpoint_f` |  | number (F) | Winter indoor temperature for this zone, if different from the house. |
| `cooling_setpoint_f` |  | number (F) | Summer indoor temperature for this zone, if different from the house. |
| `radiant_floor_heat` |  | true / false | True if the zone is heated by a radiant floor. |

### rooms

Conditioned rooms. At least one.

#### rooms (each item)

One room.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `zone` | yes | id | Id of the zone this room belongs to. |
| `floor_area_ft2` | yes | number (ft2, at least 0) | Floor area. |
| `ceiling_height_ft` |  | number (ft, at least 0) | Average ceiling height. Default 8. |
| `occupant_count` |  | number (people, at least 0) | People in the room at the cooling peak. If no room gives this, a house total is assumed and shared by floor area. |
| `internal_sensible_gain_btu_hr` |  | number (Btu/h) | Heat from appliances and lighting in this room at the cooling peak. If no room gives this, a house total is assumed and shared by floor area. |
| `internal_latent_gain_btu_hr` |  | number (Btu/h) | Moisture load from appliances in this room, as heat. Default 0. |
| `below_grade` |  | true / false | True if the room is in a conditioned basement. |
| `infiltration_share_frac` |  | number (0-1, at least 0) | Share of whole-house air leakage assigned to this room. If any room has one, shares are used (they are scaled to add to 1); otherwise leakage is shared by exposed wall area. |
| `outline_ft` |  | list | Optional floor outline for CAD tools: list of [x, y] or [x, y, z] points in feet. Not used by the engine. |

### spaces

Spaces that are not lived-in rooms: attics, crawlspaces, unconditioned basements, garages, porches, and conditioned-but-unoccupied spaces such as a sealed attic.

#### spaces (each item)

One space.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `type` | yes | one of: `vented_attic`, `unvented_attic`, `vented_crawlspace`, `unvented_crawlspace`, `unconditioned_basement`, `garage`, `open_porch`, `conditioned`, `custom` | Kind of space. "conditioned": inside the insulation and air barrier but not lived in (e.g. a sealed, roof-insulated attic); it must name a zone. "open_porch": open to outdoor air but shaded. "custom": temperature set by the weights or design temperatures below. |
| `zone` |  | id | For type "conditioned": the zone whose system conditions it. |
| `volume_ft3` |  | number (ft3, at least 0) | Air volume. Default: estimated from the space's floor or roof surfaces. |
| `vent_area_per_floor_area_frac` |  | number (ft2/ft2, at least 0) | Vented attics and crawlspaces: net vent area divided by floor area. Default 1/300 (attic), 1/150 (crawlspace). |
| `vent_air_changes_per_hr` |  | number (1/h, at least 0) | Vented attics: air changes per hour, as an alternative to vent area. |
| `heating_design_temp_f` |  | number (F) | Override: temperature of the space at the heating design condition. |
| `cooling_design_temp_f` |  | number (F) | Override: temperature of the space at the cooling design condition. |
| `indoor_weight_frac` |  | number (0-1, 0 to 1) | Type "custom": weight of indoor temperature in the space temperature. |
| `outdoor_weight_frac` |  | number (0-1, 0 to 1) | Type "custom": weight of outdoor temperature. |
| `ground_weight_frac` |  | number (0-1, 0 to 1) | Type "custom": weight of ground temperature. |
| `min_temp_f` |  | number (F) | Type "custom": the space never gets colder than this. |
| `duct_regain_frac` |  | number (0-1, 0 to 1) | Type "custom": share of duct losses in this space that return to the house. |

### surfaces

Walls, roofs, ceilings, floors and slabs: of rooms, and of unconditioned spaces (an attic's roof, a crawlspace's walls and floor). The `type` field decides which other fields apply.

#### surfaces: type `wall`

Above-grade wall.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"wall"` | Always "wall" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `outside` |  | text | What is on the other side: "outdoors", "ground", "adiabatic" (no heat flow, e.g. a party wall), the id of an unconditioned space, or the id of another room (a partition between rooms; it only matters when the two rooms are in zones with different setpoints). Default "outdoors". |
| `assembly` | yes | id | Id of an entry in assemblies that describes the construction. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Compass direction the outside of the surface faces: 0 = north, 90 = east, 180 = south, 270 = west. |

#### surfaces: type `rim_joist`

Rim (band) joist around a floor frame. Calculated like a wood-framed wall.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"rim_joist"` | Always "rim_joist" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `outside` |  | text | What is on the other side: "outdoors", "ground", "adiabatic" (no heat flow, e.g. a party wall), the id of an unconditioned space, or the id of another room (a partition between rooms; it only matters when the two rooms are in zones with different setpoints). Default "outdoors". |
| `assembly` | yes | id | Id of an entry in assemblies that describes the construction. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Compass direction the outside of the surface faces: 0 = north, 90 = east, 180 = south, 270 = west. |

#### surfaces: type `foundation_wall`

Basement or crawlspace wall, wholly or partly below grade.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"foundation_wall"` | Always "foundation_wall" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `outside` |  | text | What is on the other side: "outdoors", "ground", "adiabatic" (no heat flow, e.g. a party wall), the id of an unconditioned space, or the id of another room (a partition between rooms; it only matters when the two rooms are in zones with different setpoints). Default "ground". |
| `assembly` |  | id | Optional. Id of an assembly giving the whole-wall R-value. If absent, the wall is built from material, thickness_in and the insulation fields. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Compass direction the outside of the surface faces: 0 = north, 90 = east, 180 = south, 270 = west. |
| `height_ft` | yes | number (ft, at least 0) | Total wall height. |
| `depth_below_grade_ft` | yes | number (ft, at least 0) | How much of the height is below the outside ground level. |
| `length_ft` |  | number (ft, at least 0) | Optional wall length. Default: area_ft2 / height_ft. |
| `thickness_in` |  | number (in, at least 0) | Wall thickness. Default 8. |
| `material` |  | one of: `solid_concrete`, `double_brick`, `wood`, `concrete_block`, `concrete_block_solid_core`, `concrete_block_perlite_core`, `concrete_block_foam_core`, `concrete_block_vermiculite_core` | Structural material. Default "solid_concrete". |
| `interior_insulation` |  | object | Continuous insulation on the inside face. |
| `exterior_insulation` |  | object | Continuous insulation on the outside face. |

##### surfaces: type `foundation_wall` > interior_insulation

Continuous insulation on the inside face.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value of the insulation alone. |
| `distance_to_top_ft` |  | number (ft, at least 0) | Distance from the top of the wall down to the top of the insulation. |
| `distance_to_bottom_ft` | yes | number (ft, at least 0) | Distance from the top of the wall down to the bottom of the insulation. |

##### surfaces: type `foundation_wall` > exterior_insulation

Continuous insulation on the outside face.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value of the insulation alone. |
| `distance_to_top_ft` |  | number (ft, at least 0) | Distance from the top of the wall down to the top of the insulation. |
| `distance_to_bottom_ft` | yes | number (ft, at least 0) | Distance from the top of the wall down to the bottom of the insulation. |

#### surfaces: type `roof`

Roof. Over an attic, inside is the attic space; over a cathedral ceiling, inside is the room.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"roof"` | Always "roof" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `assembly` | yes | id | Id of an entry in assemblies that describes the construction. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Compass direction the outside of the surface faces: 0 = north, 90 = east, 180 = south, 270 = west. |
| `pitch_rise_per_12` |  | number (in per 12 in, at least 0) | Roof pitch as inches of rise per 12 inches of run (6 means 6-in-12). 0 is flat. Default 6. |

#### surfaces: type `ceiling`

Ceiling of a room, under an attic or another space.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"ceiling"` | Always "ceiling" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `outside` | yes | text | What is on the other side: "outdoors", "ground", "adiabatic" (no heat flow, e.g. a party wall), the id of an unconditioned space, or the id of another room (a partition between rooms; it only matters when the two rooms are in zones with different setpoints). Required. |
| `assembly` | yes | id | Id of an entry in assemblies that describes the construction. |

#### surfaces: type `floor`

Framed floor of a room, over a crawlspace, garage, open air or another space.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"floor"` | Always "floor" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `outside` | yes | text | What is on the other side: "outdoors", "ground", "adiabatic" (no heat flow, e.g. a party wall), the id of an unconditioned space, or the id of another room (a partition between rooms; it only matters when the two rooms are in zones with different setpoints). Required. |
| `assembly` | yes | id | Id of an entry in assemblies that describes the construction. |

#### surfaces: type `slab`

Concrete floor on the ground (slab on grade, basement floor, or the dirt or concrete floor of a crawlspace).

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"slab"` | Always "slab" for this kind of surface. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `inside` | yes | id | Id of the room (or unconditioned space) this surface belongs to. For a wall of a room, the room. For the roof over an attic, the attic space. |
| `area_ft2` | yes | number (ft2, at least 0) | Gross area, including any windows, doors or skylights set into it. |
| `outline_ft` |  | list | Optional polygon outline for CAD tools and 3D views: list of [x, y, z] points in feet. The engine uses area_ft2, not this. |
| `exposed_perimeter_ft` | yes | number (ft, at least 0) | Length of slab edge exposed to outdoor air or ground (not edges shared with other conditioned space). |
| `thickness_in` |  | number (in, at least 0) | Slab thickness. Default 4. Use 0 for a dirt floor. |
| `perimeter_insulation` |  | object | Vertical insulation at the slab edge. |
| `under_slab_insulation` |  | object | Horizontal insulation under the slab. |
| `exterior_horizontal_insulation` |  | object | Horizontal insulation wing outside the foundation. |

##### surfaces: type `slab` > perimeter_insulation

Vertical insulation at the slab edge.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value. |
| `depth_ft` | yes | number (ft, at least 0) | How far down it extends. |

##### surfaces: type `slab` > under_slab_insulation

Horizontal insulation under the slab.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value. |
| `width_ft` |  | number (ft, at least 0) | Width of the insulated band in from the edge. |
| `whole_slab` |  | true / false | True if the whole slab is insulated underneath. |

##### surfaces: type `slab` > exterior_horizontal_insulation

Horizontal insulation wing outside the foundation.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value. |
| `width_ft` | yes | number (ft, at least 0) | Width outward from the foundation. |
| `depth_below_grade_ft` |  | number (ft, at least 0) | Depth below grade. |

### openings

Windows, doors and skylights, each set into a surface. The `type` field decides which other fields apply.

#### openings: type `window`

Window or glass door.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"window"` | Always "window" for this kind of opening. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `count` |  | whole number (at least 1) | How many identical units this entry stands for. Default 1. |
| `area_ft2` |  | number (ft2, at least 0) | Area of ONE unit (rough opening). Give this, or width_ft and height_ft. |
| `width_ft` |  | number (ft, at least 0) | Width of one unit. |
| `height_ft` |  | number (ft, at least 0) | Height of one unit. |
| `surface` | yes | id | Id of the wall (or foundation wall) the window is in. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Direction the window faces. Default: the wall's azimuth_deg. |
| `glazing` |  | text | Id of a glazing preset (see the glazing list in docs/FORMAT.md), used when u_factor_btu_hr_ft2_f and shgc are not given. |
| `u_factor_btu_hr_ft2_f` |  | number (Btu/h-ft2-F, at least 0) | Whole-unit U-factor. |
| `shgc` |  | number (0-1, 0 to 1) | Solar heat gain coefficient (0 to 1, no unit). |
| `glass_layers` |  | one of: `1`, `2`, `3` | Number of panes, if known (used to pick interior-shading factors). |
| `glass_type` |  | one of: `clear`, `tinted`, `reflective`, `tinted_reflective`, `low_e`, `low_e_low_solar`, `low_e_high_solar` | Glass type, if known. |
| `storm_window` |  | one of: `none`, `clear`, `low_e` | Storm window added over the unit. Default "none". |
| `interior_shading` |  | object | Blinds, shades or curtains inside the window. Leave out for none. |
| `exterior_shading` |  | object | Shading outside the glass other than an overhang. |
| `insect_screen` |  | object | Insect screen. |
| `overhang` |  | object | Roof overhang, porch roof or awning above the window. |

##### openings: type `window` > interior_shading

Blinds, shades or curtains inside the window. Leave out for none.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` |  | one of: `dark_blinds`, `medium_blinds`, `light_blinds`, `dark_shades`, `medium_shades`, `light_shades`, `dark_curtains`, `medium_curtains`, `light_curtains` | Kind and color of the shading. |
| `coverage_frac` |  | number (0-1, 0 to 1) | Share of the window covered in summer. Default 0.5. |
| `blinds_position` |  | one of: `closed`, `half_open`, `open` | Blinds only. Default "closed". |
| `coefficient_frac` |  | number (0-1, 0 to 1) | Alternative to type: shading coefficient entered directly (1 = no shading). |

##### openings: type `window` > exterior_shading

Shading outside the glass other than an overhang.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | one of: `solar_screens`, `solar_film`, `other` | Kind of exterior shading. |
| `coefficient_frac` |  | number (0-1, 0 to 1) | For type "other": share of solar gain that still gets through (1 = no shading). |

##### openings: type `window` > insect_screen

Insect screen.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `location` | yes | one of: `interior`, `exterior` | Which side of the glass. |
| `coverage_frac` |  | number (0-1, 0 to 1) | Share of the window covered. Default 1. |

##### openings: type `window` > overhang

Roof overhang, porch roof or awning above the window.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `depth_ft` | yes | number (ft, at least 0) | How far it projects out from the wall. |
| `distance_to_window_top_ft` | yes | number (ft, at least 0) | Vertical distance from the overhang down to the top of the glass. |
| `distance_to_window_bottom_ft` | yes | number (ft, at least 0) | Vertical distance from the overhang down to the bottom of the glass. |

#### openings: type `door`

Opaque door.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"door"` | Always "door" for this kind of opening. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `count` |  | whole number (at least 1) | How many identical units this entry stands for. Default 1. |
| `area_ft2` |  | number (ft2, at least 0) | Area of ONE unit (rough opening). Give this, or width_ft and height_ft. |
| `width_ft` |  | number (ft, at least 0) | Width of one unit. |
| `height_ft` |  | number (ft, at least 0) | Height of one unit. |
| `surface` | yes | id | Id of the wall the door is in. |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | R-value of the door. |

#### openings: type `skylight`

Skylight.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | `"skylight"` | Always "skylight" for this kind of opening. |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `count` |  | whole number (at least 1) | How many identical units this entry stands for. Default 1. |
| `area_ft2` |  | number (ft2, at least 0) | Area of ONE unit (rough opening). Give this, or width_ft and height_ft. |
| `width_ft` |  | number (ft, at least 0) | Width of one unit. |
| `height_ft` |  | number (ft, at least 0) | Height of one unit. |
| `surface` | yes | id | Id of the roof the skylight is in. |
| `azimuth_deg` |  | number (deg, 0 to 360) | Direction the roof slope faces. Default: the roof's azimuth_deg. |
| `u_factor_btu_hr_ft2_f` | yes | number (Btu/h-ft2-F, at least 0) | Whole-unit U-factor. |
| `shgc` | yes | number (0-1, 0 to 1) | Solar heat gain coefficient (0 to 1, no unit). |
| `storm_window` |  | one of: `none`, `clear`, `low_e` | Storm window added over the unit. Default "none". |
| `ceiling` |  | id | If the roof is over an attic: id of the ceiling surface the light shaft comes through. |
| `interior_shading_coefficient_frac` |  | number (0-1, 0 to 1) | Shading coefficient of any interior shade (1 = none). |
| `curb` |  | object | Skylight curb. |
| `shaft` |  | object | Light shaft through the attic. |

##### openings: type `skylight` > curb

Skylight curb.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `area_ft2` | yes | number (ft2, at least 0) | Curb area. |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | Curb R-value. |

##### openings: type `skylight` > shaft

Light shaft through the attic.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `area_ft2` | yes | number (ft2, at least 0) | Shaft wall area. |
| `r_value_hr_ft2_f_btu` | yes | number (hr-ft2-F/Btu, at least 0) | Shaft wall R-value. |

### air

Air leakage, mechanical ventilation and ducts.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `infiltration` |  | object | Air leakage of the whole house. Give a blower-door result if there is one. |
| `ventilation` |  | list | Whole-house mechanical ventilation fans that run continuously or on a schedule (not bath or kitchen spot fans). |
| `ducts` |  | list | Duct systems, one per HVAC system that has ducts. |

#### air > infiltration

Air leakage of the whole house. Give a blower-door result if there is one.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `method` | yes | one of: `blower_door`, `leakiness_estimate` | "blower_door": a measured (or estimated) leakage number is given below. "leakiness_estimate": only a description is given. |
| `air_changes_per_hr_at_50pa` |  | number (1/h, at least 0) | Blower-door result as ACH50: air changes per hour at 50 pascals (or at test_pressure_pa). |
| `airflow_cfm_at_50pa` |  | number (cfm, at least 0) | Blower-door result as CFM50: airflow at 50 pascals (or at test_pressure_pa). |
| `test_pressure_pa` |  | number (Pa, at least 1) | Test pressure if not 50 Pa. |
| `natural_air_changes_per_hr` |  | number (1/h, at least 0) | Alternative: annual-average natural air changes per hour. |
| `leakage_area_in2` |  | number (in2, at least 0) | Alternative: effective leakage area at 4 Pa. |
| `leakiness` |  | one of: `very_tight`, `tight`, `average`, `leaky`, `very_leaky` | For method "leakiness_estimate". |
| `volume_ft3` |  | number (ft3, at least 0) | Blower door: volume the test was normalized by. Leakiness estimate: above-grade conditioned volume. Default: sum of room (and conditioned space) volumes. |
| `height_ft` |  | number (ft, at least 0) | Height from the lowest to the highest point of the leaky envelope. Only needed with natural_air_changes_per_hr. |
| `shielding_class` |  | whole number (1 to 5) | Wind shielding: 1 = no obstructions, 3 = some, 4 = typical suburban (default), 5 = heavily shielded. |
| `stories_above_grade` |  | number (stories, at least 1) | Number of conditioned stories above grade. Default 1. |
| `building_type` |  | one of: `detached`, `attached` | Default "detached". |
| `exterior_envelope_frac` |  | number (0-1, 0 to 1) | Attached units: share of the tested envelope that faces outdoors. Default 1. |
| `unit_height_above_grade_ft` |  | number (ft, at least 0) | Attached units and apartments: height of the unit's floor above the ground. Default 0. |
| `site_shielding` |  | one of: `normal`, `exposed`, `well_shielded` | Attached units above grade: how sheltered the site is from wind. Default "normal". |
| `fireplace` |  | true / false | True if there is an open fireplace (adds 20 cfm in winter). |

#### air > ventilation (each item)

One fan or ventilator.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `type` | yes | one of: `supply`, `exhaust`, `balanced`, `erv`, `hrv` | Kind of system. |
| `airflow_cfm` | yes | number (cfm, at least 0) | Airflow while running. |
| `hours_per_day_hr` |  | number (h, 0 to 24) | Hours of operation per day. Default 24. |
| `sensible_recovery_frac` |  | number (0-1, 0 to 1) | ERV/HRV: share of the temperature difference recovered (apparent sensible effectiveness). |
| `latent_recovery_frac` |  | number (0-1, 0 to 1) | ERV: share of the moisture difference recovered. |

#### air > ducts (each item)

The ducts of one HVAC system.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `system` | yes | id | Id of the hvac system these ducts belong to. |
| `supply_leakage_cfm_at_25pa` |  | number (cfm, at least 0) | Supply-side leakage to outside at 25 Pa. |
| `return_leakage_cfm_at_25pa` |  | number (cfm, at least 0) | Return-side leakage to outside at 25 Pa. |
| `supply_leakage_frac` |  | number (0-1, 0 to 1) | Alternative: supply leakage as a share of system airflow. |
| `return_leakage_frac` |  | number (0-1, 0 to 1) | Alternative: return leakage as a share of system airflow. |
| `segments` | yes | list | Runs of duct, grouped by where they are. |

##### air > ducts (each item) > segments (each item)

Ducts of one kind in one location.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `type` | yes | one of: `supply`, `return` | Supply or return. |
| `location` | yes | text | Where the ducts run: the id of a room or space, or "outdoors". Ducts in a room or a conditioned space lose nothing to outside. |
| `surface_area_ft2` |  | number (ft2, at least 0) | Duct surface area in this location. |
| `share_of_ducts_frac` |  | number (0-1, 0 to 1) | Alternative to surface_area_ft2: share of this system's supply (or return) ducts that is in this location; area is then estimated from the floor area served. |
| `insulation_r_value_hr_ft2_f_btu` |  | number (hr-ft2-F/Btu, at least 0) | Nominal R-value printed on the duct insulation (0 for bare ducts). Converted to an effective value. |
| `effective_r_value_hr_ft2_f_btu` |  | number (hr-ft2-F/Btu, at least 0) | Alternative: effective R-value including air films. |

### equipment

Heat-producing equipment reported on its own line in the results, e.g. a dehumidifier.

#### equipment (each item)

One piece of equipment.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `type` | yes | one of: `dehumidifier`, `other` | Kind of equipment. |
| `room` | yes | id | Id of the room (or conditioned space) the heat goes into. |
| `sensible_heat_btu_hr` | yes | number (Btu/h) | Heat given off into the room while running at the cooling peak. |
| `latent_heat_btu_hr` |  | number (Btu/h) | Moisture added to the room, as heat. Negative for moisture removed. |

### hvac

Heating and cooling systems. Equipment sizes are not inputs: the calculation says what is needed.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `systems` |  | list | One entry per system. |

#### hvac > systems (each item)

One heating and/or cooling system serving one zone.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `zone` | yes | id | Id of the zone this system serves. |
| `heating` |  | one of: `furnace`, `boiler`, `heat_pump`, `electric_resistance`, `other`, `none` | Kind of heating. Default "none". |
| `cooling` |  | one of: `central_ac`, `heat_pump`, `mini_split`, `other`, `none` | Kind of cooling. Default "none". |
| `heating_airflow_cfm_per_ton` |  | number (cfm per 12,000 Btu/h, at least 0) | Heating airflow per 12,000 Btu/h of load. Default 240 (furnace) or 360 (heat pump). |
| `cooling_airflow_cfm_per_ton` |  | number (cfm per 12,000 Btu/h, at least 0) | Cooling airflow per 12,000 Btu/h of load. Default 360. |
| `blower_heat_btu_hr` |  | number (Btu/h, at least 0) | Heat added to the air by the blower motor in cooling. Default 0. |
| `piping_loss_btu_hr` |  | number (Btu/h, at least 0) | Hydronic systems: heat lost from piping outside the conditioned space. Default 0. |
| `supply_registers` |  | list of ids | Ids of the rooms that have a supply register (or radiator, or indoor unit) of this system. |
| `returns` |  | list of ids | Ids of the rooms that have a return grille. |

### scenarios

What-if variations, each a short list of changes against the baseline house above.

#### scenarios (each item)

One scenario.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `id` | yes | id | Unique id of this item. Lowercase letters, digits, hyphens and underscores; must start with a letter or digit. |
| `name` |  | text | Name shown to people. |
| `description` |  | text | What the scenario represents. |
| `notes` |  | text | Free-form note. Never used in the calculation. |
| `cost_usd` |  | number (US dollars, at least 0) | Cost the user enters for this scenario. RightTon never supplies prices. |
| `includes` |  | list of ids | Ids of other scenarios whose changes are applied first, to stack scenarios. |
| `changes` | yes | list | Changes, applied in order. |

##### change: op `set`

Set one field.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `op` | yes | `"set"` | "set" |
| `path` | yes | text | Where: section/id/field, e.g. "surfaces/north-wall/assembly" or "air/infiltration/air_changes_per_hr_at_50pa". Nested fields continue the path: "openings/w1/overhang/depth_ft". |
| `value` | yes | any | New value. |

##### change: op `add`

Add an item to a section.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `op` | yes | `"add"` | "add" |
| `section` | yes | text | Section the item goes into, e.g. "openings" or "air/ventilation". |
| `item` | yes | object | The complete new item, with its own id. |

##### change: op `remove`

Remove an item or a field.

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `op` | yes | `"remove"` | "remove" |
| `path` | yes | text | What to remove, e.g. "openings/w3". |

### extensions

Data owned by other tools, each under its own key (e.g. extensions.my-cad-tool). Readers must keep extensions they do not understand when re-saving.

### A number with its source

| Field | Required | Type and unit | Meaning |
| --- | --- | --- | --- |
| `value` | yes | number | The number. |
| `source` |  | text | Where the number came from (e.g. "blower door test, 2024", "tape measure"). |
| `confidence` |  | one of: `measured`, `estimated`, `default` | How far to trust it. A bare number counts as "default". |

<!-- END GENERATED: field-reference -->

## Materials

Ids usable as `material` or `framing_material` in an assembly layer. Entries marked `estimated` are
typical values not yet tied to a citable open source; prefer a rated or measured R-value when known.

<!-- BEGIN GENERATED: materials -->
| Material id | Name | R per inch | Fixed R | Typical thickness (in) | Confidence | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `gypsum_board` | Gypsum board (drywall) | 0.9 |  | 0.5 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `plaster_on_wood_lath` | Plaster on wood lath |  | 0.4 | 0.875 | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `plaster_on_metal_lath` | Plaster on metal lath |  | 0.23 | 0.75 | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `wood_paneling` | Wood paneling or boards (interior) | 1.249 |  | 0.75 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `softwood` | Softwood lumber, boards, plywood, OSB | 1.249 |  |  | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `board_sheathing` | Board sheathing (3/4 in, straight or diagonal) | 1.249 |  | 0.75 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `air_space_closed` | Closed air space (empty framed cavity) |  | 1.0 |  | default | OpenStudio-HPXML materials.rb Material.AirCavityClosed (R-1.0 for any enclosed gap) |
| `fiberglass_batt` | Fiberglass batt | 3.2 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `mineral_wool_batt` | Mineral wool batt | 4.0 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `cellulose_dense_pack` | Cellulose, dense-packed in a closed cavity | 3.6 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `cellulose_loose_fill` | Cellulose, loose fill (attic floor) | 3.5 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `fiberglass_loose_fill` | Fiberglass, loose fill (attic floor) | 2.5 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `vermiculite` | Vermiculite, loose fill | 2.2 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `spray_foam_closed_cell` | Spray polyurethane foam, closed cell | 6.0 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `spray_foam_open_cell` | Spray polyurethane foam, open cell | 3.6 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `rigid_foam_generic` | Rigid foam board (generic) | 4.9 |  |  | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `xps_board` | Extruded polystyrene (XPS) board | 5.0 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `eps_board` | Expanded polystyrene (EPS) board | 4.0 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `polyiso_board` | Polyisocyanurate board, foil faced | 6.0 |  |  | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `wood_siding` | Wood siding or clapboard | 1.408 |  | 0.75 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `vinyl_or_aluminum_siding` | Vinyl or aluminum siding (hollow backed) | 1.613 |  | 0.375 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `fiber_cement_siding` | Fiber-cement siding | 0.559 |  | 0.375 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `hardboard_siding` | Hardboard (Masonite) siding | 1.449 |  | 0.5 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `asbestos_cement_shingle` | Asbestos-cement shingle siding | 0.238 |  | 0.25 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `stucco` | Stucco | 0.222 |  | 1.0 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `brick` | Brick | 0.182 |  | 4.0 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `stone` | Stone | 0.08 |  | 1.0 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `concrete` | Concrete | 0.08 |  |  | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `concrete_block_hollow` | Concrete block, hollow core | 0.2 |  | 8.0 | default | OpenStudio-HPXML materials.rb FoundationWallMaterial (k = 5.0, derived by NREL from NCMA TEK data) |
| `straw_bale` | Straw bale | 2.4 |  |  | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
| `asphalt_shingles_on_deck` | Asphalt shingles | 0.887 |  | 0.25 | default | OpenStudio-HPXML materials.rb RoofMaterialAndSheathing (k = 1.128) |
| `wood_shingles_roof` | Wood shingles or shakes | 1.408 |  | 0.5 | estimated | Typical published value; not yet checked against a citable open source [CONFIRM] |
| `metal_roofing` | Metal roofing |  | 0.0 | 0.02 | default | OpenStudio-HPXML materials.rb RoofMaterialAndSheathing (k = 346.9; negligible resistance) |
| `carpet_and_pad` | Carpet with pad |  | 2.08 | 0.5 | default | OpenStudio-HPXML materials.rb Material.CoveringBare (R-2.08 carpet) |
| `hardwood_flooring` | Hardwood flooring | 1.249 |  | 0.75 | default | OpenStudio-HPXML materials.rb (commit fb18723), conductivity k converted to R per inch = 1/k |
<!-- END GENERATED: materials -->

## Glazing presets

Ids usable as `glazing` on a window.

<!-- BEGIN GENERATED: glazing -->
| Glazing id | Description | U-factor (Btu/h-ft2-F) | SHGC |
| --- | --- | --- | --- |
| `single_clear_wood` | Single pane, clear, wood or vinyl frame | 0.89 | 0.64 |
| `single_clear_metal` | Single pane, clear, aluminum frame | 1.27 | 0.75 |
| `single_tinted_wood` | Single pane, tinted, wood or vinyl frame | 0.89 | 0.54 |
| `double_clear_wood` | Double pane, clear, wood or vinyl frame | 0.51 | 0.56 |
| `double_clear_metal` | Double pane, clear, aluminum frame | 0.81 | 0.67 |
| `double_clear_metal_thermal_break` | Double pane, clear, aluminum frame with thermal break | 0.6 | 0.67 |
| `double_tinted_wood` | Double pane, tinted, wood or vinyl frame | 0.51 | 0.46 |
| `double_low_e_wood` | Double pane, low-e (insulating), wood or vinyl frame | 0.42 | 0.52 |
| `double_low_e_argon_wood` | Double pane, low-e (insulating), argon, wood or vinyl frame | 0.39 | 0.52 |
| `double_low_e_solar_control_wood` | Double pane, low-e (solar control), wood or vinyl frame | 0.39 | 0.31 |
| `double_low_e_solar_control_argon_wood` | Double pane, low-e (solar control), argon, wood or vinyl frame | 0.36 | 0.31 |
| `triple_low_e_argon_wood` | Triple pane, low-e, argon, wood or vinyl frame | 0.27 | 0.31 |
<!-- END GENERATED: glazing -->

## Weather stations

Starter set. Any other location works by giving `location.design_conditions` instead (the web app can fill
those in from an EPW weather file).

<!-- BEGIN GENERATED: stations -->
| weather_station_id | Station | Heating design (F) | Cooling design (F) | Latitude |
| --- | --- | --- | --- | --- |
| `"723445"` | Fayetteville Drake Field | 15 | 93 | 36.0 |
| `"722780"` | Phoenix Sky Harbor Intl Ap | 41 | 108 | 33.5 |
| `"720533"` | Boulder.Muni.Ap | 10 | 91 | 40.0 |
| `"724660"` | Colorado Springs Muni Ap | 6 | 88 | 38.8 |
| `"725650"` | Denver Intl Ap | 7 | 92 | 39.8 |
| `"724089"` | Wilmington New Castle Cnty Ap | 16 | 89 | 39.7 |
| `"722020"` | Miami Intl Ap | 52 | 91 | 25.8 |
| `"911820"` | Honolulu Intl Arpt | 63 | 89 | 21.3 |
| `"725450"` | Cedar Rapids Municipal Ap | -4 | 89 | 41.9 |
| `"724386"` | Lafayette Purdue Univ Ap | 4 | 90 | 40.4 |
| `"724060"` | Baltimore Blt Washngtn Intl | 17 | 91 | 39.2 |
| `"727450"` | Duluth International Arpt | -14 | 81 | 46.8 |
| `"727720"` | Helena Regional Airport | -8 | 89 | 46.6 |
| `"723140"` | Charlotte Douglas Intl Arpt | 25 | 92 | 35.2 |
| `"745966"` | Cape May Co | 19 | 87 | 39.0 |
| `"723860"` | Las Vegas Mccarran Intl Ap | 33 | 106 | 36.1 |
| `"723544"` | Oklahoma City Wiley | 18 | 97 | 35.5 |
| `"726980"` | Portland International Ap | 29 | 87 | 45.6 |
| `"722590"` | Dallas Fort Worth Intl Ap | 26 | 98 | 32.9 |
| `"722430"` | Houston Bush Intercontinental | 33 | 95 | 30.0 |
| `"724699"` | Boulder | 10 | 91 | 40.1 |
| `"688160"` | Cape Town | 41 | 84 | -34.0 |
<!-- END GENERATED: stations -->

## Defaults

<!-- BEGIN GENERATED: defaults -->
| Default | Value | Unit | Used when | Confidence | Source |
| --- | --- | --- | --- | --- | --- |
| `heating_setpoint_f` | 70.0 | F | location.design_conditions has no heating_setpoint_f | default | OpenStudio-HPXML defaults.rb (commit fb18723): indoor heating design temperature |
| `cooling_setpoint_f` | 75.0 | F | location.design_conditions has no cooling_setpoint_f | default | OpenStudio-HPXML defaults.rb (commit fb18723): indoor cooling design temperature |
| `cooling_indoor_humidity_frac` | 0.5 | fraction | no cooling_indoor_humidity_frac; 0.45 is used instead where outdoor design air is drier than indoor air | default | OpenStudio-HPXML defaults.rb (commit fb18723): 50 % indoor relative humidity, 45 % in dry-summer climates |
| `ground_conductivity_btu_hr_ft_f` | 0.8 | Btu/h-ft-F | no ground_conductivity_btu_hr_ft_f | default | OpenStudio-HPXML defaults.rb (commit fb18723) / hvac_sizing.rb: heavy moist soil, R-1.25 per ft, used when the soil type is unknown |
| `ceiling_height_ft` | 8.0 | ft | a room has no ceiling_height_ft | default | OpenStudio-HPXML defaults.rb (commit fb18723): average ceiling height |
| `house_internal_sensible_gain_btu_hr` | 2400.0 | Btu/h | no room has internal_sensible_gain_btu_hr; shared among rooms by floor area | default | OpenStudio-HPXML defaults.rb (commit fb18723): appliance and lighting gain for a house with one refrigerator |
| `house_internal_latent_gain_btu_hr` | 0.0 | Btu/h | no room has internal_latent_gain_btu_hr | default | OpenStudio-HPXML defaults.rb (commit fb18723) |
| `occupant_count_from_bedrooms` | bedroom_count + 1 | people | no room has occupant_count and project.bedroom_count is given; shared among rooms by floor area | default | OpenStudio-HPXML defaults.rb (commit fb18723): number of bedrooms plus one |
| `occupant_count` | 4.0 | people | no room has occupant_count and project.bedroom_count is not given; shared among rooms by floor area | estimated | RightTon choice: the three-bedroom case of the rule above |
| `shielding_class` | 4 | class 1-5 | air.infiltration has no shielding_class | default | OpenStudio-HPXML defaults.rb (commit fb18723): infiltration shielding class for a typical suburban site |
| `stories_above_grade` | 1.0 | stories | air.infiltration has no stories_above_grade | estimated | RightTon choice |
| `interior_shading_coefficient` | 1.0 | fraction | a window has no interior_shading | default | RightTon choice: no credit for blinds or curtains unless they are described (the cautious direction for cooling load) |
| `solar_absorptance_frac` | 0.7 | fraction | a wall assembly has no solar_absorptance_frac | default | OpenStudio-HPXML defaults.rb (commit fb18723): medium-color wall |
| `roof_pitch_rise_per_12` | 6.0 | in per 12 in | a roof has no pitch_rise_per_12 | estimated | RightTon choice |
| `foundation_wall_thickness_in` | 8.0 | in | a foundation wall has no thickness_in | default | OpenStudio-HPXML defaults.rb (commit fb18723) |
| `slab_thickness_in` | 4.0 | in | a slab has no thickness_in | default | OpenStudio-HPXML defaults.rb (commit fb18723) |
| `heating_airflow_cfm_per_ton` | {"furnace": 240.0, "boiler": 240.0, "heat_pump": 360.0, "other": 240.0} | cfm per 12,000 Btu/h | an hvac system gives no heating airflow | default | OpenStudio-HPXML hvac.rb: default actual airflow (RESNET) |
| `cooling_airflow_cfm_per_ton` | 360.0 | cfm per 12,000 Btu/h | an hvac system gives no cooling airflow | default | OpenStudio-HPXML hvac.rb: default actual airflow (RESNET) |
| `duct_supply_area_per_floor_area` | 0.27 | ft2 of duct per ft2 of floor served | a supply duct segment has share_of_ducts_frac instead of surface_area_ft2 | default | OpenStudio-HPXML defaults.rb (commit fb18723) get_duct_surface_area, based on ASHRAE Standard 152 |
| `duct_return_area_per_floor_area_per_return` | 0.05 | ft2 of duct per ft2 of floor served, per return grille (at most 0.25) | a return duct segment has share_of_ducts_frac instead of surface_area_ft2 | default | OpenStudio-HPXML defaults.rb (commit fb18723) get_duct_surface_area, based on ASHRAE Standard 152 |
| `duct_rectangular_fraction` | {"supply": 0.25, "return": 1.0} | fraction of duct length that is rectangular | a duct segment gives insulation_r_value_hr_ft2_f_btu (nominal) instead of an effective R-value | default | OpenStudio-HPXML defaults.rb (commit fb18723) |
| `vented_attic_vent_area_frac` | 0.003333 | ft2 of vent per ft2 of attic floor | a vented attic has no vent_area_per_floor_area_frac | default | OpenStudio-HPXML defaults.rb (commit fb18723): 1/300 |
| `vented_crawlspace_vent_area_frac` | 0.006667 | ft2 of vent per ft2 of crawlspace floor | a vented crawlspace has no vent_area_per_floor_area_frac | default | OpenStudio-HPXML defaults.rb (commit fb18723): 1/150 |
| `space_height_ft` | {"unconditioned_basement": 8.0, "vented_crawlspace": 3.0, "unvented_crawlspace": 3.0, "garage": 8.0} | ft | a space has no volume_ft3: volume = floor area of its slab or floor x this height (attics: footprint x height / 3 from roof pitch) | default | OpenStudio-HPXML defaults.rb (commit fb18723) / geometry.rb |
<!-- END GENERATED: defaults -->
