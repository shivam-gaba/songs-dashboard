import type { Order, Song } from "../types";
import { COLUMNS } from "../types";
import { StarRating } from "./StarRating";

interface Props {
  songs: Song[];
  sortBy: string;
  order: Order;
  onSort: (key: string) => void;
  onRate: (song: Song, stars: number) => void;
  ratingBusy: string | null;
}

function fmt(v: number | null, digits = 3): string {
  return v === null ? "—" : Number.isInteger(v) ? String(v) : v.toFixed(digits);
}

export function SongTable({
  songs,
  sortBy,
  order,
  onSort,
  onRate,
  ratingBusy,
}: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {COLUMNS.map((c) => {
              const active = sortBy === c.key;
              return (
                <th
                  key={String(c.key)}
                  className={"sortable" + (c.numeric ? " num" : "")}
                  onClick={() => onSort(String(c.key))}
                  aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}
                  title="Click to sort (whole dataset)"
                >
                  {c.label}
                  <span className="arrow">{active ? (order === "asc" ? " ▲" : " ▼") : ""}</span>
                </th>
              );
            })}
            <th>Rating</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {songs.map((s) => (
            <tr key={s.id}>
              <td className="num">{s.index}</td>
              <td>{s.title ?? <em className="muted">untitled</em>}</td>
              <td className="num">{fmt(s.danceability)}</td>
              <td className="num">{fmt(s.energy)}</td>
              <td className="num">{fmt(s.valence)}</td>
              <td className="num">{s.mood === null ? "—" : s.mood}</td>
              <td className="num">{fmt(s.acousticness, 4)}</td>
              <td className="num">{fmt(s.tempo)}</td>
              <td className={"num" + (s.data_quality.includes("duration_suspect") ? " suspect" : "")}>
                {fmt(s.duration_ms)}
              </td>
              <td>
                <StarRating
                  value={s.rating}
                  disabled={ratingBusy === s.id}
                  onRate={(stars) => onRate(s, stars)}
                />
              </td>
              <td className="flags">
                {s.data_quality.length === 0 ? (
                  <span className="ok">clean</span>
                ) : (
                  s.data_quality.map((f) => (
                    <span key={f} className="flag" title={f}>
                      {f}
                    </span>
                  ))
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
