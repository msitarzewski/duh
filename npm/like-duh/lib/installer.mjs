import { execFileSync } from "node:child_process";
import { resolve } from "./resolver.mjs";
import { PACKAGE_NAME } from "./constants.mjs";

function printBox(lines) {
  const maxLen = Math.max(...lines.map((l) => l.length));
  const border = "+" + "-".repeat(maxLen + 2) + "+";
  console.log(border);
  for (const line of lines) {
    console.log("| " + line.padEnd(maxLen) + " |");
  }
  console.log(border);
}

function tryAutoInstall() {
  // Try uv tool install first
  try {
    console.log(`${PACKAGE_NAME}: Auto-installing duh via uv...`);
    execFileSync("uv", ["tool", "install", "duh"], {
      stdio: "inherit",
      timeout: 120_000,
    });
    return true;
  } catch {
    // uv not available or failed
  }

  // Fallback to pip install --user
  try {
    console.log(`${PACKAGE_NAME}: Auto-installing duh via pip...`);
    execFileSync("pip", ["install", "--user", "duh"], {
      stdio: "inherit",
      timeout: 120_000,
    });
    return true;
  } catch {
    // pip not available or failed
  }

  return false;
}

// --- main ---

const result = resolve();

if (result) {
  console.log(`${PACKAGE_NAME}: Found duh CLI (${result.command}${result.prefix.length ? " " + result.prefix.join(" ") : ""})`);
  process.exit(0);
}

// duh not found — try auto-install if opted in
if (process.env.DUH_AUTO_INSTALL === "1") {
  if (tryAutoInstall()) {
    console.log(`${PACKAGE_NAME}: duh installed successfully.`);
    process.exit(0);
  }
}

// Print instructions
printBox([
  `${PACKAGE_NAME}: duh CLI not found`,
  "",
  "Install the Python package with one of:",
  "",
  "  uv tool install duh        # recommended",
  "  pipx install duh",
  "  pip install duh",
  "",
  "Or set DUH_AUTO_INSTALL=1 before npm install",
  "to auto-install via uv or pip.",
]);

// Never block npm install
process.exit(0);
