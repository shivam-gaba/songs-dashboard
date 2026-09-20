import { useCallback, useEffect, useState } from "react";
import { fetchSongs, rateSong } from "./api";
import type { Order, Song, SongPage } from "./types";
import { SongTable } from "./components/SongTable";
import { TitleSearch } from "./components/TitleSearch";
import { DurationChart } from "./components/DurationChart";
import { downloadCsv, songsToCsv } from "./csv";

const PAGE_SIZE = 10;

export default function App() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("index");
  const [order, setOrder] = useState<Order>("asc");
  const [data, setData] = useState<SongPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ratingBusy, setRatingBusy] = useState<string | null>(null);
  const [allSongs, setAllSongs] = useState<Song[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSongs(page, PAGE_SIZE, sortBy, order);
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, order]);

  useEffect(() => {
    load();
  }, [load]);

  // Fetch the whole dataset once for the chart (independent of paging/sort).
  useEffect(() => {
    fetchSongs(1, 1000, "index", "asc")
      .then((r) => setAllSongs(r.items))
      .catch(() => setAllSongs([]));
  }, []);

  function onSort(key: string) {
    if (key === sortBy) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setOrder("asc");
    }
    setPage(1); // sorting reflects the whole dataset; restart at page 1
  }

  async function onRate(song: Song, stars: number) {
    setRatingBusy(song.id);
    try {
      const updated = await rateSong(song.id, stars);
      // Reflect the new rating in both the current page and the chart set.
      setData((d) =>
        d
          ? { ...d, items: d.items.map((s) => (s.id === song.id ? updated : s)) }
          : d,
      );
      setAllSongs((xs) => xs.map((s) => (s.id === song.id ? { ...s, rating: updated.rating } : s)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRatingBusy(null);
    }
  }

  function onDownloadCsv() {
    if (!data) return;
    downloadCsv(`songs_page${data.page}_by_${sortBy}_${order}.csv`, songsToCsv(data.items));
  }

  const totalPages = data?.total_pages ?? 0;

  return (
    <div className="app">
      <header>
        <h1>🎵 Songs Dashboard</h1>
        <p className="sub">
          {data ? `${data.total} songs` : "…"} · normalized &amp; reconciled from
          two upstream exports · sorting &amp; paging happen on the server across
          the full dataset
        </p>
      </header>

      {error && <div className="banner error">Error: {error}</div>}

      <section className="table-section">
        <div className="toolbar">
          <div className="pager">
            <button disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
              ← Prev
            </button>
            <span>
              Page {data?.page ?? page} / {totalPages || "…"}
            </span>
            <button
              disabled={loading || (totalPages > 0 && page >= totalPages)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
          <div className="spacer" />
          <button className="csv" disabled={!data} onClick={onDownloadCsv}>
            ⬇ Download page as CSV
          </button>
        </div>

        {data && (
          <SongTable
            songs={data.items}
            sortBy={sortBy}
            order={order}
            onSort={onSort}
            onRate={onRate}
            ratingBusy={ratingBusy}
          />
        )}
        {loading && <p className="muted loading">Loading…</p>}
      </section>

      <TitleSearch />

      {allSongs.length > 0 && <DurationChart songs={allSongs} />}

      <footer>
        <p className="muted">
          Flags column shows per-value data-quality provenance (e.g.{" "}
          <code>duration_suspect</code>, <code>energy_malformed</code>). See
          DECISIONS.md for the reconciliation rules.
        </p>
      </footer>
    </div>
  );
}
