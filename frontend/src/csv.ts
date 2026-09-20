import type { Song } from "./types";
import { COLUMNS } from "./types";

/** Escape a value for CSV (RFC-4180-ish): quote if it contains , " or newline. */
function cell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Serialize the currently shown rows to a CSV string (visible columns + rating). */
export function songsToCsv(songs: Song[]): string {
  const cols = [...COLUMNS.map((c) => c.key), "rating" as const];
  const header = [...COLUMNS.map((c) => c.label), "Rating"].join(",");
  const rows = songs.map((s) => cols.map((k) => cell(s[k])).join(","));
  return [header, ...rows].join("\n");
}

/** Trigger a browser download of the given CSV text. */
export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
