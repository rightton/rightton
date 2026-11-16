#!/usr/bin/env python3
"""Write the old-house stress cases as HPXML files for the reference engine.

Each case is NREL's sample house ``base-foundation-vented-crawlspace.xml`` (a
synthetic one-story house over a vented crawlspace) with old-house features
edited in. They are fictional test buildings, not real homes.

    python validation/stress/make_stress_cases.py <path to OpenStudio-HPXML clone>

writes validation/stress/stress-*.xml. Then run them through the reference:

    INPUT_DIR=validation/stress validation/run_reference.sh <clone> <output dir>
"""
import copy
import sys
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
NS = {"h": "http://hpxmlonline.com/2025/12"}  # set from the input file in main()


def q(tag):
    return f"{{{NS['h']}}}{tag}"


def find(el, path):
    return el.find("/".join(f"h:{p}" for p in path.split("/")), NS)


def findall(el, path):
    return el.findall("/".join(f"h:{p}" for p in path.split("/")), NS)


def text(el, path):
    found = find(el, path)
    return None if found is None else found.text


def set_text(el, path, value):
    find(el, path).text = str(value)


def enclosure(root):
    return find(root, "Building/BuildingDetails/Enclosure")


def balloon_frame_walls(root):
    """Uninsulated balloon-frame walls: plaster on lath, empty cavity, board sheathing,
    wood siding (about R-4.7 with films), and bare rim joists."""
    for wall in findall(enclosure(root), "Walls/Wall"):
        if text(wall, "InteriorAdjacentTo") == "conditioned space":
            set_text(wall, "Insulation/AssemblyEffectiveRValue", 4.7)
    for rim in findall(enclosure(root), "RimJoists/RimJoist"):
        set_text(rim, "Insulation/AssemblyEffectiveRValue", 3.0)


def single_pane_behind_porch(root):
    """Single-pane wood windows with no interior shading; the south windows sit under an
    8 ft deep porch roof."""
    for window in findall(enclosure(root), "Windows/Window"):
        set_text(window, "UFactor", 0.89)
        set_text(window, "SHGC", 0.64)
        shade = find(window, "InteriorShading")
        if shade is not None:
            window.remove(shade)
        if text(window, "Azimuth") == "180":
            overhang = etree.Element(q("Overhangs"))
            for tag, value in (("Depth", 8.0), ("DistanceToTopOfWindow", 1.5), ("DistanceToBottomOfWindow", 8.0)):
                etree.SubElement(overhang, q(tag)).text = str(value)
            find(window, "FractionOperable").addprevious(overhang)


def raised_floor(root):
    """Bare wood floor over the vented crawlspace (R-3.7 with films) and 11 ft ceilings."""
    for floor in findall(enclosure(root), "Floors/Floor"):
        if "crawlspace" in (text(floor, "ExteriorAdjacentTo") or ""):
            set_text(floor, "Insulation/AssemblyEffectiveRValue", 3.7)
    constr = find(root, "Building/BuildingDetails/BuildingSummary/BuildingConstruction")
    area = float(text(constr, "ConditionedFloorArea"))
    set_text(constr, "AverageCeilingHeight", 11.0)
    set_text(constr, "ConditionedBuildingVolume", area * 11.0)


def sealed_attic_with_ducts(root):
    """Unvented attic insulated at the roof deck (R-19.2) over a bare plaster ceiling
    (R-2.1), with all the ducts in the attic."""
    for roof in findall(enclosure(root), "Roofs/Roof"):
        set_text(roof, "Insulation/AssemblyEffectiveRValue", 19.2)
    for floor in findall(enclosure(root), "Floors/Floor"):
        if "attic" in (text(floor, "ExteriorAdjacentTo") or ""):
            set_text(floor, "Insulation/AssemblyEffectiveRValue", 2.1)
    for wall in findall(enclosure(root), "Walls/Wall"):
        if "attic" in (text(wall, "InteriorAdjacentTo") or ""):
            set_text(wall, "Insulation/AssemblyEffectiveRValue", 12.6)
    for duct in root.iter(q("Ducts")):
        set_text(duct, "DuctLocation", "attic - unvented")


def leaky(root):
    """Blower door: 14 ACH50."""
    for leak in root.iter(q("AirLeakage")):
        leak.text = "14.0"


def houston(root):
    """Hot-humid weather (Houston) instead of Denver."""
    for el in root.iter(q("EPWFilePath")):
        el.text = "USA_TX_Houston-Bush.Intercontinental.AP.722430_TMY3.epw"
    for el in root.iter(q("ClimateZone")):
        el.text = "2A"


CASES = {
    "stress-balloon-frame-walls": [balloon_frame_walls],
    "stress-single-pane-behind-porch": [single_pane_behind_porch],
    "stress-raised-floor-vented-crawlspace": [raised_floor],
    "stress-sealed-attic-with-ducts": [sealed_attic_with_ducts],
    "stress-leaky-14-ach50": [leaky],
    "stress-old-house-all-denver": [balloon_frame_walls, single_pane_behind_porch, raised_floor,
                                    sealed_attic_with_ducts, leaky],
    "stress-old-house-all-houston": [balloon_frame_walls, single_pane_behind_porch, raised_floor,
                                     sealed_attic_with_ducts, leaky, houston],
}


def main():
    base = Path(sys.argv[1]) / "workflow" / "sample_files" / "base-foundation-vented-crawlspace.xml"
    tree = etree.parse(str(base))
    NS["h"] = etree.QName(tree.getroot()).namespace
    for name, edits in CASES.items():
        case = copy.deepcopy(tree)
        for edit in edits:
            edit(case.getroot())
        case.write(str(HERE / f"{name}.xml"), xml_declaration=True, encoding="UTF-8")
        print(name, "<-", ", ".join(e.__name__ for e in edits))


if __name__ == "__main__":
    main()
