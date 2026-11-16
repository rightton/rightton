# Test of the LLM authoring guide

SPEC.md requires that a language model, given only
[FORMAT-GUIDE-FOR-LLMS.md](FORMAT-GUIDE-FOR-LLMS.md) and a description of a house, can produce a valid
house file. This records one such test.

## Method

- Date: 2026-11-16. Guide version: the one committed just before this file.
- A fresh model session (a Claude subagent with no knowledge of this repository) was given a folder
  holding two files only: a copy of the guide and the prose description below. It was told not to read
  anything else, not to run the validator or any tool, and to write the house file plus a candid list
  of everything the guide left unclear.
- The house in the description is fictional.

## Result

- The file it wrote is [`examples/llm-written-brick-bungalow.rtn.yaml`](../examples/llm-written-brick-bungalow.rtn.yaml), unedited.
- `python -m rightton.validate`: **valid on the first attempt, no errors, no warnings**
  (5 rooms, 2 spaces, 23 surfaces, 11 openings, 4 assemblies, 3 scenarios).
- It calculates: heating 51,051 Btu/h, sensible cooling 23,484 Btu/h, latent cooling 3,467 Btu/h; each of
  its three scenarios lowers the load.
- One run with one model is a pass, not proof. Its list of unclear points (below, as written) was long;
  the significant ones were answered in a new "Clarifications" section of the guide afterwards. The
  guide has not been re-tested since those edits.

## The description the model was given

A made-up 1930s brick bungalow near Baltimore, Maryland. One story plus an unfinished attic, over a
basement that nobody heats or cools.

The house is 28 feet wide (east-west) and 36 feet deep. The front faces north. Ceilings are 9 feet.

Rooms, all on one thermostat:
- Living room across the front, 28 ft x 14 ft. Three windows on the north wall and one each on the east
  and west walls. The front door is in the north wall.
- Kitchen at the back left (southwest corner), 14 ft x 12 ft, one window south, one west.
- Bedroom at the back right (southeast corner), 14 ft x 12 ft, one window south, one east.
- Between the living room and the back rooms: a bathroom on the west side (14 ft x 10 ft, one small
  2 ft x 3 ft window on the west) and a second bedroom on the east side (14 ft x 10 ft, one window east).

All windows other than the bathroom one are 2 ft 8 in wide by 5 ft tall, original single-pane wood
double-hungs. The ones on the south side got low-e storm windows a few years ago. The kitchen has a back
door in the south wall (insulated steel). The front door is an old solid wood door. Medium-colored
curtains half cover the living room windows.

Walls are solid brick, two wythes (about 8 inches), with plaster applied on wood lath over 3/4 inch
furring strips on the inside (so there is a 3/4 inch air gap). Dark red brick.

The attic is vented and unfinished. There is about 6 inches of old loose-fill fiberglass on the attic
floor over the plaster ceiling. The roof is a simple gable, 8-in-12 pitch, ridge running east-west,
dark asphalt shingles on board sheathing.

The floor is hardwood over a board subfloor on joists, no insulation, over the basement. The basement
has 8-inch poured concrete walls, 7.5 feet tall, with about 6 feet below grade, no insulation, and a
concrete slab floor.

A blower door test last year measured 2,900 CFM50.

Heating and cooling: a gas furnace and central air conditioner in the basement. All the ductwork is in
the basement, uninsulated sheet metal. There are supply registers in every room and one return in the
living room. Nobody has measured duct leakage; the technician guessed about 10 percent on the supply
side and 10 percent on the return side.

There is a bath exhaust fan but no whole-house ventilation. Three bedrooms are not present: it is a
two-bedroom house.

The owner wants to compare: (1) air sealing to about 1,800 CFM50, (2) adding R-38 of loose-fill
cellulose on top of the existing attic insulation, and (3) both together.
## The model's notes, unedited

### Notes for house.rtn.yaml

Nothing was validated or run; the file was written from GUIDE.md alone.

#### 1. Assumptions about the house

- Layout: living room 28 ft (E-W) x 14 ft across the north; bathroom (west) and bedroom 2 (east) each 14 ft E-W x 10 ft N-S in the middle; kitchen (SW) and bedroom 1 (SE) each 14 ft E-W x 12 ft N-S. 14 + 10 + 12 = 36 ft, so the stated dimensions are taken as overall outside dimensions and wall thickness is ignored.
- Weather station: Baltimore BWI, "724060".
- Both doors: size not given, estimated 3 ft x 6 ft 8 in (wrapped as estimated). Front door R-2 (solid wood), back door R-4.4 (insulated steel), the guide's two example values.
- "Dark red brick" taken as solar absorptance 0.9 (dark).
- Plaster on wood lath at the guide's fixed R; the 3/4 in furred gap as `air_space_closed`; brick 8 in.
- The ceiling is assumed to be plaster on wood lath like the walls (description only says "plaster ceiling").
- Curtains: "half cover" entered as `medium_curtains`, `coverage_frac: 0.5`, on all five living room windows.
- Low-e storms on the two south windows only (kitchen south, bedroom 1 south). The steel back door gets none.
- Floor assembly is hardwood + 3/4 in board subfloor only; joists ignored because the cavity is open to the basement.
- Ceiling joists ignored in the ceiling assembly (following the worked example, which has no framing in its ceiling).
- Basement is the full 28 x 36 ft footprint; one foundation wall surface for the whole 128 ft perimeter (960 ft2); slab 1008 ft2 with `exposed_perimeter_ft: 128`; slab thickness left out (not given).
- Roof: 1008 ft2 x 1.202 = 1212 ft2, split into north and south slopes (ridge runs east-west). No eave overhang added to the footprint. No window overhangs entered.
- Attic gable end walls, the rim joist, and basement windows/doors are not in the description and are left out.
- Bath exhaust fan left out (guide: whole-house fans only).
- Duct leakage 10% / 10% entered as fractions, wrapped as estimated. Ducts 100% in the basement, R-0.
- `stories_above_grade: 1` given; volume, building type, shielding left to defaults.
- No occupants or internal gains; no thermostat setpoints (defaults).
- Attic scenario implemented as "add a new ceiling assembly, then point all five ceilings at it"; the added cellulose is a named R-38 layer rather than a thickness of `cellulose_loose_fill`.

#### 2. Where the guide was unclear, ambiguous or silent

### Scenarios (the least certain part of my file)

1. No way is shown to add a layer to an existing assembly. `set` on `assemblies/ceiling-old/layers/2` (an index that does not exist yet) might append, might error. `add` is documented only with `section: "openings"`; whether `section` may be `assemblies`, or a nested list like an assembly's layers, is not said. I guessed that `add` with `section: assemblies` works.
2. Not stated whether changes in one scenario are applied in order (my `set` operations depend on the preceding `add`), or whether references are checked before or after the whole scenario is applied.
3. Not stated whether an assembly that no surface uses in the baseline is allowed (the alternative design: define the upgraded ceiling up front). An unused-item rule would decide which approach is right.
4. Changing one thing on many surfaces needs one `set` per surface (five here). If there is a shorter way (wildcard, or changing the assembly itself), the guide does not show it. Replacing a whole assembly with `set path: assemblies/ceiling-old` is not shown either.
5. `includes` with `changes: []` for the combined scenario: I inferred this is the intended pattern from "may be an empty list"; an example would confirm it. Order of `includes` vs own changes is given, order among included scenarios is not.
6. Can a scenario `value` be a wrapped `{value, source, confidence}` object? If the baseline field is wrapped (my CFM50 is), does a bare `value: 1800` replace the whole wrapper? Unknown.

### Estimated / wrapped values

7. The guide never says which fields accept the `{value, source, confidence}` wrapper. I used it on door `width_ft`/`height_ft` and on duct leakage fractions; if only some fields accept it, those are errors.
8. Allowed `confidence` values are not listed in the enum table; only `measured` and `estimated` appear in the text. I wanted something like "stated in the description but itself a guess" for the duct leakage and did not know if e.g. `assumed` or `default` exists. Also unclear whether `source` and `confidence` are both required in a wrapper.
9. "Leave optional fields out rather than guessing" vs. "estimate required ones": opening size is not marked `*`, yet a door with no size seems meaningless. I could not tell if door size is required or has a default, so I estimated it.

### Basement and foundation

10. `area_ft2` is marked required for every surface, but for `foundation_wall` there are also `height_ft` and `length_ft`. Is `area_ft2` still required, must it equal length x height, and is it the whole wall or only the above- or below-grade part? I gave all three consistently (960 = 128 x 7.5).
11. Not stated whether one foundation wall for the whole perimeter is acceptable or whether it should be one per side (with `azimuth_deg`). No basement or crawlspace appears in the worked example, which is the single biggest gap for this house.
12. `exposed_perimeter_ft` for a basement slab 6 ft below grade: is it the full perimeter (128), or 0 because no slab edge is exposed to outdoor air? I used the full perimeter.
13. Slab `thickness_in` default is not given. Since "0 = dirt floor", I worried about what an omitted thickness means; I left it out as instructed for unknown optional values.
14. Rim joist: `rim_joist` is a surface type but nothing says when one is expected, what its `inside` should be (basement? the room above?), or how to size it. Omitted.
15. `foundation_wall` `outside` "defaults to ground" but 1.5 ft of this wall is above grade. I assumed `depth_below_grade_ft` handles that split and did not add a separate above-grade wall.
16. Should the floor over the basement include joists as a framed layer when the cavity is empty? The framing rule only talks about "fill between them". I left joists out.
17. Do `floor` assemblies want the layers "inside face to outside face" meaning top (room side) to bottom? I assumed yes: hardwood first, then subfloor.

### Walls and assemblies

18. Solid masonry wall: `construction` and `cladding` are both offered. For solid brick, is it `construction: brick` + `cladding: brick`, or `cladding: none` (no separate cladding)? "brick and stone matter" suggests it affects the calculation, so a wrong pick may change results. I used brick for both.
19. With `construction: brick` and explicit `layers` containing 8 in of brick, is the brick double counted, or does `construction` only select a wall group? Not explained.
20. `{material: air_space_closed}` has a fixed R but no typical thickness; the description says 3/4 in. I did not know if `thickness_in` is allowed, ignored, or an error on a fixed-R material, so I omitted it. Same question for `plaster_on_wood_lath` (fixed R and a typical thickness).
21. The furring strips make the air-gap layer technically a framed layer. I did not add `framing_material`/`framing_frac` because the rule says framed layers need `thickness_in` and I was unsure it combines with a fixed-R material.
22. `solar_absorptance_frac`: only four anchor values given. "Dark red brick" could be 0.7 or 0.9. Also unclear whether cladding/roof color already implies it.
23. Ceiling with loose fill between and over joists: the example ignores framing; the framing rule says "0.1 joists/rafters". Unclear whether an attic-floor insulation layer should be marked framed.
24. Roof assembly: both `roofing: asphalt_shingles` (assembly field) and a `asphalt_shingles_on_deck` layer are used in the example. It is not explained why both are needed or what happens if they disagree. The `roofing` enum also has both `asphalt_shingles` and `shingles`.
25. Roof assemblies: no guidance on whether rafters belong in the layers for a vented attic roof (example omits them, so I did).

### Attic

26. Gable end walls of the attic: the guide says an attic needs ceilings and roof surfaces but says nothing about gable walls (a `wall` with `inside: attic`?). Omitted.
27. Roof `area_ft2`: should eave/rake overhangs be included? I used footprint only, per the formula.
28. Roof `azimuth_deg`: I assumed it is the direction the slope faces (downslope), by analogy with walls. Not stated.

### Openings

29. Curtains: `interior_shading` is described as `{type, coverage_frac, blinds_position}`. Is `blinds_position` required, forbidden, or ignored when `type` is curtains? I left it out.
30. "Half cover": is that `coverage_frac: 0.5` (share of window area covered) or fully hung curtains half drawn? The guide does not define `coverage_frac`.
31. `count` with width/height: I assume area is per unit times count (the guide says so for `area_ft2`, less explicitly for width/height).
32. `storm_window` on a door is not offered; fine here, but a storm door would have no home.
33. No field for window operating type or frame beyond the preset names; "wood double-hung" maps to `single_clear_wood` only through the preset description. Fine, just noting.
34. Whether a `glazing` preset plus `storm_window: low_e` is the right way to say "single pane with low-e storm" is only implied by the clear-storm sentence.
35. Feet-and-inches: 2 ft 8 in entered as 2.67. No guidance on rounding precision.

### Air, ducts, HVAC

36. With `airflow_cfm_at_50pa` (CFM50), is `volume_ft3` or `height_ft` needed to convert? Does the default volume include only the rooms (9072 ft3) or also the basement, which a blower door test of this house likely included? Not said; I left volume out.
37. `stories_above_grade`, `building_type`, `shielding_class`, `site_shielding`, `weather_shielding_factor`: no description of defaults or of when to set them. `shielding_class` and `site_shielding` look like two fields for the same idea.
38. Duct leakage fractions: fraction of what (system airflow)? And if the ducts are in an unconditioned basement that is inside the blower-door envelope, is that handled? Not explained.
39. Duct segments: with one supply and one return segment each at `share_of_ducts_frac: 1.0`, I assumed shares are per type (supply shares sum to 1, return shares sum to 1), following the example. Not stated.
40. Location of the furnace itself (basement) has no field; fine, but `blower_heat_btu_hr` and `piping_loss_btu_hr` have no guidance on when to set them.
41. Bath exhaust fan: "Whole-house fans only" let me omit it, but the wording could also be read as "only whole-house fans (attic fans) go here". Clearer: "continuous whole-house mechanical ventilation only; leave out bath and kitchen spot fans".
42. `unconditioned_basement` space: optional fields like `volume_ft3` have no stated default; I left all out.

### General / format

43. `format_version: 1.0.0` unquoted is a YAML string (fine), but worth saying whether quotes matter, as is done for the station id.
44. Output rules say "list in plain text what you assumed" after the file, while files may not contain unknown fields; it is not said whether YAML comments are allowed in the file (the example uses them, so I did).
45. The reserved words list does not say whether ids like `house`, `attic`, `basement`, `ducts` (which mirror section or type names) are safe; the example uses `attic` and `ducts`, so I assumed yes.
46. The guide says ids are unique file-wide; unclear whether that includes scenario ids and ids of items created by scenario `add`.
47. "Three bedrooms are not present: it is a two-bedroom house" in the description is oddly worded; I read it as `bedroom_count: 2`. (A description problem, not a guide problem.)
48. The station table has two Boulder entries with different ids; no guidance on choosing. Not relevant here, but a reader would stumble.
49. "Wall area = length x ceiling height": for an old house with 9 ft ceilings the wall between ceiling and floor framing is not counted anywhere unless a rim joist is entered; no guidance.
