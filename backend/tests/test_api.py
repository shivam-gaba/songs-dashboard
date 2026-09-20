"""HTTP-level tests for the API contract (FastAPI TestClient)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["songs"] == 25


def test_list_default_pagination(client):
    r = client.get("/songs")
    body = r.json()
    assert body["page"] == 1 and body["size"] == 10
    assert body["total"] == 25 and body["total_pages"] == 3
    assert len(body["items"]) == 10


def test_list_second_page_offsets_correctly(client):
    first = client.get("/songs", params={"size": 10, "page": 1}).json()
    second = client.get("/songs", params={"size": 10, "page": 2}).json()
    first_ids = {s["id"] for s in first["items"]}
    second_ids = {s["id"] for s in second["items"]}
    assert first_ids.isdisjoint(second_ids)  # no overlap, nothing skipped


def test_sort_desc_across_full_set(client):
    r = client.get("/songs", params={"sort_by": "tempo", "order": "desc",
                                     "size": 25})
    tempos = [s["tempo"] for s in r.json()["items"] if s["tempo"] is not None]
    assert tempos == sorted(tempos, reverse=True)


def test_invalid_sort_field_is_400(client):
    r = client.get("/songs", params={"sort_by": "bogus"})
    assert r.status_code == 400


def test_invalid_order_is_422(client):
    r = client.get("/songs", params={"order": "sideways"})
    assert r.status_code == 422  # rejected by the query pattern


def test_search_multiple_matches(client):
    r = client.get("/songs/search", params={"title": "perfect"})
    body = r.json()
    assert body["count"] == 2 and len(body["matches"]) == 2


def test_search_no_match_is_200_empty(client):
    r = client.get("/songs/search", params={"title": "zzz"})
    assert r.status_code == 200 and r.json()["count"] == 0


def test_get_by_id_404(client):
    assert client.get("/songs/id/nope").status_code == 404


def test_rate_song_valid(client):
    sid = client.get("/songs").json()["items"][0]["id"]
    r = client.post(f"/songs/{sid}/rating", json={"stars": 5})
    assert r.status_code == 200 and r.json()["rating"] == 5


def test_rate_song_out_of_range_is_422(client):
    sid = client.get("/songs").json()["items"][0]["id"]
    assert client.post(f"/songs/{sid}/rating", json={"stars": 9}).status_code == 422
    assert client.post(f"/songs/{sid}/rating", json={"stars": 0}).status_code == 422


def test_rate_unknown_song_is_404(client):
    assert client.post("/songs/nope/rating", json={"stars": 3}).status_code == 404


def test_duration_stats_excludes_suspect_and_missing(client):
    body = client.get("/stats/duration").json()
    # 3 seconds-not-ms rows are excluded from the honest average.
    assert body["excluded_suspect"] == 3
    assert body["avg_seconds"] is not None
