import { useCallback, useEffect, useState } from "react";
import { fetchAllSongs, fetchSongs, rateSong } from "./api";
import type { Order, Song, SongPage } from "./types";
import { SongTable } from "./components/SongTable";
import { RatingChart } from "./components/RatingChart";
import { downloadCsv, songsToCsv } from "./csv";

const PAGE_SIZE = 10;

export default function App() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("index");
  const [order, setOrder] = useState<Order>("asc");
  const [search, setSearch] = useState(""); // raw input
  const [query, setQuery] = useState(""); // debounced, applied filter
  const [data, setData] = useState<SongPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ratingBusy, setRatingBusy] = useState<string | null>(null);
  const [allSongs, setAllSongs] = useState<Song[]>([]);

  // Debounce the search box by 1s so we don't fire an API call on every
  // keystroke; applying a new filter restarts at page 1.
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 1000);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchSongs(page, PAGE_SIZE, sortBy, order, query));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, order, query]);

  useEffect(() => {
    load();
  }, [load]);

  // Load the whole dataset once for the chart (paged under the API's size cap).
  useEffect(() => {
    fetchAllSongs()
      .then(setAllSongs)
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
  const isFiltering = query.length > 0;
  const noResults = !!data && data.total === 0;

  return (
    <div className="app">
      <header>
        <h1>🎵 Songs Dashboard</h1>
        <p className="sub">{data ? `${data.total} songs` : "…"}</p>
      </header>

      {error && <div className="banner error">Error: {error}</div>}

      {/* Search sits above the table and filters it (partial, case/space-insensitive). */}
      <div className="searchbar">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title… (e.g. 21, perfect)"
          aria-label="search songs by title"
        />
        {search && (
          <button className="clear" onClick={() => setSearch("")} aria-label="clear search">
            ✕
          </button>
        )}
      </div>

      <section className="table-section">
        <div className="toolbar">
          <div className="pager">
            <button disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
              ← Prev
            </button>
            <span>
              Page {noResults ? 0 : data?.page ?? page} / {totalPages}
            </span>
            <button
              disabled={loading || totalPages === 0 || page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
          {isFiltering && data && (
            <span className="result-count">
              {data.total} result{data.total === 1 ? "" : "s"} for “{query}”
            </span>
          )}
          <div className="spacer" />
          <button className="csv" disabled={!data || noResults} onClick={onDownloadCsv}>
            ⬇ Download page as CSV
          </button>
        </div>

        {data && !noResults && (
          <SongTable
            songs={data.items}
            sortBy={sortBy}
            order={order}
            onSort={onSort}
            onRate={onRate}
            ratingBusy={ratingBusy}
          />
        )}
        {noResults && (
          <p className="empty">
            No songs match “{query}”. Search ignores case and spacing and matches
            any part of the title.
          </p>
        )}
        {loading && <p className="muted loading">Loading…</p>}
      </section>

      {allSongs.length > 0 && <RatingChart songs={allSongs} />}
    </div>
  );
}
