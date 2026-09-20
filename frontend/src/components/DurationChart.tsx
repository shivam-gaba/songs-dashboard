import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Song } from "../types";

/**
 * Duration per song, in the raw stored `duration_ms`. This chart is chosen to
 * EXPOSE the unit bug: three songs were recorded in seconds, not milliseconds,
 * so on a linear ms axis their bars are ~invisible next to real tracks. We
 * paint those three red so the quirk is unmistakable rather than hidden.
 */
export function DurationChart({ songs }: { songs: Song[] }) {
  const data = songs
    .filter((s) => s.duration_ms !== null)
    .map((s) => ({
      title: s.title ?? s.id.slice(0, 6),
      duration_ms: s.duration_ms as number,
      suspect: s.data_quality.includes("duration_suspect"),
    }));

  const suspectCount = data.filter((d) => d.suspect).length;

  return (
    <section className="chart-card">
      <h2>Duration per song (raw ms)</h2>
      <p className="chart-note">
        {suspectCount} bars are painted red: their <code>duration_ms</code> is
        implausibly small (e.g. 158) — recorded in <strong>seconds, not
        milliseconds</strong>. They vanish on a linear ms axis, which is exactly
        the point: the chart surfaces a unit bug a summary statistic would hide.
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 64 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="title"
            angle={-40}
            textAnchor="end"
            interval={0}
            height={70}
            tick={{ fontSize: 11 }}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(v: number, _n, p) =>
              (p?.payload?.suspect ? `${v} (suspect: looks like seconds)` : `${v} ms`)
            }
          />
          <Bar dataKey="duration_ms" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.suspect ? "#d64545" : "#4c6ef5"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
