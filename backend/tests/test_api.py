import time

from fastapi.testclient import TestClient

from app.news import NewsSourceError

from .conftest import FakeAnalyzer, FakeNews, Gate, make_client, wait_for_run

REFRESH = {"keywords": ["HR trends", "talent acquisition"], "max_results": 10, "analyze": True}


def refresh(client: TestClient, body: dict = REFRESH) -> dict:
    resp = client.post("/api/runs", json=body)
    assert resp.status_code == 202, resp.text
    return wait_for_run(client, resp.json()["id"])


def test_refresh_stores_dedupes_and_analyzes(
    client: TestClient, news: FakeNews, analyzer: FakeAnalyzer
) -> None:
    run = refresh(client)
    assert run["status"] == "succeeded", run
    assert (run["fetched"], run["new"], run["analyzed"]) == (4, 4, 4)
    assert run["prompt_tokens"] == 40
    page = client.get("/api/articles").json()
    assert page["total"] == 4
    assert {a["analysis_status"] for a in page["items"]} == {"done"}
    # Article 3 came from both keywords but is stored once, credited to the first keyword.
    assert [a["keyword"] for a in page["items"] if a["url"].endswith("/3")] == ["HR trends"]


def test_second_refresh_is_idempotent_and_does_not_reanalyze(client, news, analyzer) -> None:
    refresh(client)
    second = refresh(client)
    assert (second["fetched"], second["new"], second["to_analyze"]) == (4, 0, 0)
    assert len(analyzer.analyzed) == 4
    assert client.get("/api/articles").json()["total"] == 4


def test_refresh_without_analysis_is_first_class(client, news, analyzer) -> None:
    """Regression: the Streamlit app raised KeyError: 'sentiment' when AI analysis was off."""
    run = refresh(client, {**REFRESH, "analyze": False})
    assert run["status"] == "succeeded" and run["phase"] == "done"
    items = client.get("/api/articles").json()["items"]
    assert {a["analysis_status"] for a in items} == {"skipped"}
    assert analyzer.analyzed == []
    insights = client.get("/api/insights").json()
    assert insights["sentiment"]["unanalyzed"] == 4 and insights["avg_relevance"] is None
    # A later refresh with analysis on picks up the skipped articles.
    later = refresh(client)
    assert later["to_analyze"] == 4 and later["analyzed"] == 4


def test_missing_gemini_key_stores_articles_with_warning(settings, news) -> None:
    with make_client(settings, news, None) as client:
        assert client.get("/api/health").json()["gemini_configured"] is False
        run = refresh(client)
    assert run["status"] == "partial"
    assert "GEMINI_API_KEY" in run["warnings"][0]
    assert run["fetched"] == 4


def test_missing_serpapi_key_returns_503(settings) -> None:
    with make_client(settings, None, None) as client:
        resp = client.post("/api/runs", json=REFRESH)
    assert resp.status_code == 503
    assert "SERPAPI_KEY" in resp.json()["detail"]


def test_concurrent_refresh_is_rejected(settings, news) -> None:
    gate = Gate()
    with make_client(settings, news, FakeAnalyzer(gate=gate)) as client:
        first = client.post("/api/runs", json=REFRESH)
        assert first.status_code == 202
        assert client.post("/api/runs", json=REFRESH).status_code == 409
        gate.open = True
        assert wait_for_run(client, first.json()["id"])["status"] == "succeeded"
        assert client.post("/api/runs", json=REFRESH).status_code == 202


def test_partial_failures_are_reported_and_retried(settings, news) -> None:
    news.results = {
        "HR trends": news.results["HR trends"],
        "talent acquisition": NewsSourceError("Invalid API key."),
    }
    with make_client(settings, news, FakeAnalyzer(drop_ids={2})) as client:
        run = refresh(client)
        assert run["status"] == "partial"
        assert run["analyzed"] == 2 and run["analysis_failed"] == 1
        assert any("Invalid API key" in w for w in run["warnings"])
        failed = [
            a
            for a in client.get("/api/articles").json()["items"]
            if a["analysis_status"] == "failed"
        ]
        assert [a["analysis_error"] for a in failed] == ["missing from model output"]
    with make_client(settings, news, FakeAnalyzer()) as client:
        retry = refresh(client)
        assert retry["to_analyze"] == 1 and retry["analyzed"] == 1


def test_all_searches_failing_fails_the_run(settings) -> None:
    news = FakeNews(
        {
            "HR trends": NewsSourceError("quota exceeded"),
            "talent acquisition": NewsSourceError("quota exceeded"),
        }
    )
    with make_client(settings, news, FakeAnalyzer()) as client:
        run = refresh(client)
    assert run["status"] == "failed" and run["error"] == "Every keyword search failed."


def test_interrupted_run_is_reconciled_on_startup(settings, news) -> None:
    gate = Gate()
    with make_client(settings, news, FakeAnalyzer(gate=gate)) as client:
        run_id = client.post("/api/runs", json=REFRESH).json()["id"]
        time.sleep(0.1)
    # Shutdown cancelled the run; a new process must not be blocked by it.
    with make_client(settings, news, FakeAnalyzer()) as client:
        old = client.get(f"/api/runs/{run_id}").json()
        assert old["status"] == "failed"
        assert client.post("/api/runs", json=REFRESH).status_code == 202


def test_keyword_validation(client) -> None:
    assert client.post("/api/runs", json={"keywords": [" ", ""]}).status_code == 422
    assert client.post("/api/runs", json={"keywords": ["x" * 101]}).status_code == 422
    assert client.post("/api/runs", json={"keywords": ["a"], "max_results": 51}).status_code == 422
    assert client.post("/api/runs", json={"keywords": ["a"] * 11}).status_code == 422


def test_keywords_are_normalized_and_split_quota(client, news) -> None:
    resp = client.post(
        "/api/runs", json={"keywords": [" HR  trends ", "hr TRENDS", "Payroll"], "max_results": 15}
    )
    run = wait_for_run(client, resp.json()["id"])
    assert run["keywords"] == ["HR trends", "Payroll"]
    assert sorted(news.calls) == [("HR trends", 8), ("Payroll", 8)]


def test_article_filters_sort_and_search(client, news) -> None:
    refresh(client)
    get = lambda **p: client.get("/api/articles", params=p).json()  # noqa: E731
    assert get(source="SHRM")["total"] == 2
    assert get(min_relevance=7)["total"] == 2  # relevance = id + 4
    assert [a["relevance"] for a in get(sort="relevance")["items"]] == [8, 7, 6, 5]
    assert get(sentiment=["positive", "negative"])["total"] == 2  # ids 3, 2
    assert get(q="story 4")["total"] == 1
    assert get(q="100%")["total"] == 0  # LIKE wildcards are escaped
    page = get(limit=3, offset=3)
    assert len(page["items"]) == 1 and page["total"] == 4
    assert client.get("/api/articles", params={"sort": "random"}).status_code == 422


def test_insights_and_sources(client, news) -> None:
    refresh(client)
    data = client.get("/api/insights", params={"days": 7}).json()
    assert data["total"] == 4 and data["analyzed"] == 4
    assert data["avg_relevance"] == 6.5
    assert sum(data["relevance_histogram"]) == 4 and len(data["relevance_histogram"]) == 10
    assert data["top_themes"][0] == {"name": "Pay Transparency", "count": 4}
    assert {s["name"] for s in data["top_sources"]} == {"HR Dive", "SHRM"}
    assert sum(d["count"] for d in data["daily"]) == 4
    sources = client.get("/api/sources").json()
    assert sources == [{"name": "HR Dive", "count": 2}, {"name": "SHRM", "count": 2}]


def test_security_headers_and_host_allow_list(client) -> None:
    resp = client.get("/api/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_spa_fallback_and_traversal(settings, tmp_path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    settings.frontend_dist = dist
    with make_client(settings, None, None) as client:
        assert "spa" in client.get("/insights").text
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert "nope" not in client.get("/..%2Fsecret.txt").text
        assert client.get("/api/missing").status_code == 404


def test_cross_site_simple_post_is_rejected(client) -> None:
    """A form or text/plain POST from another site cannot start a paid refresh."""
    body = '{"keywords": ["HR trends"]}'
    resp = client.post("/api/runs", content=body, headers={"content-type": "text/plain"})
    assert resp.status_code == 422
    assert client.get("/api/runs").json() == []
