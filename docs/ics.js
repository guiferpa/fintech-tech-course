// Shared by the generator page (docs/index.html) and the CLI (scripts/generate-ics.mjs).
// Dates are handled as naive local dates (UTC arithmetic, no time zones) so the
// output uses floating times: 19:00 stays 19:00 in whatever zone the calendar uses.

const pad = (n) => String(n).padStart(2, "0");

function parseDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s).trim());
  if (!m) throw new Error(`Invalid date "${s}", expected YYYY-MM-DD`);
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  if (d.getUTCMonth() !== +m[2] - 1) throw new Error(`Invalid date "${s}"`);
  return d;
}

const isoDate = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
const icsDateTime = (d) =>
  `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00`;
const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
const isWeekend = (d) => d.getUTCDay() === 0 || d.getUTCDay() === 6;

// Assigns each session, in order, to the next weekday that is not a day off.
export function schedule(sessions, { start, skip = [] }) {
  let day = parseDate(start);
  const off = new Set(skip.filter(Boolean).map((s) => isoDate(parseDate(s))));
  const out = [];
  for (const s of sessions) {
    while (isWeekend(day) || off.has(isoDate(day))) day = addDays(day, 1);
    out.push({ ...s, date: isoDate(day) });
    day = addDays(day, 1);
  }
  return out;
}

function escapeText(s) {
  return String(s).replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

// RFC 5545: lines longer than 75 octets are folded with CRLF + space.
function fold(line) {
  const bytes = new TextEncoder().encode(line);
  if (bytes.length <= 75) return line;
  const parts = [];
  let cur = "", len = 0, limit = 75;
  for (const ch of line) {
    const n = new TextEncoder().encode(ch).length;
    if (len + n > limit) { parts.push(cur); cur = ""; len = 0; limit = 74; }
    cur += ch; len += n;
  }
  parts.push(cur);
  return parts.join("\r\n ");
}

export function buildIcs(data, { start, time = "19:00", lang = "en", skip = [], calendarName, reminderMinutes = 15, now = new Date() }) {
  if (!data.languages.includes(lang)) throw new Error(`Unknown language "${lang}", use one of: ${data.languages.join(", ")}`);
  const tm = /^(\d{1,2}):(\d{2})$/.exec(time);
  if (!tm || +tm[1] > 23 || +tm[2] > 59) throw new Error(`Invalid time "${time}", expected HH:MM`);
  const stamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//fintech-tech-course//calendar generator//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${escapeText(calendarName || data.course)}`,
  ];
  schedule(data.sessions, { start, skip }).forEach((s, i) => {
    const begin = new Date(parseDate(s.date).getTime() + (+tm[1] * 60 + +tm[2]) * 60000);
    const end = new Date(begin.getTime() + (s.minutes ?? data.sessionMinutes) * 60000);
    lines.push(
      "BEGIN:VEVENT",
      `UID:${start}-${String(i + 1).padStart(2, "0")}@fintech-tech-course`,
      `DTSTAMP:${stamp}`,
      `DTSTART:${icsDateTime(begin)}`,
      `DTEND:${icsDateTime(end)}`,
      `SUMMARY:${escapeText(s.title[lang])}`,
      `DESCRIPTION:${escapeText(s.description[lang])}`,
      `URL:${data.repo}`,
    );
    if (reminderMinutes > 0) {
      lines.push("BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${escapeText(s.title[lang])}`, `TRIGGER:-PT${reminderMinutes}M`, "END:VALARM");
    }
    lines.push("END:VEVENT");
  });
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}

