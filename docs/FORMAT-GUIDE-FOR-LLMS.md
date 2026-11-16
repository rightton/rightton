# How to write a RightTon house file (guide for language models)

You are given this guide and a description of a house. Produce ONE RightTon house file that describes it.
RightTon calculates heating and cooling design loads from the file. This guide is self-contained.

## Output rules

- Output a single YAML document (or JSON if asked) and nothing else inside the code block. File name `*.rtn.yaml`.
- Start with `format_version: 1.0.0`.
- Use ONLY the field names in this guide. Unknown fields are errors. Every unit is in the field name
  (`area_ft2`, `height_ft`, `thickness_in`); never invent `area`, `height`, `r_value`.
- US units. Numbers are bare numbers without units or quotes. Fractions (`_frac`) are 0 to 1, not percent.
- Every item has an `id`: lowercase letters, digits, `-`, `_`; unique across the WHOLE file (a room and a
  wall may not share an id). Refer to things by id. `outdoors`, `ground`, `adiabatic` are reserved words.
- Do not include street addresses, owner names or other personal details. Location is a weather station.
- If the description does not give a value, leave the optional field out (RightTon applies a documented
  default) rather than guessing; if you must estimate something required, wrap it:
  `{value: 180, source: "estimated from 12 ft x 15 ft", confidence: estimated}`. Use
  `confidence: measured` only for things the description says were measured.
- After the file, list in plain text what you assumed.

## Skeleton

```yaml
format_version: 1.0.0
project: {name: ..., description: ..., bedroom_count: 3}
location: {weather_station_id: "725650"}       # or design_conditions, see below
assemblies: [ ... ]     # constructions, each defined once
zones: [ ... ]          # at least one
rooms: [ ... ]          # at least one; each names its zone
spaces: [ ... ]         # attic, crawlspace, garage, porch ... (optional)
surfaces: [ ... ]       # walls, roofs, ceilings, floors, slabs
openings: [ ... ]       # windows, doors, skylights
air: {infiltration: {...}, ventilation: [...], ducts: [...]}
equipment: [ ... ]      # dehumidifier etc. (optional)
hvac: {systems: [ ... ]}
scenarios: [ ... ]      # optional what-ifs
extensions: {}          # optional, other tools' data
```

## Sections and their fields

Required fields are marked `*`. Every item also accepts optional `name` and `notes` (text).

**project**: `name`, `description`, `notes`, `bedroom_count` (whole number), `created_with`.

**location**: `weather_station_id` (text, in quotes, from the station table below), `weather_station_name`,
`design_conditions`. If no listed station is near the house, omit `weather_station_id` and give at least
these five in `design_conditions`: `heating_outdoor_temp_f`, `cooling_outdoor_temp_f`, `daily_temp_range`
(low | medium | high), `humidity_difference_gr_lb` (outdoor minus indoor moisture, grains per lb: about 40 to
60 humid Gulf/Southeast, 20 to 35 Midwest/Northeast, negative in the dry West), `latitude_deg`.
Other optional overrides: `elevation_ft`, `heating_setpoint_f` (default 70), `cooling_setpoint_f` (default 75),
`cooling_indoor_humidity_frac`, `ground_conductivity_btu_hr_ft_f`, `cooling_outdoor_humidity_ratio_lb_lb`,
`annual_average_temp_f`, `ground_temp_winter_f`, `ground_temp_summer_f`, `weather_shielding_factor`.

**assemblies** (each): `id`*, `type`* (wall | roof | ceiling | floor), then EITHER `layers` OR
`r_value_hr_ft2_f_btu` (whole assembly including air films).
- `layers`: list from the INSIDE face to the OUTSIDE face. Do not add air films. Each layer is one of:
  `{material: <id>, thickness_in: N}`; `{material: <id>}` when the material has a fixed R or a typical
  thickness; `{name: ..., r_value_hr_ft2_f_btu: N}`; `{name: ..., r_per_inch_hr_ft2_f_btu_in: N, thickness_in: N}`.
  Optional `source`.
- A framed layer (studs, joists, rafters with fill between them) adds `framing_material: softwood` (or
  `framing_r_per_inch_hr_ft2_f_btu_in`) and needs `thickness_in`; then set `framing_frac` on the assembly
  (0.25 studs at 16 in, 0.2 at 24 in, 0.1 joists/rafters).
- Walls: `construction` (default wood_stud), `cladding` (default wood; brick and stone matter),
  `solar_absorptance_frac` (0.3 white, 0.5 light, 0.7 medium, 0.9 dark).
- Roofs: `roofing`, `roof_color`, `radiant_barrier` (true/false).

**zones** (each): `id`*, `heating_setpoint_f`, `cooling_setpoint_f`, `radiant_floor_heat`.

**rooms** (each): `id`*, `zone`*, `floor_area_ft2`*, `ceiling_height_ft` (default 8), `occupant_count`,
`internal_sensible_gain_btu_hr`, `internal_latent_gain_btu_hr`, `below_grade` (true for a conditioned basement
room), `infiltration_share_frac`, `outline_ft`. Normally leave occupants and internal gains out.

**spaces** (each): `id`*, `type`* (vented_attic | unvented_attic | vented_crawlspace | unvented_crawlspace |
unconditioned_basement | garage | open_porch | conditioned | custom). `conditioned` = inside the insulation but
not lived in (sealed, roof-insulated attic); it needs `zone`. Optional: `volume_ft3`,
`vent_area_per_floor_area_frac`, `vent_air_changes_per_hr`, `heating_design_temp_f`, `cooling_design_temp_f`;
for `custom`: `indoor_weight_frac`, `outdoor_weight_frac`, `ground_weight_frac`, `min_temp_f`, `duct_regain_frac`.

**surfaces** (each): `id`*, `type`*, `inside`* (id of the room or space it belongs to), `area_ft2`* (gross,
including windows and doors), optional `outline_ft`. `outside` is `outdoors`, `ground`, `adiabatic` (party
wall), a space id, or another room id. By `type`:
- `wall`, `rim_joist`: `assembly`*, `azimuth_deg` (needed if it has windows), `outside` (default outdoors).
- `roof`: `assembly`*, `azimuth_deg`, `pitch_rise_per_12`. `inside` is the attic space, or the room for a
  cathedral ceiling. Never give a roof an `outside`.
- `ceiling`: `assembly`*, `outside`* (the attic or space above).
- `floor`: `assembly`*, `outside`* (crawlspace, garage, `outdoors` ...).
- `foundation_wall`: `height_ft`*, `depth_below_grade_ft`*, `thickness_in`, `material`, `length_ft`,
  `azimuth_deg`, `assembly` (optional), `interior_insulation` / `exterior_insulation`
  `{r_value_hr_ft2_f_btu, distance_to_top_ft, distance_to_bottom_ft}`. `outside` defaults to ground.
- `slab`: `exposed_perimeter_ft`*, `thickness_in` (0 = dirt floor), `perimeter_insulation`
  `{r_value_hr_ft2_f_btu, depth_ft}`, `under_slab_insulation` `{r_value_hr_ft2_f_btu, width_ft, whole_slab}`,
  `exterior_horizontal_insulation` `{r_value_hr_ft2_f_btu, width_ft, depth_below_grade_ft}`. No assembly.

**openings** (each): `id`*, `type`* (window | door | skylight), `surface`* (the wall or roof it is in),
size as `area_ft2` of ONE unit or `width_ft` and `height_ft`, and `count` (default 1).
- `window`: `glazing` (preset id) OR both `u_factor_btu_hr_ft2_f` and `shgc`; `azimuth_deg` (default: the
  wall's); `storm_window` (none | clear | low_e); `glass_layers`, `glass_type`;
  `interior_shading` `{type, coverage_frac, blinds_position}` or `{coefficient_frac}`;
  `exterior_shading` `{type, coefficient_frac}`; `insect_screen` `{location, coverage_frac}`;
  `overhang` `{depth_ft, distance_to_window_top_ft, distance_to_window_bottom_ft}` (all three required).
- `door`: `r_value_hr_ft2_f_btu`* (about 2 solid wood, 4.4 insulated steel). Glass doors are windows.
- `skylight`: `u_factor_btu_hr_ft2_f`*, `shgc`*, `azimuth_deg`, `storm_window`, `ceiling`,
  `interior_shading_coefficient_frac`, `curb` / `shaft` `{area_ft2, r_value_hr_ft2_f_btu}`.

**air**:
- `infiltration`: `method`* (blower_door | leakiness_estimate). With blower_door give ONE of
  `air_changes_per_hr_at_50pa` (ACH50), `airflow_cfm_at_50pa` (CFM50), `natural_air_changes_per_hr`,
  `leakage_area_in2`. With leakiness_estimate give `leakiness`. Optional: `test_pressure_pa`, `volume_ft3`,
  `height_ft`, `shielding_class` (1 to 5, default 4), `stories_above_grade`, `building_type`,
  `exterior_envelope_frac`, `unit_height_above_grade_ft`, `site_shielding`, `fireplace` (true/false).
- `ventilation` (each): `id`*, `type`* (supply | exhaust | balanced | erv | hrv), `airflow_cfm`*,
  `hours_per_day_hr`, `sensible_recovery_frac`, `latent_recovery_frac`. Whole-house fans only.
- `ducts` (each): `id`*, `system`* (hvac system id), `segments`*, leakage as `supply_leakage_cfm_at_25pa` and
  `return_leakage_cfm_at_25pa`, OR `supply_leakage_frac` and `return_leakage_frac` (not both kinds).
  Each segment: `type`* (supply | return), `location`* (room id, space id, or outdoors), `surface_area_ft2`
  or `share_of_ducts_frac`, and `insulation_r_value_hr_ft2_f_btu` (nominal, 0 = bare) or
  `effective_r_value_hr_ft2_f_btu`.

**equipment** (each): `id`*, `type`* (dehumidifier | other), `room`*, `sensible_heat_btu_hr`*,
`latent_heat_btu_hr` (negative = moisture removed).

**hvac**: `systems` (each): `id`*, `zone`*, `heating` (furnace | boiler | heat_pump | electric_resistance | other |
none), `cooling` (central_ac | heat_pump | mini_split | other | none), `supply_registers` (list of room ids),
`returns` (list of room ids), `heating_airflow_cfm_per_ton`, `cooling_airflow_cfm_per_ton`,
`blower_heat_btu_hr`, `piping_loss_btu_hr`. At most one heating and one cooling system per zone (normally one
entry that does both). Do not enter equipment sizes.

**scenarios** (each): `id`*, `changes`* (may be an empty list), `name`, `description`, `cost_usd`, `includes`
(ids of scenarios applied first). Each change is one of:
- `{op: set, path: "section/id/field", value: ...}`
- `{op: add, section: "openings", item: {...complete item with its own id...}}`
- `{op: remove, path: "openings/some-id"}`

Paths: `air/infiltration/air_changes_per_hr_at_50pa`, `surfaces/north-wall/assembly`,
`openings/w1/storm_window`. Layers and duct segments have no id; use their position counting from 0:
`assemblies/wall-old/layers/1`.

**extensions**: free-form object for other tools; leave out.

## Geometry rules that the validator enforces

- Window, door and skylight areas on a surface must add up to no more than the surface's `area_ft2`.
- Wall area = length x ceiling height. Give each exterior wall of each room its own surface, with
  `azimuth_deg` = the compass direction its OUTSIDE faces (0 north, 90 east, 180 south, 270 west).
- Every room should have its exterior walls, its ceiling (or roof) and its floor (or slab) unless those
  border another conditioned room. Interior partitions are left out.
- An attic needs both the ceilings below it (`inside` = room, `outside` = attic) and its roof surfaces
  (`inside` = attic). A crawlspace or unconditioned basement needs the floors above it, its foundation walls
  (`inside` = the crawlspace) and its slab or dirt floor (`inside` = the crawlspace).
- Roof area = footprint x sqrt(1 + (pitch/12)^2): x 1.118 for 6-in-12, x 1.202 for 8-in-12, x 1.414 for 12-in-12.
- `depth_below_grade_ft` cannot exceed `height_ft`.
- A window behind a porch roof: either give it an `overhang`, or make an `open_porch` space and set the
  wall's `outside` to it (the wall and its windows are then treated as fully shaded).

## Clarifications (questions writers of these files have actually had)

- **Numbers with a source.** ANY numeric field may be written `{value: N, source: "...", confidence: ...}`.
  Only `value` is required. `confidence` is `measured`, `estimated` or `default`.
- **Scenario changes** are applied in the order listed, after the scenarios named in `includes`. `set` replaces
  the whole old value (a bare number may replace a wrapped one and the other way round). To ADD INSULATION to
  an existing assembly, append a layer: `{op: add, section: "assemblies/<assembly-id>/layers", item: {...layer...}}`
  (the new layer goes on the outside end of the list), or replace a layer with
  `{op: set, path: "assemblies/<assembly-id>/layers/<position>", value: {...layer...}}`. Every surface using that
  assembly changes with it. Adding a new assembly and re-pointing surfaces with `set` also works.
- **Foundation walls** always need `area_ft2` (= length x height) as well as `height_ft` and
  `depth_below_grade_ft`. One foundation wall for the whole perimeter is fine. `rim_joist` surfaces are
  optional detail.
- **Slabs.** `exposed_perimeter_ft` is the length of slab edge along exterior walls, also for a basement
  floor deep below grade. Default thickness is 4 in.
- **Solid masonry walls** (brick, stone, block, concrete, log): set `construction` to the material, set
  `cladding: none`, and still list the masonry as a layer. `construction`, `cladding`, `roofing` and
  `roof_color` describe the surface for the solar and time-lag part of the calculation; they add no R-value,
  so the layers must carry all of it (including a shingle layer on a roof).
- **Fixed-R materials** (`air_space_closed`, `plaster_on_wood_lath` ...) may be given a `thickness_in`; it is
  recorded but the R-value does not change. A thin furred air gap is an ordinary layer, not a framed one.
- **Attics.** Gable end walls of an attic are `wall` surfaces with `inside: <attic>`. A roof's `azimuth_deg` is
  the direction its slope faces (downhill).
- **Infiltration.** `volume_ft3` is optional: the default is the sum of room floor area x ceiling height (plus
  `conditioned` spaces), which leaves out unconditioned basements, as a blower-door volume should. Defaults:
  `stories_above_grade` 1, `shielding_class` 4, `building_type` detached, `site_shielding` normal.
- **Ducts.** `supply_leakage_frac` / `return_leakage_frac` are fractions of the system airflow that leak to
  outside. `share_of_ducts_frac` is the share of that system's supply (or return) duct area in that
  location; shares of one type add up to 1 or less (the rest is taken to be inside the rooms).
- **Interior shading.** `coverage_frac` is the share of the glass area covered. `blinds_position` applies to
  blinds only.
- **Ventilation** means fans that ventilate the whole house on a schedule. Bath and kitchen exhaust fans are
  left out.

## Allowed values

<!-- BEGIN GENERATED: enums -->
| Field (where) | Allowed values |
| --- | --- |
| `daily_temp_range (location.design_conditions)` | low, medium, high |
| `type (assemblies)` | wall, roof, ceiling, floor |
| `construction (assemblies)` | wood_stud, steel_stud, double_wood_stud, sip, cmu, brick, adobe, concrete, stone, log, icf, straw_bale |
| `cladding (assemblies)` | wood, vinyl, aluminum, fiber_cement, stucco, shingle, brick, stone, other, none |
| `roofing (assemblies)` | asphalt_shingles, wood_shingles, metal, clay_tile, concrete, plastic_rubber, eps, shingles |
| `roof_color (assemblies)` | dark, medium_dark, medium, medium_light, light, white, reflective |
| `type (spaces)` | vented_attic, unvented_attic, vented_crawlspace, unvented_crawlspace, unconditioned_basement, garage, open_porch, conditioned, custom |
| `material (surfaces[foundation_wall])` | solid_concrete, double_brick, wood, concrete_block, concrete_block_solid_core, concrete_block_perlite_core, concrete_block_foam_core, concrete_block_vermiculite_core |
| `glass_type (openings[window])` | clear, tinted, reflective, tinted_reflective, low_e, low_e_low_solar, low_e_high_solar |
| `storm_window (openings[window])` | none, clear, low_e |
| `type (openings[window].interior_shading)` | dark_blinds, medium_blinds, light_blinds, dark_shades, medium_shades, light_shades, dark_curtains, medium_curtains, light_curtains |
| `blinds_position (openings[window].interior_shading)` | closed, half_open, open |
| `type (openings[window].exterior_shading)` | solar_screens, solar_film, other |
| `location (openings[window].insect_screen)` | interior, exterior |
| `storm_window (openings[skylight])` | none, clear, low_e |
| `method (air.infiltration)` | blower_door, leakiness_estimate |
| `leakiness (air.infiltration)` | very_tight, tight, average, leaky, very_leaky |
| `building_type (air.infiltration)` | detached, attached |
| `site_shielding (air.infiltration)` | normal, exposed, well_shielded |
| `type (air.ventilation)` | supply, exhaust, balanced, erv, hrv |
| `type (air.ducts.segments)` | supply, return |
| `type (equipment)` | dehumidifier, other |
| `heating (hvac.systems)` | furnace, boiler, heat_pump, electric_resistance, other, none |
| `cooling (hvac.systems)` | central_ac, heat_pump, mini_split, other, none |
<!-- END GENERATED: enums -->

## Materials (for `material` and `framing_material`)

<!-- BEGIN GENERATED: materials-compact -->
| Material id | What it is | R per inch | Fixed R | Typical thickness (in) |
| --- | --- | --- | --- | --- |
| `gypsum_board` | Gypsum board (drywall) | 0.9 |  | 0.5 |
| `plaster_on_wood_lath` | Plaster on wood lath |  | 0.4 | 0.875 |
| `plaster_on_metal_lath` | Plaster on metal lath |  | 0.23 | 0.75 |
| `wood_paneling` | Wood paneling or boards (interior) | 1.249 |  | 0.75 |
| `softwood` | Softwood lumber, boards, plywood, OSB | 1.249 |  |  |
| `board_sheathing` | Board sheathing (3/4 in, straight or diagonal) | 1.249 |  | 0.75 |
| `air_space_closed` | Closed air space (empty framed cavity) |  | 1.0 |  |
| `fiberglass_batt` | Fiberglass batt | 3.2 |  |  |
| `mineral_wool_batt` | Mineral wool batt | 4.0 |  |  |
| `cellulose_dense_pack` | Cellulose, dense-packed in a closed cavity | 3.6 |  |  |
| `cellulose_loose_fill` | Cellulose, loose fill (attic floor) | 3.5 |  |  |
| `fiberglass_loose_fill` | Fiberglass, loose fill (attic floor) | 2.5 |  |  |
| `vermiculite` | Vermiculite, loose fill | 2.2 |  |  |
| `spray_foam_closed_cell` | Spray polyurethane foam, closed cell | 6.0 |  |  |
| `spray_foam_open_cell` | Spray polyurethane foam, open cell | 3.6 |  |  |
| `rigid_foam_generic` | Rigid foam board (generic) | 4.9 |  |  |
| `xps_board` | Extruded polystyrene (XPS) board | 5.0 |  |  |
| `eps_board` | Expanded polystyrene (EPS) board | 4.0 |  |  |
| `polyiso_board` | Polyisocyanurate board, foil faced | 6.0 |  |  |
| `wood_siding` | Wood siding or clapboard | 1.408 |  | 0.75 |
| `vinyl_or_aluminum_siding` | Vinyl or aluminum siding (hollow backed) | 1.613 |  | 0.375 |
| `fiber_cement_siding` | Fiber-cement siding | 0.559 |  | 0.375 |
| `hardboard_siding` | Hardboard (Masonite) siding | 1.449 |  | 0.5 |
| `asbestos_cement_shingle` | Asbestos-cement shingle siding | 0.238 |  | 0.25 |
| `stucco` | Stucco | 0.222 |  | 1.0 |
| `brick` | Brick | 0.182 |  | 4.0 |
| `stone` | Stone | 0.08 |  | 1.0 |
| `concrete` | Concrete | 0.08 |  |  |
| `concrete_block_hollow` | Concrete block, hollow core | 0.2 |  | 8.0 |
| `straw_bale` | Straw bale | 2.4 |  |  |
| `asphalt_shingles_on_deck` | Asphalt shingles | 0.887 |  | 0.25 |
| `wood_shingles_roof` | Wood shingles or shakes | 1.408 |  | 0.5 |
| `metal_roofing` | Metal roofing |  | 0.0 | 0.02 |
| `carpet_and_pad` | Carpet with pad |  | 2.08 | 0.5 |
| `hardwood_flooring` | Hardwood flooring | 1.249 |  | 0.75 |
<!-- END GENERATED: materials-compact -->

## Glazing presets (for `glazing`)

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

An old single-pane window with a storm window is `glazing: single_clear_wood` plus `storm_window: clear`.

## Weather stations (for `weather_station_id`; write the id in quotes)

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

## Worked example

A small one-story house: two rooms, vented attic, slab on grade, furnace and air conditioner with ducts in the attic.

```yaml
# guide-example
format_version: 1.0.0
project:
  name: Example two-room house
  bedroom_count: 1
location:
  weather_station_id: "723140"
assemblies:
  - id: wall-2x4
    type: wall
    framing_frac: 0.25
    solar_absorptance_frac: 0.7
    layers:
      - {material: gypsum_board, thickness_in: 0.5}
      - {name: R-13 batt, r_value_hr_ft2_f_btu: 13, thickness_in: 3.5, framing_material: softwood}
      - {material: softwood, name: OSB sheathing, thickness_in: 0.5}
      - {material: vinyl_or_aluminum_siding}
  - id: ceiling-r30
    type: ceiling
    layers:
      - {material: gypsum_board, thickness_in: 0.5}
      - {material: cellulose_loose_fill, thickness_in: 8.5}
  - id: attic-roof
    type: roof
    roofing: asphalt_shingles
    roof_color: dark
    layers:
      - {material: softwood, name: Roof deck, thickness_in: 0.5}
      - {material: asphalt_shingles_on_deck}
zones:
  - {id: house}
rooms:
  - {id: living, name: Living room and kitchen, zone: house, floor_area_ft2: 400, ceiling_height_ft: 8}
  - {id: bedroom, name: Bedroom, zone: house, floor_area_ft2: 200, ceiling_height_ft: 8}
spaces:
  - {id: attic, type: vented_attic}
surfaces:
  # living room: 20 ft x 20 ft, exterior on south, west and north
  - {id: living-south, type: wall, inside: living, area_ft2: 160, assembly: wall-2x4, azimuth_deg: 180}
  - {id: living-west, type: wall, inside: living, area_ft2: 160, assembly: wall-2x4, azimuth_deg: 270}
  - {id: living-north, type: wall, inside: living, area_ft2: 160, assembly: wall-2x4, azimuth_deg: 0}
  - {id: living-ceiling, type: ceiling, inside: living, outside: attic, area_ft2: 400, assembly: ceiling-r30}
  - {id: living-slab, type: slab, inside: living, area_ft2: 400, exposed_perimeter_ft: 60}
  # bedroom: 10 ft x 20 ft on the east side
  - {id: bedroom-south, type: wall, inside: bedroom, area_ft2: 80, assembly: wall-2x4, azimuth_deg: 180}
  - {id: bedroom-east, type: wall, inside: bedroom, area_ft2: 160, assembly: wall-2x4, azimuth_deg: 90}
  - {id: bedroom-north, type: wall, inside: bedroom, area_ft2: 80, assembly: wall-2x4, azimuth_deg: 0}
  - {id: bedroom-ceiling, type: ceiling, inside: bedroom, outside: attic, area_ft2: 200, assembly: ceiling-r30}
  - {id: bedroom-slab, type: slab, inside: bedroom, area_ft2: 200, exposed_perimeter_ft: 40}
  # the attic's roof: 600 ft2 footprint x 1.118 (6-in-12), two slopes
  - {id: roof-south, type: roof, inside: attic, area_ft2: 335, assembly: attic-roof, azimuth_deg: 180, pitch_rise_per_12: 6}
  - {id: roof-north, type: roof, inside: attic, area_ft2: 335, assembly: attic-roof, azimuth_deg: 0, pitch_rise_per_12: 6}
openings:
  - {id: living-south-windows, type: window, surface: living-south, count: 2, width_ft: 3, height_ft: 5, glazing: double_clear_wood}
  - id: living-west-window
    type: window
    surface: living-west
    width_ft: 6
    height_ft: 5
    glazing: double_low_e_wood
    interior_shading: {type: light_blinds, coverage_frac: 1.0, blinds_position: half_open}
  - {id: front-door, type: door, surface: living-south, width_ft: 3, height_ft: 6.67, r_value_hr_ft2_f_btu: 4.4}
  - {id: bedroom-east-window, type: window, surface: bedroom-east, width_ft: 3, height_ft: 5, glazing: double_clear_wood}
air:
  infiltration:
    method: blower_door
    air_changes_per_hr_at_50pa: {value: 7, source: blower door test, confidence: measured}
  ducts:
    - id: ducts
      system: furnace-ac
      supply_leakage_frac: 0.08
      return_leakage_frac: 0.05
      segments:
        - {type: supply, location: attic, share_of_ducts_frac: 1.0, insulation_r_value_hr_ft2_f_btu: 8}
        - {type: return, location: attic, share_of_ducts_frac: 1.0, insulation_r_value_hr_ft2_f_btu: 8}
hvac:
  systems:
    - id: furnace-ac
      zone: house
      heating: furnace
      cooling: central_ac
      supply_registers: [living, bedroom]
      returns: [living]
scenarios:
  - id: tighter
    name: Air seal to 4 ACH50
    changes:
      - {op: set, path: air/infiltration/air_changes_per_hr_at_50pa, value: 4}
```

## Common mistakes

| Mistake | Correct |
| --- | --- |
| `area: 160` or `area_sqft: 160` | `area_ft2: 160` |
| `r_value: 13` | `r_value_hr_ft2_f_btu: 13` |
| `coverage_frac: 50` (percent) | `coverage_frac: 0.5` |
| `floor_area_ft2: "400 sq ft"` | `floor_area_ft2: 400` |
| `weather_station_id: 723140` (number) | `weather_station_id: "723140"` |
| `id: North Wall` | `id: north-wall` (put the readable text in `name`) |
| A room and a surface both with id `kitchen` | ids are unique file-wide: `kitchen` and `kitchen-north` |
| Windows larger than their wall | wall `area_ft2` is the gross area and must be at least the sum of its openings |
| Giving a roof `outside: outdoors` | leave `outside` off roofs |
| `inside: attic` on a ceiling | a ceiling has `inside: <room>`, `outside: <attic>` |
| An attic with ceilings but no roof surfaces | add roof surfaces with `inside: <attic>` |
| A crawlspace with floors above but no walls of its own | add a `foundation_wall` and a `slab` with `inside: <crawlspace>` |
| Listing air films, or listing layers outside-to-inside | no films; inside face first |
| A framed layer without `thickness_in` or without `framing_frac` on the assembly | give both |
| Window without direction | `azimuth_deg` on the window or its wall |
| `u_factor` only, or `shgc` only | give both, or a `glazing` preset |
| Entering furnace or AC tonnage | sizes are results, not inputs |
| Two heating (or two cooling) systems in one zone | one of each per zone; split the rooms into two zones |
| Street address or owner name | never; use the weather station only |

## Before you answer, check

1. Every `zone`, `inside`, `outside`, `assembly`, `surface`, `system`, `room`, `location` reference matches an id that exists.
2. Ids are unique across the file and lowercase.
3. Each exterior wall with windows has `azimuth_deg`.
4. Openings fit in their surfaces.
5. No field names other than those in this guide.
