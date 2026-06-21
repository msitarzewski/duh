#!/usr/bin/env node

import { spawn } from "node:child_process";
import { resolve } from "../lib/resolver.mjs";
import { PACKAGE_NAME } from "../lib/constants.mjs";

const result = resolve();

if (!result) {
  console.error(`${PACKAGE_NAME}: duh CLI not found.\n`);
  console.error("Install the Python package with one of:");
  console.error("  uv tool install duh        # recommended");
  console.error("  pipx install duh");
  console.error("  pip install duh");
  console.error(`\nOr set DUH_PATH to the duh executable path.`);
  process.exit(1);
}

const args = [...result.prefix, ...process.argv.slice(2)];
const child = spawn(result.command, args, { stdio: "inherit" });

// Forward signals to child
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    child.kill(signal);
  });
}

child.on("error", (err) => {
  console.error(`${PACKAGE_NAME}: Failed to start duh: ${err.message}`);
  process.exit(1);
});

child.on("close", (code, signal) => {
  if (signal) {
    // Re-raise the signal so the parent sees the correct exit status
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 1);
  }
});
