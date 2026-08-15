"""In-process smoke tests for the MCP server (fastmcp Client)."""

import asyncio

import pytest

fastmcp = pytest.importorskip("fastmcp")


def _chromium_available() -> bool:
    from playwright.async_api import async_playwright

    async def _check() -> bool:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            return True
        except Exception:
            return False

    return asyncio.run(_check())


requires_chromium = pytest.mark.skipif(
    not _chromium_available(),
    reason="chromium is not available for Playwright",
)


@pytest.mark.asyncio
async def test_tools_are_registered():
    from fastmcp import Client

    from layoutlens.mcp_server import mcp

    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert tools == {
        "audit_accessibility",
        "scan_layout",
        "check_ui",
        "compare_ui",
    }


@pytest.mark.asyncio
async def test_check_ui_reports_missing_key_as_error(tmp_path, monkeypatch):
    """LLM tools return a clear error string instead of crashing keyless."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from fastmcp import Client

    import layoutlens.mcp_server as srv

    srv._lens = None  # reset the cached client so the env change applies
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"fake")

    async with Client(srv.mcp) as client:
        result = await client.call_tool(
            "check_ui", {"url": str(shot), "question": "Is it good?"}
        )
    text = result.content[0].text
    assert text.startswith("error:")
    assert "API key" in text


@pytest.mark.browser
@requires_chromium
@pytest.mark.asyncio
async def test_scan_layout_keyless_end_to_end(tmp_path, monkeypatch):
    """Real chromium, no key: scan_layout returns a compact defect summary."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from fastmcp import Client

    import layoutlens.mcp_server as srv

    srv._lens = None
    page = tmp_path / "defect.html"
    page.write_text(
        "<html><head><title>d</title></head><body>"
        '<div style="width:3000px;height:20px;background:green"></div>'
        "</body></html>"
    )

    async with Client(srv.mcp) as client:
        result = await client.call_tool("scan_layout", {"url": str(page)})
    text = result.content[0].text
    assert text.splitlines()[0].lower().startswith("no")
    assert "page-overflow" in text
    # Compact contract: a defect summary, not a raw report dump.
    assert len(text) < 2000
