"""Browser end-to-end tests against the built SPA and the real API with demo providers.

Needs: frontend built (npm run build) and `uv sync --group e2e`. Skips otherwise.
"""

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist" / "index.html"
pytestmark = pytest.mark.skipif(not DIST.is_file(), reason="frontend not built")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    port = free_port()
    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.e2e.demo_server", "--port", str(port), "--db", str(db)],
        cwd=Path(__file__).resolve().parents[2],
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("demo server did not start")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator["playwright.Browser"]:
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    errors: list[str] = []
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    yield page
    page.close()
    assert errors == [], errors


def test_refresh_populates_feed_and_filters_persist_in_url(page, base_url) -> None:
    expect = playwright.expect
    page.goto(base_url)
    expect(page.get_by_role("heading", name="No articles yet")).to_be_visible()

    page.get_by_role("button", name="Refresh news").click()
    expect(page.get_by_role("button", name="Refreshing…")).to_be_disabled()
    expect(page.get_by_role("status").filter(has_text="analyzed")).to_be_visible(timeout=15_000)
    articles = page.locator("main ol.list > li")
    expect(articles.first).to_be_visible()
    total = articles.count()
    assert total >= 5

    page.get_by_label("Negative").check()
    expect(page).to_have_url(f"{base_url}/?sentiment=negative")
    expect(articles).not_to_have_count(total)
    for badge in articles.locator(".sentiment").all_inner_texts():
        assert badge.strip() == "Negative"

    page.reload()
    expect(page.get_by_label("Negative")).to_be_checked()
    page.get_by_role("button", name="Clear filters").first.click()
    expect(articles).to_have_count(total)

    page.get_by_label("Search").fill("overtime")
    expect(articles).to_have_count(1)
    expect(articles.first.get_by_role("link")).to_have_attribute("rel", "noopener noreferrer")


def test_insights_render_with_time_window(page, base_url) -> None:
    expect = playwright.expect
    page.goto(f"{base_url}/insights")
    expect(page.get_by_role("heading", name="Insights")).to_be_visible()
    expect(page.locator(".lede")).to_contain_text("analyzed")
    page.get_by_label("7 days").check()
    expect(page).to_have_url(f"{base_url}/insights?days=7")
    expect(page.get_by_role("heading", name="Top themes")).to_be_visible()
    assert page.title() == "Insights · HR News Intelligence"


def test_mobile_layout_has_no_horizontal_overflow(browser, base_url) -> None:
    page = browser.new_page(viewport={"width": 360, "height": 780})
    for path in ("/", "/insights"):
        page.goto(base_url + path)
        page.wait_for_load_state("networkidle")
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, f"{path} overflows by {overflow}px"
    page.close()


def test_skip_link_and_keyboard_focus(page, base_url) -> None:
    page.goto(base_url)
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.textContent.trim()")
    assert focused == "Skip to content"
    page.keyboard.press("Enter")
    assert page.url.endswith("#main")
