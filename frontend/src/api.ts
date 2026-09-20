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
): Promise<SongPage> {
  const q = new URLSearchParams({
    page: String(page),
    size: String(size),
    sort_by: sortBy,
    order,
  });
  return req<SongPage>(`/songs?${q}`);
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
