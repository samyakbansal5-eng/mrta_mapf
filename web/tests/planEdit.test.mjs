// Unit tests for the Plan editor helpers. Run: npm run test:editor (Node 22+, strips TS types).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import * as E from "../lib/planEdit.ts";

const sample = JSON.parse(fs.readFileSync(new URL("../../scenarios/small_factory.json", import.meta.url), "utf8"));
const base = () => E.normalise(sample, "copy");

test("normalise copies and never mutates the source", () => {
  const p = base();
  p.robots[0].id = "X";
  assert.equal(sample.robots[0].id, "R1");
  assert.equal(p.robots[2].can_carry, null);
  assert.deepEqual(Object.keys(p.machines).sort(), ["M1", "M2", "M3", "M4"]);
});

test("add robot picks a new id and a free floor cell", () => {
  const p = E.addRobot(base());
  const r = p.robots[3];
  assert.equal(r.id, "R4");
  assert.equal(p.grid[r.start[1]][r.start[0]], ".");
  assert.ok(!E.occupied(base()).has(r.start.join(",")));
});

test("renaming or removing a robot updates its events", () => {
  let p = { ...base(), events: [{ t: 3, type: "robot_failure", robot: "R2" }] };
  p = E.updateRobot(p, 1, { id: "AGV2" });
  assert.equal(p.events[0].robot, "AGV2");
  p = E.removeRobot(p, 1);
  assert.equal(p.events.length, 0);
  assert.equal(p.robots.length, 2);
});

test("machines: add, rename everywhere, remove from routes", () => {
  let p = E.addMachine(base());
  assert.ok("M5" in p.stations);
  p = E.renameStation(p, "M2", "Lathe");
  assert.deepEqual(p.products[0].route, ["M1", "Lathe", "M4"]);
  assert.equal(p.products[0].process_time.Lathe, 3);
  assert.deepEqual(Object.keys(p.stations).slice(0, 3), ["RM", "M1", "Lathe"]);
  assert.equal(E.renameStation(p, "M1", "M3"), p, "rename onto an existing name is refused");
  p = E.removeMachine(p, "Lathe");
  assert.deepEqual(p.products[0].route, ["M1", "M4"]);
  assert.deepEqual(p.products[1].route, ["M3"]);
  assert.equal(E.removeMachine(p, "RM"), p, "stores cannot be removed");
});

test("products: route steps, duplicate, rename keeps can_carry in step", () => {
  let p = base();
  p.robots[0].can_carry = ["P1"];
  p = E.addStep(p, 2, "M4", 7);
  assert.deepEqual(p.products[2].route, ["M3", "M4"]);
  assert.equal(p.products[2].process_time.M4, 7);
  p = E.moveStep(p, 2, 1, -1);
  assert.deepEqual(p.products[2].route, ["M4", "M3"]);
  p = E.removeStep(p, 2, 0);
  assert.deepEqual(p.products[2].process_time, { M3: 5 });
  p = E.duplicateProduct(p, 0);
  assert.equal(p.products[1].id, "P4");
  assert.deepEqual(p.robots[0].can_carry, ["P1", "P4"]);
  p = E.updateProduct(p, 0, { id: "Gear" });
  assert.deepEqual(p.robots[0].can_carry, ["Gear", "P4"]);
  p = E.removeProduct(p, 0);
  assert.deepEqual(p.robots[0].can_carry, ["P4"]);
});

test("events and cell parsing", () => {
  assert.deepEqual(E.parseCells("4,4; 5, 4 ; bad"), [[4, 4], [5, 4]]);
  assert.equal(E.formatCells([[4, 4], [5, 4]]), "4,4; 5,4");
  let p = E.addEvent(base(), "block_cells");
  assert.equal(p.events[0].until, 30);
  p = E.updateEvent(p, 0, { until: null });
  assert.equal(p.events[0].until, null);
  assert.equal(E.removeEvent(p, 0).events.length, 0);
});

test("map: toggle wall and resize keep a rectangular grid", () => {
  let p = E.toggleWall(base(), 1, 1);
  assert.equal(p.grid[1][1], "#");
  const W = p.grid[0].length, H = p.grid.length;
  p = E.resize(E.resize(p, "x", 1), "y", 1);
  assert.equal(p.grid[0].length, W + 1);
  assert.equal(p.grid.length, H + 1);
  assert.ok(p.grid.every((r) => r.length === W + 1));
  assert.equal(p.grid[1][W], "#", "right border stays a wall");
  p = E.resize(E.resize(p, "x", -1), "y", -1);
  assert.equal(p.grid.length, H);
  assert.equal(p.grid[0].length, W);
});
