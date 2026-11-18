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
- Split cavity (foam then batt in one stud bay): one framed layer per fill, consecutively; their
  thicknesses must add up to the cavity depth. Unfilled depth: a last framed layer
  `{material: air_space_closed, thickness_in: <leftover>, framing_material: softwood}`.
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
Any material can go in any layer; any insulation can fill any framed cavity.

| Material id | Type | What it is | R per inch | Fixed R | Typical thickness (in) |
| --- | --- | --- | --- | --- | --- |
| `gypsum_board` | Gypsum and plaster | Gypsum board (drywall) | 0.9 |  | 0.5 |
| `plaster_on_wood_lath` | Gypsum and plaster | Plaster on wood lath |  | 0.51 | 0.875 |
| `plaster_on_metal_lath` | Gypsum and plaster | Plaster on metal lath |  | 0.23 | 0.75 |
| `wood_paneling` | Wood | Wood paneling or boards (interior) | 1.249 |  | 0.75 |
| `softwood` | Wood | Softwood lumber, boards, plywood, OSB | 1.249 |  |  |
| `board_sheathing` | Wood | Board sheathing (3/4 in, straight or diagonal) | 1.249 |  | 0.75 |
| `fiberglass_batt` | Batts and blankets | Fiberglass batt | 3.15 |  |  |
| `mineral_wool_batt` | Batts and blankets | Mineral wool batt | 4.2 |  |  |
| `cellulose_dense_pack` | Loose fill and blown-in | Cellulose, dense-packed in a closed cavity | 3.12 |  |  |
| `cellulose_loose_fill` | Loose fill and blown-in | Cellulose, loose fill (attic floor) | 3.5 |  |  |
| `fiberglass_loose_fill` | Loose fill and blown-in | Fiberglass, loose fill (attic floor) | 2.5 |  |  |
| `vermiculite` | Loose fill and blown-in | Vermiculite, loose fill | 2.2 |  |  |
| `spray_foam_closed_cell` | Spray foam | Spray polyurethane foam, closed cell | 5.0 |  |  |
| `spray_foam_open_cell` | Spray foam | Spray polyurethane foam, open cell | 3.33 |  |  |
| `rigid_foam_generic` | Rigid boards | Rigid foam board (generic) | 4.9 |  |  |
| `xps_board` | Rigid boards | Extruded polystyrene (XPS) board | 5.0 |  |  |
| `eps_board` | Rigid boards | Expanded polystyrene (EPS) board | 3.9 |  |  |
| `polyiso_board` | Rigid boards | Polyisocyanurate board | 5.9 |  |  |
| `mineral_wool_board` | Rigid boards | Mineral wool board (rigid, stone wool) | 4.2 |  | 1.5 |
| `straw_bale` | Straw and other natural fiber | Straw bale | 2.4 |  |  |
| `brick` | Masonry and concrete | Brick | 0.182 |  | 4.0 |
| `stone` | Masonry and concrete | Stone | 0.08 |  | 1.0 |
| `concrete` | Masonry and concrete | Concrete | 0.08 |  |  |
| `concrete_block_hollow` | Masonry and concrete | Concrete block, hollow core | 0.2 |  | 8.0 |
| `wood_siding` | Cladding and siding | Wood siding or clapboard | 1.408 |  | 0.75 |
| `vinyl_or_aluminum_siding` | Cladding and siding | Vinyl or aluminum siding (hollow backed) | 1.613 |  | 0.375 |
| `fiber_cement_siding` | Cladding and siding | Fiber-cement siding | 0.559 |  | 0.375 |
| `hardboard_siding` | Cladding and siding | Hardboard (Masonite) siding | 1.449 |  | 0.5 |
| `asbestos_cement_shingle` | Cladding and siding | Asbestos-cement shingle siding | 0.238 |  | 0.25 |
| `stucco` | Cladding and siding | Stucco | 0.222 |  | 1.0 |
| `asphalt_shingles_on_deck` | Roofing | Asphalt shingles | 0.887 |  | 0.25 |
| `wood_shingles_roof` | Roofing | Wood shingles or shakes |  | 0.94 | 0.75 |
| `metal_roofing` | Roofing | Metal roofing |  | 0.0 | 0.02 |
| `carpet_and_pad` | Flooring | Carpet with pad |  | 2.08 | 0.5 |
| `hardwood_flooring` | Flooring | Hardwood flooring | 1.249 |  | 0.75 |
| `air_space_closed` | Air spaces | Closed air space (empty framed cavity) |  | 1.0 |  |
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

Pick the listed station nearest the house, in the same climate (same side of mountains, similar elevation and
distance from the coast). Each entry is `id name`. If none is suitable, give `design_conditions` instead.

<!-- BEGIN GENERATED: stations-compact -->
- **AK**: 704540 Adak Nas; 701718 Ambler; 701625 Anaktuvuk Pass; 702720 Anchorage Elmendorf; 702730 Anchorage Intl AP; 702735 Anchorage Merrill Field; 702320 Aniak Airport; 703980 Annette Island AP; 702075 Anvik; 700260 Barrow W Post W Rogers Arpt  N; 702190 Bethel Airport; 701740 Bettles Field; 702670 Big Delta Allen Aaf; 702986 Big River Lake; 702746 Birchwood; 702606 Chulitna; 703160 Cold Bay Arpt; 702960 Cordova; 700637 Deadhorse; 703210 Dillingham  Amos; 704890 Dutch Harbor; 702084 Emmonak; 702650 Fairbanks Eielson A; 702610 Fairbanks Intl Arpt; 701940 Fort Yukon; 702040 Gambell; 702710 Gulkana Intermediate Field; 703670 Gustavus; 702495 Hayes River; 702647 Healy River Airport; 703410 Homer Arpt; 702607 Hoonah; 702186 Hooper Bay; 702225 Huslia; 703400 Iliamna Arpt; 703810 Juneau Intl Arpt; 703855 Kake Seaplane Base; 702590 Kenai Municipal AP; 703950 Ketchikan Intl AP; 703260 King Salmon Arpt; 703500 Kodiak Airport; 701330 Kotzebue Ralph Wein Memorial; 702725 Lake Hood Seaplane; 702310 Mcgrath Arpt; 702185 Mekoryuk; 703430 Middleton Island Aut; 702460 Minchumina; 702600 Nenana Municipal AP; 702000 Nome Municipal Arpt; 702910 Northway Airport; 702740 Palmer Municipal; 703860 Petersburg; 701043 Point Hope  Awos; 703330 Port Heiden; 702005 Saint Mary S  Awos; 703165 Sand Point; 702035 Savoonga; 700197 Selawik; 702770 Seward; 704140 Shemya AFB; 701195 Shishmaref  Awos; 703710 Sitka Japonski AP; 703620 Skagway Airport; 703407 Sleetmute; 702595 Soldotna; 703080 St Paul Island Arpt; 702510 Talkeetna State Arpt; 701780 Tanana Ralph M Calhoun Mem AP; 703606 Togiac Village Awos; 702070 Unalakleet Field; 702756 Valdez Pioneer Fiel; 702750 Valdez Wso; 702757 Whittier; 703870 Wrangell; 703610 Yakutat State Arpt
- **AL**: 722287 Anniston Metropolitan AP; 722284 Auburn Opelika APt; 722280 Birmingham Municipal AP; 722269 Cairns Field Fort Rucker; 722268 Dothan Municipal AP; 722285 Gadsen Muni  Awos; 723230 Huntsville Intl Jones Field; 722265 Maxwell AFB; 722235 Mobile Downtown AP; 722230 Mobile Regional AP; 722260 Montgomery Dannelly Field; 723235 Muscle Shoals Regional AP; 722267 Troy Af; 722286 Tuscaloosa Municipal AP
- **AR**: 723448 Batesville  Awos; 723444 Bentonville  Awos; 723419 El Dorado Goodwin Field; 723445 Fayetteville Drake Field; 723447 Flippin  Awos; 723440 Fort Smith Regional AP; 723446 Harrison Faa AP; 723407 Jonesboro Muni; 723405 Little Rock AFB; 723403 Little Rock Adams Field; 723415 Memorial Fld; 723417 Pine Bluff Faa AP; 723449 Rogers  Awos; 723443 Siloam Spring Awos; 723434 Springdale Muni; 723416 Stuttgart  Awos; 723418 Texarkana Webb Field; 723406 Walnut Ridge  Awos
- **AZ**: 722748 Casa Granda  Awos; 722745 Davis Monthan AFB; 722784 Deer Valley Phoenix; 722735 Douglas Bisbee Douglas Intl A; 723755 Flagstaff Pulliam Arpt; 723783 Grand Canyon Natl P; 723700 Kingman  Amos; 722785 Luke AFB; 723710 Page Muni  Amos; 722780 Phoenix Sky Harbor Intl AP; 723723 Prescott Love Field; 722747 Safford  Amos; 722789 Scottsdale Muni; 723747 Show Low Municipal; 722740 Tucson International AP; 723740 Winslow Municipal AP; 722800 Yuma Intl Arpt; 699604 Yuma Mcas
- **CA**: 725958 Alturas; 725945 Arcata Airport; 723840 Bakersfield Meadows Field; 724837 Beale AFB; 724800 Bishop Airport; 725845 Blue Canyon AP; 747188 Blythe Riverside Co Arpt; 722880 Burbank Glendale Passadena AP; 723926 Camarillo  Awos; 722926 Camp Pendleton Mcas; 722927 Carlsbad Palomar; 746120 China Lake Naf; 722899 Chino Airport; 722904 Chula Vista Brown Field Naas; 724936 Concord Concord Buchanan Fiel; 725946 Crescent City Faa Ai; 723815 Daggett Barstow Daggett AP; 723810 Edwards AFB; 723890 Fresno Yosemite Intl AP; 722976 Fullerton Municipal; 724935 Hayward Air Term; 747185 Imperial; 722956 Jack Northrop Fld H; 723816 Lancaster Gen Wm Fox Field; 747020 Lemoore Reeves Nas; 724927 Livermore Municipal; 722895 Lompoc  Awos; 722970 Long Beach Daugherty Fld; 722950 Los Angeles Intl Arpt; 722860 March AFB; 724815 Merced Macready Fld; 724926 Modesto City County AP; 725955 Montague Siskiyou County AP; 724915 Monterey Naf; 745090 Mountain View Moffett Fld Nas; 724955 Napa Co  Airport; 723805 Needles Airport; 724930 Oakland Metropolitan Arpt; 723927 Oxnard Airport; 722868 Palm Springs Intl; 747187 Palm Springs Thermal AP; 723820 Palmdale Airport; 723965 Paso Robles Municipal Arpt; 723910 Point Mugu Nf; 723895 Porterville  Awos; 725910 Red Bluff Municipal Arpt; 725920 Redding Municipal Arpt; 722869 Riverside Muni; 724830 Sacramento Executive Arpt; 724839 Sacramento Metropolitan AP; 724917 Salinas Municipal AP; 722900 San Diego Lindbergh Field; 722930 San Diego Miramar Nas; 722903 San Diego Montgomer; 722906 San Diego North Island Nas; 724940 San Francisco Intl AP; 724945 San Jose Intl AP; 722897 San Luis Co Rgnl; 723830 Sandberg; 722977 Santa Ana John Wayne AP; 723925 Santa Barbara Municipal AP; 723940 Santa Maria Public Arpt; 722885 Santa Monica Muni; 724957 Santa Rosa  Awos; 725847 South Lake Tahoe; 724920 Stockton Metropolitan Arpt; 745160 Travis Field AFB; 725846 Truckee Tahoe; 690150 Twentynine Palms; 725905 Ukiah Municipal AP; 722886 Van Nuys Airport; 723896 Visalia Muni  Awos; 724838 Yuba Co
- **CO**: 724698 Akron Washington Co AP; 724620 Alamosa San Luis Valley Rgnl; 724676 Aspen Pitkin Co Sar; 724695 Aurora Buckley Field Angb; 724699 Broomfield Jeffco  Boulder   S; 724660 Colorado Springs Muni AP; 724767 Cortez Montezuma Co; 725700 Craig Moffat; 724666 Denver Centennial  Golden   Nr; 725650 Denver Intl AP; 724625 Durango La Plata Co; 724675 Eagle County AP; 724769 Fort Collins  Awos; 724760 Grand Junction Walker Field; 724768 Greeley Weld  Awos; 724677 Gunnison Co   Awos; 725715 Hayden Yampa  Awos; 724635 La Junta Municipal AP; 724636 Lamar Municipal; 724673 Leadville Lake Co; 724665 Limon; 724765 Montrose Co  Arpt; 724640 Pueblo Memorial AP; 725717 Rifle Garfield Rgnl; 724645 Trinidad Las Animas County AP
- **CT**: 725040 Bridgeport Sikorsky Memorial; 725086 Danbury Municipal; 725046 Groton New London AP; 725080 Hartford Bradley Intl AP; 725087 Hartford Brainard Fd; 725045 New Haven Tweed Airport; 725029 Oxford  Awos
- **DE**: 724088 Dover AFB; 724089 Wilmington New Castle Cnty AP
- **FL**: 722215 Crestview Bob Sikes AP; 722056 Daytona Beach Intl AP; 722039 Fort Lauderdale; 722025 Fort Lauderdale Hollywood Int; 722106 Fort Myers Page Field; 722146 Gainesville Regional AP; 722026 Homestead AFB; 722068 Jacksonville Craig; 722060 Jacksonville Intl Arpt; 722065 Jacksonville Nas; 722010 Key West Intl Arpt; 722015 Key West Nas; 722119 Lakeland Linder Rgn; 747880 Macdill AFB; 722016 Marathon Airport; 722066 Mayport Ns; 722040 Melbourne Regional AP; 722020 Miami Intl AP; 722029 Miami Kendall Tamia; 722024 Miami Opa Locka; 722038 Naples Municipal; 747946 Nasa Shuttle Fclty; 722055 Ocala Muni  Awos; 722053 Orlando Executive AP; 722050 Orlando Intl Arpt; 722057 Orlando Sanford Airport; 722245 Panama City Bay Co; 722225 Pensacola Forest Sherman Nas; 722223 Pensacola Regional AP; 722115 Sarasota Bradenton; 722108 Southwest Florida I; 722103 St Lucie Co Intl; 722104 St Petersburg Albert Whitted; 722116 St Petersburg Clear; 722140 Tallahassee Regional AP  Isis; 722110 Tampa International AP; 747750 Tyndall AFB; 722210 Valparaiso Elgin AFB; 747770 Valparaiso Hurlburt; 722045 Vero Beach Municipal Arpt; 722030 West Palm Beach Intl Arpt; 722226 Whiting Field Naas
- **GA**: 722160 Albany Dougherty County AP; 722135 Alma Bacon County AP; 723110 Athens Ben Epps AP; 722190 Atlanta Hartsfield Intl AP; 722180 Augusta Bush Field; 722136 Brunswick Golden Is; 722137 Brunswick Malcolm Mckinnon AP; 722255 Columbus Metropolitan Arpt; 722196 Dekalb Peachtree; 722250 Fort Benning Lawson; 722195 Fulton Co Arpt Brow; 747804 Hunter Aaf; 722170 Macon Middle Ga Regional AP; 722270 Marietta Dobbins AFB; 747810 Moody AFB Valdosta; 723200 Rome R B Russell AP; 722070 Savannah Intl AP; 722166 Valdosta Wb Airport; 722175 Warner Robins AFB
- **GU**: 912180 Andersen AFB; 912120 Guam Wfo
- **HI**: 911780 Barbers Point Nas; 912850 Hilo International AP; 911820 Honolulu Intl Arpt; 911900 Kahului Airport; 911760 Kaneohe Bay Mcas; 911904 Kapalua; 911975 Kona Intl At Keahol; 911905 Lanai; 911650 Lihue Airport; 911860 Molokai  Amos
- **IA**: 725457 Algona; 725453 Atlantic; 725486 Boone Muni; 725455 Burlington Municipal AP; 725450 Cedar Rapids Municipal AP; 725469 Chariton; 725463 Charles City; 725479 Clarinda; 725473 Clinton Muni  Awos; 725497 Council Bluffs; 725474 Creston; 725476 Decorah; 725477 Denison; 725460 Des Moines Intl AP; 725470 Dubuque Regional AP; 726499 Estherville Muni; 726498 Fair Field; 725490 Fort Dodge  Awos; 725483 Fort Madison; 725456 Keokuk Muni; 725493 Knoxville; 725484 Le Mars; 725485 Mason City Municipal Arpt; 725475 Monticello Muni; 725487 Muscatine; 725464 Newton Muni; 725488 Oelwen; 725489 Orange City; 725465 Ottumwa Industrial AP; 725494 Red Oak; 725495 Sheldon; 725467 Shenandoah Muni; 725570 Sioux City Sioux Gateway AP; 726500 Spencer; 725496 Storm Lake; 725454 Washington; 725480 Waterloo Municipal AP; 725478 Webster City
- **ID**: 726810 Boise Air Terminal  Uo; 725867 Burley Municipal Arpt; 726813 Caldwell  Awos; 727834 Coeur D Alene Awos; 725865 Hailey Friedman Mem; 725785 Idaho Falls Fanning Field; 725866 Joslin Fld Magic Va  Twin Fall; 727830 Lewiston Nez Perce Cnty AP; 725786 Malad City; 726815 Mountain Home AFB; 725780 Pocatello Regional AP; 726865 Salmon Lemhi  Awos; 725868 Soda Springs Tigert
- **IL**: 744655 Aurora Municipal; 724338 Belleville Scott AFB; 725314 Cahokia St  Louis; 724397 Central Illinois Rg; 725340 Chicago Midway AP; 725300 Chicago Ohare Intl AP; 725347 Chicago Waukegan; 725316 Decatur; 724339 Marion Regional; 725440 Moline Quad City Intl AP; 724335 Mount Vernon  Awos; 725320 Peoria Greater Peoria AP; 724396 Quincy Muni Baldwin Fld; 725430 Rockford Greater Rockford AP; 724336 Southern Illinois; 724390 Springfield Capital AP; 725326 Sterling Rockfalls; 725315 Univ Of Illinois Wi  Bondville; 725305 W  Chicago Du Page
- **IN**: 725336 Delaware Co Johnson; 724320 Evansville Regional AP; 725330 Fort Wayne Intl AP; 725335 Grissom Arb; 724365 Huntingburg; 724380 Indianapolis Intl AP; 724386 Lafayette Purdue Univ AP; 724375 Monroe Co; 725350 South Bend Michiana Rgnl AP; 724373 Terre Haute Hulman Regional A
- **KS**: 724507 Chanute Martin Johnson AP; 724580 Concordia Blosser Muni AP; 724510 Dodge City Regional AP; 724556 Emporia Municipal AP; 724550 Fort Riley Marshall Aaf; 724515 Garden City Municipal AP; 724650 Goodland Renner Field; 724517 Great Bend  Awos; 724518 Hays Muni  Awos; 724655 Hill City Municipal AP; 724506 Hutchinson Municipal AP; 724516 Liberal Muni; 724555 Manhattan Rgnl; 724505 Mcconnell AFB; 724509 Newton  Awos; 724468 Olathe Johnson Co; 724475 Olathe Johnson Co Industrial; 724585 Russell Municipal AP; 724586 Salina Municipal AP; 724565 Topeka Forbes Field; 724560 Topeka Municipal AP; 724504 Wichita Col  Jabara; 724500 Wichita Mid Continent AP
- **KY**: 746716 Bowling Green Warren Co AP; 724210 Cincinnati Northern Ky AP; 746710 Fort Campbell Aaf; 724240 Fort Knox Godman Aaf; 724238 Henderson City; 724236 Jackson Julian Carroll AP; 724220 Lexington Bluegrass AP; 724243 London Corbin AP; 724235 Louisville Bowman Field; 724230 Louisville Standiford Field; 724350 Paducah Barkley Regional AP; 724354 Somerset Awos
- **LA**: 722487 Alexandria Esler Regional AP; 722485 Barksdale AFB; 722317 Baton Rouge Ryan Arpt; 747540 England AFB; 722390 Fort Polk Aaf; 722406 Houma Terrebonne; 722405 Lafayette Regional AP; 722400 Lake Charles Regional Arpt; 722404 Lake Charles Wb Airp; 722486 Monroe Regional AP; 722314 New Iberia Naas; 722316 New Orleans Alvin Callender F; 722310 New Orleans Intl Arpt; 722315 New Orleans Lakefront AP; 722329 Patterson Memorial; 722484 Shreveport Downtown; 722480 Shreveport Regional Arpt
- **MA**: 725067 Barnstable Muni Boa; 725088 Beverly Muni; 725090 Boston Logan Intl Arpt; 744910 Chicopee Falls Westo; 744904 Lawrence Muni; 725066 Marthas Vineyard; 725063 Nantucket Memorial AP; 725065 New Bedford Rgnl; 725075 North Adams; 725098 Norwood Memorial; 725060 Otis Angb; 725064 Plymouth Municipal; 725073 Provincetown  Awos; 744915 Westfield Barnes Muni AP; 725095 Worchester Regional Arpt
- **MD**: 745940 Andrews AFB; 724060 Baltimore Blt Washngtn Intl; 724066 Hagerstown Rgnl Ric; 724040 Patuxent River Nas; 724045 Salisbury Wicomico Co AP
- **ME**: 726184 Auburn Lewiston; 726185 Augusta Airport; 726088 Bangor International AP; 726077 Bar Harbor  Awos; 727120 Caribou Municipal Arpt; 727033 Houlton Intl Arpt; 726196 Millinocket Municipal AP; 743920 Naval Air Station; 726083 Northern Aroostook; 726060 Portland Intl Jetport; 727130 Presque Isle Municip; 726079 Rockland Knox Awos; 726064 Sanford Muni  Awos; 726073 Waterville  Awos; 727135 Wiscasset
- **MI**: 726390 Alpena County Regional AP; 725374 Ann Arbor Municipal; 725396 Battle Creek Kellogg AP; 726355 Benton Harbor Ross; 726384 Cadillac Wexford Co AP; 727344 Chippewa Co Intl; 725375 Detroit City Airport; 725370 Detroit Metropolitan Arpt; 725376 Detroit Willow Run AP; 726480 Escanaba  Awos; 726370 Flint Bishop Intl Arpt; 726350 Grand Rapids Kent County Int; 727440 Hancock Houghton Co AP; 726380 Houghton Lake Roscommon Co Ar; 725378 Howell; 727437 Iron Mountain Ford; 727445 Ironwood  Awos; 725395 Jackson Reynolds Field; 726357 Kalamazoo Battle Cr; 725390 Lansing Capital City Arpt; 726385 Manistee  Awos; 726487 Menominee  Awos; 725377 Mount Clemens Selfridge Fld; 726360 Muskegon County Arpt; 726375 Oakland Co Intl; 726395 Oscoda Wurtsmith AFB; 727347 Pellston Emmet County AP; 726379 Saginaw Tri City Intl AP; 727340 Sault Ste Marie Sanderson Fie; 725384 St Clair County Int; 726387 Traverse City Cherry Capital
- **MN**: 727504 Aitkin Ndb Awos; 726589 Albert Lea  Awos; 726557 Alexandria Municipal AP; 727566 Austin Muni; 727476 Baudette International AP; 727550 Bemidji Municipal; 727507 Benson Muni; 726555 Brainerd Wieland; 727503 Cambridge Muni; 726558 Cloquet  Awos; 727473 Crane Lake  Awos; 727452 Crookston Muni Fld; 727457 Detroit Lakes Awos; 727450 Duluth International Arpt; 727459 Ely Muni; 727474 Eveleth Muni  Awos; 726586 Fairmont Muni Awos; 726563 Faribault Muni Awos; 726560 Fergus Falls Awos; 726579 Flying Cloud; 727505 Fosston Awos; 726547 Glenwood  Asos; 727458 Grand Rapids Awos; 727478 Hallock; 727455 Hibbing Chisholm Hibbing AP; 726569 Hutchinson  Awos; 727470 International Falls Intl AP; 726583 Litchfield Muni; 726578 Little Falls  Awos; 726585 Mankato Awos; 726559 Marshall Ryan Awos; 726575 Minneapolis Crystal; 726580 Minneapolis St Paul Intl Arp; 727475 Mora Muni  Awos; 726565 Morris Muni  Awos; 726567 New Ulm Muni  Awos; 726544 Orr; 726568 Owatonna  Awos; 727453 Park Rapids Municipal AP; 726566 Pipestone  Awos; 726564 Red Wing; 726556 Redwood Falls Muni; 726440 Rochester International Arpt; 727477 Roseau Muni  Awos; 727556 Silver Bay; 726603 South St Paul Muni; 726550 St Cloud Regional Arpt; 726584 St Paul Downtown AP; 727555 Thief River Awos; 727444 Two Harbors; 727533 Wheaton Ndb  Awos; 726576 Willmar; 726588 Winona Muni  Awos; 726587 Worthington  Awos
- **MO**: 723489 Cape Girardeau Municipal AP; 724450 Columbia Regional Airport; 724454 Farmington; 724457 Ft Lnrd Wd Aaf; 724458 Jefferson City Mem; 723495 Joplin Municipal AP; 724459 Kaiser Mem  Awos; 724463 Kansas City Downtown AP; 724460 Kansas City Intl Arpt; 724455 Kirksville Regional AP; 723300 Poplar Bluff Amos; 724400 Springfield Regional Arpt; 724490 St Joseph Rosecrans Memorial; 724340 St Louis Lambert Intl Arpt; 724345 St Louis Spirit Of St Louis A; 724456 Vichy Rolla Natl Arpt; 724467 Whiteman AFB
- **MS**: 723306 Columbus AFB; 723307 Golden Tri Awos; 722356 Greenville Municipal; 722359 Greenwood Leflore Arpt; 747685 Gulfport Biloxi Int; 722348 Hattiesburg Laurel; 722350 Jackson International AP; 747686 Keesler AFB; 722358 Mccomb Pike County AP; 722340 Meridian Key Field; 722345 Meridian Naas; 722357 Natchez Hardy Awos; 723320 Tupelo C D Lemons Arpt
- **MT**: 726770 Billings Logan Intl Arpt; 726797 Bozeman Gallatin Field; 726785 Butte Bert Mooney Arpt; 727796 Cut Bank Muni AP; 727680 Glasgow Intl Arpt; 726676 Glendive Awos; 727750 Great Falls Intl Arpt; 727770 Havre City County AP; 727720 Helena Regional Airport; 727790 Kalispell Glacier Pk Intl Ar; 726776 Lewistown Municipal Arpt; 726798 Livingston Mission Field; 742300 Miles City Municipal Arpt; 727730 Missoula International AP; 727687 Sidney Richland; 727686 Wolf Point Intl  Fort Peck   S
- **NC**: 723150 Asheville Regional Arpt; 723040 Cape Hatteras Nws Bldg; 723140 Charlotte Douglas Intl Arpt; 723090 Cherry Point Mcas; 723046 Dare Co Rgnl; 746943 Elizabeth City Coast Guard Ai; 723030 Fayetteville Pope AFB; 723035 Fayetteville Rgnl G; 746930 Fort Bragg Simmons Aaf; 723066 Goldsboro Seymour Johnson AFB; 723170 Greensboro Piedmont Triad Int; 723145 Hickory Regional AP; 723069 Jacksonville  Awos; 723067 Kinston Stallings AFB; 723095 New Bern Craven Co Regl AP; 723096 New River Mcaf; 723065 Pitt Greenville Arp; 723060 Raleigh Durham International; 723068 Rocky Mount Wilson; 723143 Southern Pines Awos; 723013 Wilmington International Arpt; 723193 Winston Salem Reynolds AP
- **ND**: 727640 Bismarck Municipal Arpt  Isis; 727573 Devils Lake Awos; 727645 Dickinson Municipal AP; 727530 Fargo Hector International AP; 727575 Grand Forks Af; 727576 Grand Forks International AP; 727535 Jamestown Municipal Arpt; 727675 Minot AFB; 727676 Minot Faa AP; 727670 Williston Sloulin Intl AP
- **NE**: 725556 Ainsworth Municipal; 725635 Alliance Municipal; 725515 Beatrice Municipal; 725540 Bellevue Offutt AFB; 725628 Brewster Field Arpt; 725555 Broken Bow Muni; 725636 Chadron Municipal AP; 725565 Columbus Muni; 725533 Falls City Brenner; 725564 Fremont Muni Arpt; 725520 Grand Island Central Ne Regio; 725525 Hastings Municipal; 725626 Imperial Faa AP; 725526 Kearney Muni  Awos; 725510 Lincoln Municipal Arpt; 725625 Mccook Municipal; 725560 Norfolk Karl Stefan Mem Arpt; 725620 North Platte Regional AP; 725566 O Neill Baker Field; 725500 Omaha Eppley Airfield; 725530 Omaha Wsfo; 725524 Ord Sharp Field; 725660 Scottsbluff W B Heilig Field; 725610 Sidney Municipal AP; 725527 Tekamah  Asos; 725670 Valentine Miller Field
- **NH**: 726160 Berlin Municipal; 726050 Concord Municipal Arpt; 726165 Dillant Hopkins; 726155 Laconia Muni  Awos; 726116 Lebanon Municipal; 743945 Manchester Airport; 726130 Mount Washington; 726055 Pease Intl Tradepor
- **NJ**: 724070 Atlantic City Intl AP; 724084 Belmar Asc; 724094 Caldwell Essex Co; 745966 Cape May Co; 724096 Mcguire AFB; 724075 Millville Municipal AP; 725020 Newark International Arpt; 725025 Teterboro Airport; 724095 Trenton Mercer County AP
- **NM**: 723650 Albuquerque Intl Arpt  Isis; 722687 Carlsbad Cavern City Air Term; 723600 Clayton Municipal Airpark; 722686 Clovis Cannon AFB; 722689 Clovis Muni   Awos; 722725 Deming Muni; 723658 Farmington Four Corners Regl; 723627 Gallup Sen Clarke Fld; 747320 Holloman AFB; 722695 Las Cruces Intl; 723677 Las Vegas Municipal Arpt; 722680 Roswell Industrial Air Park; 723656 Sata Fe County Municipal AP; 722683 Sierra Blanca Rgnl; 723663 Taos Muni APt Awos; 722710 Truth Or Consequences Muni AP; 723676 Tucumcari Faa AP
- **NV**: 725825 Elko Municipal Arpt; 724860 Ely Yelland Field; 724885 Fallon Naas; 723860 Las Vegas Mccarran Intl AP; 725805 Lovelock Derby Field; 723870 Mercury Desert Rock AP  Surfra; 723865 Nellis AFB; 724880 Reno Tahoe International AP; 724855 Tonopah Airport; 725830 Winnemucca Municipal Arpt
- **NY**: 726228 Adirondack Rgnl; 725180 Albany County AP; 725150 Binghamton Edwin A Link Field; 725280 Buffalo Niagara Intl AP; 725156 Elmira Corning Regional AP; 743700 Fort Drum Wheeler S; 725185 Glens Falls AP; 725035 Islip Long Isl Macarthur AP; 725235 Jamestown  Awos; 726223 Massena AP; 725145 Monticello Awos; 725033 New York Central Prk Obs Belv; 744860 New York J F Kennedy Intl Ar; 725030 New York Laguardia Arpt; 725287 Niagara Falls Af; 725036 Poughkeepsie Dutchess Co AP; 744864 Republic; 725290 Rochester Greater Rochester I; 725038 Stewart Field; 725190 Syracuse Hancock Intl Arpt; 725197 Utica Oneida County AP; 726227 Watertown AP; 744865 Westhampton Gabreski AP; 725037 White Plains Westchester Co A
- **OH**: 725210 Akron Akron Canton Reg AP; 725245 Burke Lakefront; 724297 Cincinnati Municipal AP Lunki; 725240 Cleveland Hopkins Intl AP; 724280 Columbus Port Columbus Intl A; 724290 Dayton International Airport; 745700 Dayton Wright Patterson AFB; 725366 Findlay Airport; 725246 Mansfield Lahm Municipal Arpt; 724288 Ohio State Universi; 725360 Toledo Express Airport; 725250 Youngstown Regional Airport; 724286 Zanesville Municipal AP
- **OK**: 723520 Altus AFB; 723565 Bartlesville Philli; 723526 Clinton Sherman; 723550 Fort Sill Post Field Af; 723527 Gage Airport; 723525 Hobart Municipal AP; 723575 Lawton Municipal; 723566 Mcalester Municipal AP; 723540 Oklahoma City Tinker AFB; 723544 Oklahoma City Wiley; 723530 Oklahoma City Will Rogers Wor; 723546 Ponca City Municipal AP  Sgp; 723545 Stillwater Rgnl; 723560 Tulsa International Airport; 723535 Vance AFB
- **OR**: 727910 Astoria Regional Airport; 726959 Aurora State; 726886 Baker Municipal AP; 726830 Burns Municipal Arpt  Uo; 726945 Corvallis Muni; 726930 Eugene Mahlon Sweet Arpt  Uo; 725895 Klamath Falls Intl AP  Uo; 726884 La Grande Muni AP; 725976 Lakeview  Awos; 725970 Medford Rogue Valley Intl AP; 726917 North Bend Muni Airport; 726880 Pendleton E Or Regional AP; 726986 Portland Hillsboro; 726980 Portland International AP; 726985 Portland Troutdale; 726835 Redmond Roberts Field; 726904 Roseburg Regional AP; 726940 Salem Mcnary Field; 725975 Sexton Summit
- **PA**: 725170 Allentown Lehigh Valley Intl; 725126 Altoona Blair Co Arpt; 725266 Bradford Regional AP; 725124 Butler Co   Awos; 725125 Dubois Faa AP; 725260 Erie International AP; 725267 Franklin; 725118 Harrisburg Capital City Arpt; 725127 Johnstown Cambria County AP; 725116 Lancaster; 725115 Middletown Harrisburg Intl AP; 724080 Philadelphia International AP; 724085 Philadelphia Ne Philadelphia; 725205 Pittsburgh Allegheny Co AP; 725200 Pittsburgh International AP; 725103 Reading Spaatz Field; 725128 State College  Penn State   Su; 725117 Washington  Awos; 725130 Wilkes Barre Scranton Intl AP; 725140 Williamsport Regional AP; 724086 Willow Grove Nas
- **PR**: 785140 Aquadilla Borinquen; 785145 Eugenio Maria De Ho; 785203 Mercedita; 785350 Roosevelt Roads; 785260 San Juan Intl Arpt; 785263 San Juan L M Marin Intl AP
- **RI**: 725058 Block Island State Arpt; 725054 Pawtucket  Awos; 725070 Providence T F Green State Ar
- **SC**: 723125 Anderson County AP; 722085 Beaufort Mcas; 722080 Charleston Intl Arpt; 723100 Columbia Metro Arpt; 723106 Florence Regional AP; 723119 Greenville Downtown AP; 723120 Greer Greenvl Spartanbrg AP; 747910 Myrtle Beach AFB; 747915 North Myrtle Beach Grand Stra; 747900 Sumter Shaw AFB
- **SD**: 726590 Aberdeen Regional Arpt; 726515 Brookings  Awos; 726525 Chan Gurney Muni; 726625 Ellsworth AFB; 726540 Huron Regional Arpt; 726545 Mitchell  Awos; 726685 Mobridge; 726686 Pierre Municipal AP; 726620 Rapid City Regional Arpt; 726510 Sioux Falls Foss Field; 726546 Watertown Municipal AP
- **TN**: 723183 Bristol Tri City Airport; 723240 Chattanooga Lovell Field AP; 723265 Crossville Memorial AP; 723347 Dyersburg Municipal AP; 723346 Jackson Mckellar Sipes Regl A; 723260 Knoxville Mcghee Tyson AP; 723340 Memphis International AP; 723270 Nashville International AP
- **TX**: 690190 Abilene Dyess AFB; 722660 Abilene Regional AP  Ut; 722517 Alice Intl AP; 723630 Amarillo International AP  Can; 722540 Austin Mueller Municipal AP  U; 722500 Brownsville S Padre Isl Intl; 722544 Camp Mabry; 723604 Childress Municipal AP; 722445 College Station Easterwood Fl; 722510 Corpus Christi Intl Arpt  Ut; 722515 Corpus Christi Nas; 722526 Cotulla Faa AP; 722587 Cox Fld; 722636 Dalhart Municipal AP; 722598 Dallas Addison Arpt; 722590 Dallas Fort Worth Intl AP; 722583 Dallas Love Field; 722599 Dallas Redbird Arpt; 722610 Del Rio  Ut; 722615 Del Rio Laughlin AFB; 722577 Draughon Miller Cen; 722700 El Paso International AP  Ut; 722570 Fort Hood; 722594 Fort Worth Alliance; 722596 Fort Worth Meacham; 722595 Fort Worth Nas; 722420 Galveston Scholes; 722547 Georgetown  Awos; 722588 Greenville Majors; 722505 Harlingen Rio Grande Valley I; 722533 Hondo Municipal AP; 722430 Houston Bush Intercontinental; 722429 Houston D W  Hooks; 722436 Houston Ellington AFB  Clear L; 722435 Houston William P Hobby AP; 722575 Killeen Muni  Awos; 722516 Kingsville; 722520 Laredo Intl AP  Ut; 722470 Longview Gregg County AP  Over; 722670 Lubbock International AP; 722446 Lufkin Angelina Co; 722640 Marfa AP; 722563 Mc Gregor  Awos; 722506 Mcallen Miller Intl AP  Edinbu; 722650 Midland International AP; 722597 Mineral Wells Municipal AP; 722499 Nacogdoches  Awos; 722555 Palacios Municipal AP; 722410 Port Arthur Jefferson County; 722536 Randolph AFB; 722576 Robert Gray Aaf; 722524 Rockport Aransas Co; 722630 San Angelo Mathis Field; 722530 San Antonio Intl AP; 722535 San Antonio Kelly Field AFB; 722523 San Antonio Stinson; 722448 Tyler Pounds Fld; 722550 Victoria Regional AP; 722560 Waco Regional AP; 723510 Wichita Falls Municipal Arpt; 722656 Wink Winkler County AP
- **UT**: 724723 Blanding; 724756 Bryce Cnyn Faa AP; 724755 Cedar City Municipal AP; 724795 Delta; 724735 Hanksville; 724776 Moab Canyonlands  Uo; 725755 Ogden Hill AFB; 725750 Ogden Hinkley Airport; 725724 Provo Muni  Awos; 724754 Saint George  Awos; 725720 Salt Lake City Intl Arpt  Isis; 725705 Vernal; 725810 Wendover Usaf Auxiliary Field
- **VA**: 724058 Abington; 724016 Charlottesville Faa; 724106 Danville Faa AP; 724037 Davison Aaf; 724014 Dinwiddie Co; 724017 Farmville; 723083 Franklin Naas; 724107 Hillsville; 724115 Hot Springs Ingalls; 745980 Langley AFB; 724055 Leesburg Godfrey; 724100 Lynchburg Regional Arpt; 724036 Manassas Muni Awos; 724056 Marion   Wytheville; 745985 Martinsville; 724026 Melfa Accomack Arpt; 723086 Newport News; 723080 Norfolk International AP; 723085 Norfolk Nas; 723075 Oceana Nas; 724116 Pulaski; 724035 Quantico Mcas; 724010 Richmond International AP; 724110 Roanoke Regional AP; 724033 Shannon Arpt; 724105 Staunton Shenandoah; 724113 Virginia Tech Arpt; 724030 Washington Dc Dulles Intl Ar; 724050 Washington Dc Reagan AP; 724053 Winchester Rgnl; 724117 Wise Lonesome Pine
- **VI**: 785430 Charlotte Amalie Harry S Trum
- **VT**: 726170 Burlington International AP; 726145 Montpelier AP; 725165 Rutland State; 726115 Springfield Hartnes
- **WA**: 727976 Bellingham Intl AP; 727928 Bremerton National; 727826 Ephrata AP Fcwos; 727855 Fairchild AFB; 727856 Felts Fld; 742070 Gray Aaf; 727840 Hanford; 727923 Hoquiam AP; 727924 Kelso Wb AP; 727827 Moses Lake Grant County AP; 727920 Olympia Airport; 727845 Pasco; 727857 Pullman Moscow Rgnl; 727970 Quillayute State Airport; 727934 Renton Muni; 727935 Seattle Boeing Field  Isis; 727930 Seattle Seattle Tacoma Intl A; 727937 Snohomish Co; 727850 Spokane International AP  Chen; 727815 Stampede Pass; 742060 Tacoma Mcchord AFB; 727938 Tacoma Narrows; 726988 The Dalles Municipal Arpt; 727926 Toledo Winlock Mem; 727846 Walla Walla City County AP; 727825 Wenatchee Pangborn; 690230 Whidbey Island Nas; 727885 William R Fairchild; 727810 Yakima Air Terminal
- **WI**: 726626 Antigo Lang Awos; 726457 Appleton Outagamie; 726435 Eau Claire County AP; 726450 Green Bay Austin Straubel Int; 726415 Janesville Rock Co; 726430 La Crosse Municipal Arpt; 726416 Lone Rock Faa AP; 726410 Madison Dane Co Regional Arpt; 726455 Manitowac Muni Awos; 726574 Marshfield Muni; 726400 Milwaukee Mitchell Intl AP; 726404 Minocqua Woodruff; 726465 Mosinee Central Wi; 726468 Phillips Price Co; 727415 Rhinelander Oneida; 726467 Rice Lake Municipal; 726458 Sturgeon Bay; 726464 Watertown; 726463 Wausau Municipal Arpt; 726456 Wittman Rgnl
- **WV**: 724120 Beckley Raleigh Co Mem AP; 724125 Bluefield Mercer Co  Nrel; 724140 Charleston Yeager Arpt; 724170 Elkins Elkins Randolph Co Arp; 724175 Harrison Marion Rgn; 724250 Huntington Tri State Arpt; 724127 Lewisburg Greenbrie; 724177 Martinsburg Eastern Wv Reg AP; 724176 Morgantown Hart Field; 724273 Parkersburg Wood County AP; 724275 Wheeling Ohio County AP
- **WY**: 725690 Casper Natrona Co Intl AP; 725640 Cheyenne Municipal Arpt; 726700 Cody Muni  Awos; 725775 Evanston Burns Fld; 726650 Gillette Gillette C; 725776 Jackson Hole; 725760 Lander Hunt Field; 725645 Laramie General Brees Field; 725745 Rawlins Municipal AP; 725765 Riverton Municipl AP; 725744 Rock Springs Arpt  Green River; 726660 Sheridan County Arpt; 726665 Worland Municipal
<!-- END GENERATED: stations-compact -->

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
