#!/usr/bin/env node
// Generates the course calendar (.ics) starting on a date you choose.
// Usage: node scripts/generate-ics.mjs --start 2027-03-01 [--time 19:00] [--lang en|pt-BR]
//        [--skip 2027-04-02,2027-04-21] [--name "Fintech Tech Course"] [--reminder 15] > course.ics
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseArgs } from "node:util";
import { buildIcs, schedule } from "../docs/ics.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { values } = parseArgs({
  options: {
    start: { type: "string" },
    time: { type: "string", default: "19:00" },
    lang: { type: "string", default: "en" },
    skip: { type: "string", default: "" },
    name: { type: "string" },
    reminder: { type: "string", default: "15" },
    help: { type: "boolean", short: "h" },
  },
});

if (values.help || !values.start) {
  console.error(readFileSync(fileURLToPath(import.meta.url), "utf8").split("\n").slice(1, 4).join("\n").replace(/^\/\/ ?/gm, ""));
  process.exit(values.help ? 0 : 1);
}

try {
  const data = JSON.parse(readFileSync(join(root, "docs", "sessions.json"), "utf8"));
  const skip = values.skip.split(",").map((s) => s.trim()).filter(Boolean);
  if (new Date(values.start + "T00:00:00Z").getUTCDay() !== 1) console.error(`Note: ${values.start} is not a Monday; weeks will not line up with Mon-Fri.`);
  const sessions = schedule(data.sessions, { start: values.start, skip });
  process.stdout.write(buildIcs(data, { start: values.start, time: values.time, lang: values.lang, skip, calendarName: values.name, reminderMinutes: Number(values.reminder) }));
  console.error(`${sessions.length} sessions, ${sessions[0].date} to ${sessions.at(-1).date}`);
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
