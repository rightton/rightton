// Client for the Python core running in a web worker.
import type { CalcOutput, Library, Ranges } from "./types";

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void };

class Engine {
  private worker: Worker;
  private pending = new Map<number, Pending>();
  private next = 1;
  ready: Promise<void>;

  constructor() {
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    this.worker.onmessage = (event) => {
      const { id, ok, result, error } = event.data;
      const p = this.pending.get(id);
      if (!p) return;
      this.pending.delete(id);
      if (ok) p.resolve(result);
      else p.reject(new Error(error));
    };
    this.worker.onerror = (event) => {
      for (const p of this.pending.values()) p.reject(new Error(event.message || "The calculation engine failed to start."));
      this.pending.clear();
    };
    const base = new URL(import.meta.env.BASE_URL, window.location.href).href;
    this.ready = this.send("__init__", { base }).then(() => undefined);
  }

  private send(name: string, payload: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const id = this.next++;
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, name, payload });
    });
  }

  private async call<T>(name: string, payload: unknown): Promise<T> {
    await this.ready;
    return (await this.send(name, payload)) as T;
  }

  library = () => this.call<Library>("library", {});
  calculate = (house: unknown) => this.call<CalcOutput>("calculate", house);
  sensitivity = (house: unknown) => this.call<Ranges>("sensitivity", house);
  assembly = (asm: unknown) => this.call<AssemblyResult>("assembly", asm);
  epw = (text: string) => this.call<{ weather_station_name: string; design_conditions: Record<string, unknown> }>("design_conditions_from_epw", text);
}

export type AssemblyResult = {
  ok: boolean; error?: string; from_layers?: boolean; r_value?: number; u_factor?: number; r_value_sheltered?: number;
  cavity_path_r?: number; framing_path_r?: number; film_inside_r?: number; film_outside_r?: number;
  layers?: { name: string; r_value: number; framing_r_value: number | null }[];
};

export const engine = new Engine();
