export interface Song {
  index: number;
  id: string;
  title: string | null;
  danceability: number | null;
  energy: number | null;
  mood: number | null;
  acousticness: number | null;
  tempo: number | null;
  valence: number | null;
  duration_ms: number | null;
  num_sections: number | null;
  num_segments: number | null;
  rating: number | null;
}

export interface SongPage {
  items: Song[];
  page: number;
  size: number;
  total: number;
  total_pages: number;
  sort_by: string;
  order: string;
}

export interface SearchResult {
  query: string;
  count: number;
  matches: Song[];
}

export type Order = "asc" | "desc";

// Columns shown in the table, in order. `key` maps to the API sort field.
export const COLUMNS: { key: keyof Song; label: string; numeric: boolean }[] = [
  { key: "index", label: "#", numeric: true },
  { key: "title", label: "Title", numeric: false },
  { key: "danceability", label: "Dance", numeric: true },
  { key: "energy", label: "Energy", numeric: true },
  { key: "valence", label: "Valence", numeric: true },
  { key: "mood", label: "Mood", numeric: true },
  { key: "acousticness", label: "Acoustic", numeric: true },
  { key: "tempo", label: "Tempo", numeric: true },
  { key: "duration_ms", label: "Duration", numeric: true },
];

/** Format a duration in ms as MM:SS:MS (e.g. 225947 -> "03:45:947"). */
export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  const millis = Math.round(ms % 1000);
  const p2 = (n: number) => String(n).padStart(2, "0");
  return `${p2(minutes)}:${p2(seconds)}:${String(millis).padStart(3, "0")}`;
}
