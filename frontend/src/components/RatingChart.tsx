import { useEffect, useState } from "react";
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

// One compartment per rating class, plus a bucket for unrated songs. The colour
// ramp runs cool→warm with the rating (gold, matching the stars); unrated is grey.
const CLASSES: { label: string; stars: number | null; color: string }[] = [
  { label: "Unrated", stars: null, color: "#ced4da" },
  { label: "★ 1", stars: 1, color: "#ffd8a8" },
  { label: "★ 2", stars: 2, color: "#ffc078" },
  { label: "★ 3", stars: 3, color: "#ffa94d" },
  { label: "★ 4", stars: 4, color: "#ff922b" },
  { label: "★ 5", stars: 5, color: "#f76707" },
];

const PREVIEW = 5; // songs shown in the hover tooltip before "+N more"

interface Bucket {
  label: string;
  count: number;
  color: string;
  songs: string[];
}

function RatingTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const b: Bucket = payload[0].payload;
  const extra = b.count - PREVIEW;
  return (
    <div className="chart-tooltip">
      <strong>
        {b.label} · {b.count} song{b.count === 1 ? "" : "s"}
      </strong>
      {b.songs.length > 0 && (
        <ul>
          {b.songs.slice(0, PREVIEW).map((t, i) => (
            <li key={i}>{t}</li>
          ))}
          {extra > 0 && <li className="more-hint">+{extra} more · click bar to view all</li>}
        </ul>
      )}
    </div>
  );
}

/**
 * Distribution of songs across rating classes. Each bar is a compartment (1–5
 * stars, plus Unrated); its height is how many songs sit there. Hovering shows
 * up to five example songs; clicking a bar opens a side drawer with the full
 * list — the tooltip never tries to render a huge category (scales to 1000+).
 */
export function RatingChart({ songs }: { songs: Song[] }) {
  const [drawer, setDrawer] = useState<Bucket | null>(null);

  const data: Bucket[] = CLASSES.map((c) => {
    const matches = songs.filter((s) =>
      c.stars === null ? s.rating == null : s.rating === c.stars,
    );
    return {
      label: c.label,
      count: matches.length,
      color: c.color,
      songs: matches.map((s) => s.title ?? s.id.slice(0, 6)),
    };
  });

  const rated = songs.filter((s) => s.rating != null).length;

  // Close the drawer on Escape.
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  return (
    <section className="chart-card">
      <h2>Songs by rating</h2>
      <p className="chart-note">
        {rated} of {songs.length} songs rated. Each bar is a rating class — hover
        to preview, click a bar to see every song in it.
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip content={<RatingTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
          <Bar
            dataKey="count"
            isAnimationActive={false}
            radius={[4, 4, 0, 0]}
            cursor="pointer"
            onClick={(_: unknown, index: number) => {
              const b = data[index];
              if (b && b.count > 0) setDrawer(b);
            }}
          >
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {drawer && (
        <>
          <div className="drawer-overlay" onClick={() => setDrawer(null)} />
          <aside className="drawer" role="dialog" aria-label={`Songs rated ${drawer.label}`}>
            <header className="drawer-head">
              <h3>
                {drawer.label} · {drawer.count} song{drawer.count === 1 ? "" : "s"}
              </h3>
              <button className="drawer-close" onClick={() => setDrawer(null)} aria-label="close">
                ✕
              </button>
            </header>
            {/* Scrollable list handles large categories; a very large catalog
                would page this from the API rather than the in-memory set. */}
            <ol className="drawer-list">
              {drawer.songs.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ol>
          </aside>
        </>
      )}
    </section>
  );
}
