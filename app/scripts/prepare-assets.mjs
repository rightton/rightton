// Copies everything the app needs at run time into public/ (all git-ignored):
//   public/pyodide/      the Pyodide runtime (Python compiled for the browser), from node_modules
//   public/core.json     RightTon's Python core, data files and schema as {path: text}
//   public/examples/     the example house files
// Nothing is fetched from another site when the app runs.
import { cpSync, mkdirSync, readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const app = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(app, "..");
const pub = join(app, "public");

mkdirSync(join(pub, "pyodide"), { recursive: true });
for (const f of ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]) {
  const src = join(app, "node_modules", "pyodide", f);
  if (existsSync(src)) cpSync(src, join(pub, "pyodide", f));
}

const files = {};
for (const f of readdirSync(join(repo, "core", "rightton"))) {
  if (f.endsWith(".py")) files[`rightton/${f}`] = readFileSync(join(repo, "core", "rightton", f), "utf8");
}
for (const f of readdirSync(join(repo, "data"))) {
  if (f.endsWith(".json") || f.endsWith(".csv")) files[`rightton/_data/${f}`] = readFileSync(join(repo, "data", f), "utf8");
}
files["rightton/_data/rightton-house.schema.json"] = readFileSync(join(repo, "schema", "rightton-house.schema.json"), "utf8");
writeFileSync(join(pub, "core.json"), JSON.stringify(files));

mkdirSync(join(pub, "examples"), { recursive: true });
for (const f of readdirSync(join(repo, "examples"))) cpSync(join(repo, "examples", f), join(pub, "examples", f));
mkdirSync(join(pub, "schema"), { recursive: true });
cpSync(join(repo, "schema", "rightton-house.schema.json"), join(pub, "schema", "rightton-house.schema.json"));
console.log(`assets ready: ${Object.keys(files).length} core files`);
