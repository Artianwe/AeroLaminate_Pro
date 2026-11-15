// Layup notation tests (node --test). Author: Anwesh Ajitabh Dash.
import test from "node:test";
import assert from "node:assert/strict";
import { parseLayup, formatLayup } from "../src/lib/layup.ts";

test("quasi-isotropic symmetric", () => {
  assert.deepEqual(parseLayup("[0/±45/90]s").angles, [0, 45, -45, 90, 90, -45, 45, 0]);
});
test("repeats and group multiplier", () => {
  assert.deepEqual(parseLayup("[45/-45/0_2]2").angles, [45, -45, 0, 0, 45, -45, 0, 0]);
  assert.deepEqual(parseLayup("[+-30]s").angles, [30, -30, -30, 30]);
});
test("middle ply", () => {
  assert.deepEqual(parseLayup("[0/90~]s").angles, [0, 90, 0]);
});
test("errors", () => {
  assert.ok(parseLayup("0/45").error);
  assert.ok(parseLayup("[0/abc]").error);
  assert.ok(parseLayup("[0/200]").error);
  assert.ok(parseLayup("[0//45]").error);
});
test("format round trip", () => {
  for (const s of ["[0/±45/90]s", "[45/-45/0_2]", "[0/90~]s", "[±30_2]s"]) {
    const a = parseLayup(s).angles;
    assert.deepEqual(parseLayup(formatLayup(a)).angles, a, s);
  }
});
