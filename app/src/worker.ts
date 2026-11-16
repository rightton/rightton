/// <reference lib="webworker" />
// Runs RightTon's Python core in a background thread through Pyodide, so the
// page stays responsive. All load math happens in Python; this file only
// passes JSON in and out.

type Msg = { id: number; name: string; payload: unknown };

let call: ((name: string, payload: string) => string) | null = null;

async function init(base: string) {
  const { loadPyodide } = await import(/* @vite-ignore */ `${base}pyodide/pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: `${base}pyodide/` });
  const files: Record<string, string> = await (await fetch(`${base}core.json`)).json();
  const root = "/home/pyodide/rightton_core";
  for (const [path, text] of Object.entries(files)) {
    const full = `${root}/${path}`;
    pyodide.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
    pyodide.FS.writeFile(full, text);
  }
  pyodide.runPython(`import sys\nsys.path.insert(0, "${root}")\nfrom rightton import api`);
  const fn = pyodide.globals.get("api").call;
  call = (name, payload) => fn(name, payload) as string;
}

self.onmessage = async (event: MessageEvent<Msg>) => {
  const { id, name, payload } = event.data;
  try {
    if (name === "__init__") {
      await init((payload as { base: string }).base);
      self.postMessage({ id, ok: true, result: null });
      return;
    }
    if (!call) throw new Error("The calculation engine is not loaded yet.");
    const out = JSON.parse(call(name, JSON.stringify(payload)));
    self.postMessage({ id, ...out });
  } catch (e) {
    self.postMessage({ id, ok: false, error: e instanceof Error ? e.message : String(e) });
  }
};
