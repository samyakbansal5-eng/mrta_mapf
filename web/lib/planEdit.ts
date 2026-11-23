// Pure helpers for the Plan editor. Every function returns a NEW plan object (never mutates).
// A plan is the same JSON the engine reads (see scenarios/small_factory.json).

export type Cell = [number, number];
export type Robot = { id: string; start: Cell; step_cost: number; payload: number; can_carry: string[] | null };
export type Product = { id: string; route: string[]; weight: number; process_time: Record<string, number> };
export type PlanEvent =
  | { t: number; type: "block_cells"; cells: Cell[]; until: number | null }
  | { t: number; type: "robot_failure" | "robot_recovered"; robot: string };
export type Plan = {
  name: string; time_step_seconds: number; grid: string[];
  stations: Record<string, Cell>; machines: Record<string, { type?: string }>;
  robots: Robot[]; products: Product[]; events: PlanEvent[];
  [k: string]: any;
};

export const STORES = ["RM", "FG"];
export const isStore = (name: string) => STORES.includes(name);

/** Deep copy + fill defaults, so the editor always sees every field. */
export function normalise(src: any, name?: string): Plan {
  const p = JSON.parse(JSON.stringify(src ?? {}));
  const stations: Record<string, Cell> = {};
  for (const [k, v] of Object.entries<any>(p.stations ?? {})) stations[k] = [Number(v[0]), Number(v[1])];
  const robots: Robot[] = (p.robots ?? []).map((r: any) => ({
    id: String(r.id),
    start: typeof r.start === "string" ? [...(stations[r.start] ?? [0, 0])] as Cell : [Number(r.start?.[0] ?? 0), Number(r.start?.[1] ?? 0)],
    step_cost: r.step_cost ?? 1,
    payload: r.payload ?? 10,
    can_carry: Array.isArray(r.can_carry) ? [...r.can_carry] : null,
  }));
  const products: Product[] = (p.products ?? []).map((x: any) => ({
    id: String(x.id), route: [...(x.route ?? [])], weight: x.weight ?? 0, process_time: { ...(x.process_time ?? {}) },
  }));
  const machines: Record<string, { type?: string }> = { ...(p.machines ?? {}) };
  for (const s of Object.keys(stations)) if (!isStore(s) && !machines[s]) machines[s] = {};
  return {
    ...p,
    name: name ?? p.name ?? "my plan",
    time_step_seconds: p.time_step_seconds ?? 1,
    grid: (p.grid ?? ["#####", "#...#", "#####"]).map(String),
    stations, machines, robots, products,
    events: (p.events ?? []).map((e: any) => ({ ...e })),
  };
}

export function nextId(prefix: string, used: string[]) {
  let n = 1;
  while (used.includes(prefix + n)) n++;
  return prefix + n;
}

const key = (c: Cell) => c[0] + "," + c[1];

/** Cells already taken by a station or a robot start. */
export function occupied(p: Plan) {
  const s = new Set<string>();
  Object.values(p.stations).forEach((c) => s.add(key(c)));
  p.robots.forEach((r) => s.add(key(r.start)));
  return s;
}

/** First free floor cell nobody uses, scanning row by row; null when the floor is full. */
export function freeCell(p: Plan): Cell | null {
  const used = occupied(p);
  for (let y = 0; y < p.grid.length; y++) for (let x = 0; x < p.grid[y].length; x++)
    if (p.grid[y][x] !== "#" && !used.has(x + "," + y)) return [x, y];
  return null;
}

// ------------------------------------------------------------------ robots
export function addRobot(p: Plan): Plan {
  const id = nextId("R", p.robots.map((r) => r.id));
  return { ...p, robots: [...p.robots, { id, start: freeCell(p) ?? [1, 1], step_cost: 1, payload: 10, can_carry: null }] };
}
export function updateRobot(p: Plan, i: number, patch: Partial<Robot>): Plan {
  const old = p.robots[i];
  const robots = p.robots.map((r, j) => (j === i ? { ...r, ...patch } : r));
  let events = p.events;
  if (patch.id && patch.id !== old.id)
    events = events.map((e) => ("robot" in e && e.robot === old.id ? { ...e, robot: patch.id! } : e));
  return { ...p, robots, events };
}
export function removeRobot(p: Plan, i: number): Plan {
  const id = p.robots[i].id;
  return { ...p, robots: p.robots.filter((_, j) => j !== i), events: p.events.filter((e) => !("robot" in e && e.robot === id)) };
}

// ------------------------------------------------------------------ machines / stations
export function addMachine(p: Plan): Plan {
  const id = nextId("M", Object.keys(p.stations));
  return { ...p, stations: { ...p.stations, [id]: freeCell(p) ?? [1, 1] }, machines: { ...p.machines, [id]: {} } };
}
export function moveStation(p: Plan, name: string, c: Cell): Plan {
  return { ...p, stations: { ...p.stations, [name]: c } };
}
export function setMachineType(p: Plan, name: string, type: string): Plan {
  const m = { ...(p.machines[name] ?? {}) };
  if (type) m.type = type; else delete m.type;
  return { ...p, machines: { ...p.machines, [name]: m } };
}
/** Rename a station everywhere it is used (routes, process times, machine info). Keeps order. */
export function renameStation(p: Plan, from: string, to: string): Plan {
  if (!to || from === to || to in p.stations) return p;
  const stations: Record<string, Cell> = {};
  for (const [k, v] of Object.entries(p.stations)) stations[k === from ? to : k] = v;
  const machines: Record<string, any> = {};
  for (const [k, v] of Object.entries(p.machines)) machines[k === from ? to : k] = v;
  const products = p.products.map((x) => {
    const pt: Record<string, number> = {};
    for (const [k, v] of Object.entries(x.process_time)) pt[k === from ? to : k] = v;
    return { ...x, route: x.route.map((m) => (m === from ? to : m)), process_time: pt };
  });
  return { ...p, stations, machines, products };
}
/** Remove a machine and every route step that uses it. */
export function removeMachine(p: Plan, name: string): Plan {
  if (isStore(name)) return p;
  const { [name]: _s, ...stations } = p.stations;
  const { [name]: _m, ...machines } = p.machines;
  const products = p.products.map((x) => {
    const { [name]: _t, ...pt } = x.process_time;
    return { ...x, route: x.route.filter((m) => m !== name), process_time: pt };
  });
  return { ...p, stations, machines, products };
}
export const machineNames = (p: Plan) => Object.keys(p.stations).filter((s) => !isStore(s));

// ------------------------------------------------------------------ products (job profiles)
export function addProduct(p: Plan): Plan {
  const id = nextId("P", p.products.map((x) => x.id));
  const m = machineNames(p)[0];
  return { ...p, products: [...p.products, { id, route: m ? [m] : [], weight: 1, process_time: m ? { [m]: 3 } : {} }] };
}
export function duplicateProduct(p: Plan, i: number): Plan {
  const src = p.products[i];
  const id = nextId("P", p.products.map((x) => x.id));
  const copy = { ...JSON.parse(JSON.stringify(src)), id };
  const robots = p.robots.map((r) => (r.can_carry && r.can_carry.includes(src.id) ? { ...r, can_carry: [...r.can_carry, id] } : r));
  const products = [...p.products];
  products.splice(i + 1, 0, copy);
  return { ...p, products, robots };
}
export function updateProduct(p: Plan, i: number, patch: Partial<Product>): Plan {
  const old = p.products[i];
  const products = p.products.map((x, j) => (j === i ? { ...x, ...patch } : x));
  let robots = p.robots;
  if (patch.id && patch.id !== old.id)
    robots = robots.map((r) => (r.can_carry ? { ...r, can_carry: r.can_carry.map((c) => (c === old.id ? patch.id! : c)) } : r));
  return { ...p, products, robots };
}
export function removeProduct(p: Plan, i: number): Plan {
  const id = p.products[i].id;
  return {
    ...p, products: p.products.filter((_, j) => j !== i),
    robots: p.robots.map((r) => (r.can_carry ? { ...r, can_carry: r.can_carry.filter((c) => c !== id) } : r)),
  };
}
/** Route editing: add a step at the end, remove step k, move step k by +-1, set its process time. */
export function addStep(p: Plan, i: number, machine: string, time = 3): Plan {
  const x = p.products[i];
  return updateProduct(p, i, { route: [...x.route, machine], process_time: { [machine]: time, ...x.process_time } });
}
export function removeStep(p: Plan, i: number, k: number): Plan {
  const x = p.products[i];
  const route = x.route.filter((_, j) => j !== k);
  const pt = { ...x.process_time };
  if (!route.includes(x.route[k])) delete pt[x.route[k]];
  return updateProduct(p, i, { route, process_time: pt });
}
export function moveStep(p: Plan, i: number, k: number, d: -1 | 1): Plan {
  const route = [...p.products[i].route];
  const j = k + d;
  if (j < 0 || j >= route.length) return p;
  [route[k], route[j]] = [route[j], route[k]];
  return updateProduct(p, i, { route });
}
export function setProcessTime(p: Plan, i: number, machine: string, v: number): Plan {
  return updateProduct(p, i, { process_time: { ...p.products[i].process_time, [machine]: v } });
}

// ------------------------------------------------------------------ events
export function addEvent(p: Plan, type: PlanEvent["type"]): Plan {
  const t = 10;
  const e: PlanEvent = type === "block_cells"
    ? { t, type, cells: [freeCell(p) ?? [1, 1]], until: t + 20 }
    : { t, type, robot: p.robots[0]?.id ?? "R1" };
  return { ...p, events: [...p.events, e] };
}
export function updateEvent(p: Plan, i: number, patch: any): Plan {
  return { ...p, events: p.events.map((e, j) => (j === i ? ({ ...e, ...patch } as PlanEvent) : e)) };
}
export function removeEvent(p: Plan, i: number): Plan {
  return { ...p, events: p.events.filter((_, j) => j !== i) };
}
/** "4,4; 5,4" <-> [[4,4],[5,4]]. Bad parts are dropped. */
export function parseCells(text: string): Cell[] {
  return text.split(/[;\n]/).map((s) => s.match(/-?\d+/g)).filter((m): m is RegExpMatchArray => !!m && m.length >= 2)
    .map((m) => [parseInt(m[0], 10), parseInt(m[1], 10)] as Cell);
}
export const formatCells = (cells: Cell[]) => cells.map((c) => c[0] + "," + c[1]).join("; ");

// ------------------------------------------------------------------ map
export function toggleWall(p: Plan, x: number, y: number): Plan {
  const rows = p.grid.map((r) => r.split(""));
  if (rows[y]?.[x] === undefined) return p;
  rows[y][x] = rows[y][x] === "#" ? "." : "#";
  return { ...p, grid: rows.map((r) => r.join("")) };
}
/**
 * Grow or shrink the map by one column (axis "x") or row ("y"). New space is added just inside the
 * right / bottom border, copying the neighbouring line, so a walled border stays walled.
 */
export function resize(p: Plan, axis: "x" | "y", d: 1 | -1): Plan {
  const H = p.grid.length, W = p.grid[0]?.length ?? 0;
  if (axis === "x") {
    if (d < 0 && W <= 3) return p;
    const at = Math.max(1, W - 1);
    const grid = p.grid.map((r) => (d > 0 ? r.slice(0, at) + r[at - 1] + r.slice(at) : r.slice(0, at - 1) + r.slice(at)));
    return { ...p, grid };
  }
  if (d < 0 && H <= 3) return p;
  const at = Math.max(1, H - 1);
  const grid = d > 0 ? [...p.grid.slice(0, at), p.grid[at - 1], ...p.grid.slice(at)] : [...p.grid.slice(0, at - 1), ...p.grid.slice(at)];
  return { ...p, grid };
}

/** Output for saving: drop empty machine-info entries' noise but keep everything the engine reads. */
export function toScenario(p: Plan) {
  return JSON.parse(JSON.stringify(p));
}
