import assert from "node:assert/strict";
import test from "node:test";

import { RUN_LIFECYCLE_EVENT_TYPES, TERMINAL_RUN_EVENT_TYPES } from "./runEvents.ts";

test("system.run_failed is treated as a terminal run event", () => {
  assert.equal(TERMINAL_RUN_EVENT_TYPES.has("system.run_failed"), true);
  assert.equal(RUN_LIFECYCLE_EVENT_TYPES.has("system.run_failed"), true);
});

test("run_retry_started refreshes lifecycle without becoming terminal", () => {
  assert.equal(TERMINAL_RUN_EVENT_TYPES.has("run_retry_started"), false);
  assert.equal(RUN_LIFECYCLE_EVENT_TYPES.has("run_retry_started"), true);
});
