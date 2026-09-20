import type { SearchResult, SongPage, Song, Order } from "./types";

const BASE = "/api";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function fetchSongs(
  page: number,
  size: number,
  sortBy: string,
  order: Order,
  query = "",
): Promise<SongPage> {
  const params = new URLSearchParams({
    page: String(page),
    size: String(size),
    sort_by: sortBy,
    order,
  });
  if (query.trim()) params.set("q", query.trim());
  return req<SongPage>(`/songs?${params}`);
}

// Backend caps `size` at 100 (a DoS guard), so to load the whole dataset for
// the chart we page through at the max size and concatenate. For very large
// catalogs this is many round-trips — see REFLECTION.md on why full-dataset
// loads don't scale — but it's correct and respects the API's limit.
const MAX_PAGE_SIZE = 100;

export async function fetchAllSongs(
  sortBy = "index",
  order: Order = "asc",
): Promise<Song[]> {
  const first = await fetchSongs(1, MAX_PAGE_SIZE, sortBy, order);
  const all = [...first.items];
  for (let p = 2; p <= first.total_pages; p++) {
    all.push(...(await fetchSongs(p, MAX_PAGE_SIZE, sortBy, order)).items);
  }
  return all;
}

export function searchByTitle(title: string): Promise<SearchResult> {
  return req<SearchResult>(`/songs/search?title=${encodeURIComponent(title)}`);
}

export function rateSong(id: string, stars: number): Promise<Song> {
  return req<Song>(`/songs/${encodeURIComponent(id)}/rating`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ stars }),
  });
}
