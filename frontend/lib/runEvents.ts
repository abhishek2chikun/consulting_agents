export const TERMINAL_RUN_EVENT_TYPES = new Set([
  "run_completed",
  "run_failed",
  "system.run_failed",
  "run_cancelled",
]);

export const RUN_LIFECYCLE_EVENT_TYPES = new Set([
  ...TERMINAL_RUN_EVENT_TYPES,
  "cancel_ack",
]);
