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

// --- main ---

const result = resolve();

if (result) {
  console.log(`${PACKAGE_NAME}: Found duh CLI (${result.command}${result.prefix.length ? " " + result.prefix.join(" ") : ""})`);
  process.exit(0);
}

// Print instructions
printBox([
  `${PACKAGE_NAME}: duh CLI not found`,
  "",
  "Install this project's Python CLI from its public repository:",
  "",
  "  uv tool install git+https://github.com/msitarzewski/duh.git",
  "",
  "Or set DUH_PATH to an existing verified duh executable.",
]);

// Never block npm install
process.exit(0);
