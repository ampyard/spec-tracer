import pytest

from conftest import run_tool


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
FC002_FEATURES = ROOT / "tests" / "fixtures" / "fc002" / "features"
FC002_UNIT = ROOT / "tests" / "fixtures" / "fc002" / "unit.xml"
FC002_E2E = ROOT / "tests" / "fixtures" / "fc002" / "e2e.json"
MODULE_FEATURES = ROOT / "tests" / "fixtures" / "module_scope" / "features"
PARSERS_E2E = ROOT / "tests" / "fixtures" / "module_scope" / "parsers_e2e.json"

CONFIGS = [
    {
        "id": "fc002",
        "features": FC002_FEATURES,
        "unit": FC002_UNIT,
        "e2e": FC002_E2E,
    },
    {
        "id": "module_scope",
        "features": MODULE_FEATURES,
        "e2e": {"parsers": [PARSERS_E2E]},
    },
]

_SNAPSHOT_JS = """
() => {
  const rows = [...document.querySelectorAll('.tree-row')].map((el) => ({
    name: el.getAttribute('data-sort-name'),
    completion: el.getAttribute('data-sort-completion'),
    result: el.getAttribute('data-sort-result'),
    status: el.getAttribute('data-sort-status'),
    duration: el.getAttribute('data-sort-duration'),
  }));
  const statTiles = [...document.querySelectorAll('.stat-card strong')]
    .map((el) => el.textContent.trim());
  const health = [...document.querySelectorAll('.health-card')].map((el) => ({
    status: el.className,
    title: (el.querySelector('.health-title') || {}).textContent || null,
    value: (el.querySelector('.health-value') || {}).textContent || null,
    message: (el.querySelector('.health-message') || {}).textContent || null,
  }));
  const tiers = [...document.querySelectorAll('.tier')].map((el) => ({
    name: (el.querySelector('.tier-label strong') || {}).textContent || null,
    count: (el.querySelector('.tier-count') || {}).textContent || null,
  }));
  const steps = [...document.querySelectorAll('.steps li')].map((el) => el.textContent);
  const reqChips = [...document.querySelectorAll('.required-chip')]
    .map((el) => el.className + ' | ' + el.textContent);
  const moduleChips = [...document.querySelectorAll('.module-chip')]
    .map((el) => el.textContent);
  const unlinkedRows = [...document.querySelectorAll('#page-unlinked .table-row')]
    .map((el) => el.textContent.trim());
  return { rows, statTiles, health, tiers, steps, reqChips, moduleChips, unlinkedRows };
}
"""


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # pragma: no cover - environment-dependent
        pytest.skip("playwright is not installed")

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment-dependent
            pytest.skip(f"playwright chromium is not installed: {exc}")
        yield browser
        browser.close()


def _snapshot(browser, html_path):
    def _allow_file_requests(route):
        if route.request.url.startswith("file:"):
            route.continue_()
        else:
            route.abort()

    context = browser.new_context()
    context.route("**/*", _allow_file_requests)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(html_path.as_uri())
    page.wait_for_selector(".stat-card")
    snapshot = page.evaluate(_SNAPSHOT_JS)
    context.close()
    assert not errors, f"page JS errors: {errors}"
    return snapshot


@pytest.mark.parametrize("config", CONFIGS, ids=[c["id"] for c in CONFIGS])
def test_client_browser_render_matches_server_render(config, tmp_path, browser):
    server_html = tmp_path / "report-server.html"
    client_html = tmp_path / "report-client.html"

    server_args = dict(config, render_mode="server")
    client_args = dict(config, render_mode="client")
    for html, args in ((server_html, server_args), (client_html, client_args)):
        result = run_tool(
            args["features"],
            html,
            unit=args.get("unit"),
            integration=args.get("integration"),
            e2e=args.get("e2e"),
            render_mode=args["render_mode"],
        )
        assert result.returncode == 0, result.stderr

    server = _snapshot(browser, server_html)
    client = _snapshot(browser, client_html)

    assert client["rows"] == server["rows"]
    assert client["statTiles"] == server["statTiles"]
    assert client["health"] == server["health"]
    assert client["tiers"] == server["tiers"]
    assert client["steps"] == server["steps"]
    assert client["reqChips"] == server["reqChips"]
    assert client["moduleChips"] == server["moduleChips"]
    assert client["unlinkedRows"] == server["unlinkedRows"]
    assert len(client["rows"]) > 0, "client renderer built no tree rows"