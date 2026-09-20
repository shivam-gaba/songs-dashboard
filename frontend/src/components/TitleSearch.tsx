import { useState } from "react";
import type { Song } from "../types";
import { searchByTitle } from "../api";

/** Title search: type a title, Get Song, render 0 / 1 / many matches. */
export function TitleSearch() {
  const [title, setTitle] = useState("");
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "done"; query: string; matches: Song[] }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setState({ kind: "loading" });
    try {
      const r = await searchByTitle(title.trim());
      setState({ kind: "done", query: r.query, matches: r.matches });
    } catch (err) {
      setState({ kind: "error", message: (err as Error).message });
    }
  }

  return (
    <section className="search-card">
      <h2>Find a song by title</h2>
      <form onSubmit={run} className="search-form">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. perfect  (case & spacing don't matter)"
          aria-label="song title"
        />
        <button type="submit">Get Song</button>
      </form>

      {state.kind === "loading" && <p className="muted">Searching…</p>}
      {state.kind === "error" && <p className="error">Error: {state.message}</p>}

      {state.kind === "done" && state.matches.length === 0 && (
        <p className="muted">
          No song matches “{state.query}”. Titles are matched ignoring case and
          spacing, but not spelling.
        </p>
      )}

      {state.kind === "done" && state.matches.length > 1 && (
        <p className="notice">
          {state.matches.length} songs share this title — showing all of them.
        </p>
      )}

      {state.kind === "done" && state.matches.length > 0 && (
        <ul className="matches">
          {state.matches.map((m) => (
            <li key={m.id}>
              <strong>{m.title}</strong>{" "}
              <span className="muted">({m.id})</span>
              <div className="attrs">
                dance {m.danceability ?? "—"} · energy {m.energy ?? "—"} ·
                tempo {m.tempo ?? "—"} · valence {m.valence ?? "—"} ·
                duration {m.duration_ms ?? "—"} ms
                {m.data_quality.length > 0 && (
                  <span className="flag-inline"> · flags: {m.data_quality.join(", ")}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
