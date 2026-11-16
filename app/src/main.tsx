import { engine } from "./engine";
const el = document.getElementById("root")!;
el.textContent = "loading";
(async () => {
  const lib = await engine.library();
  const house = await (await fetch("./examples/old-house.rtn.json")).json();
  const out = await engine.calculate(house);
  el.textContent = `SMOKE ${lib.format_version} ${out.valid} ${Math.round(out.baseline!.building.heating_btuh)} ${out.scenarios.length}`;
})().catch((e) => { el.textContent = "FAIL " + e.message; });
