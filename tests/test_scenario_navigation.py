"""Navigation expectations must settle before reading document evidence."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from layoutlens import Scenario
from layoutlens.scenarios import runner


@pytest.mark.asyncio
@pytest.mark.parametrize("matches", [True, False])
async def test_url_expectation_waits_before_observing_document(monkeypatch, matches):
    settled = False
    page = SimpleNamespace(
        url="https://example.test/checkout",
        on=Mock(),
        context=SimpleNamespace(
            expose_binding=AsyncMock(), add_init_script=AsyncMock()
        ),
    )

    async def wait_for_url(predicate, **_kwargs):
        nonlocal settled
        settled = True
        if not matches:
            raise PlaywrightTimeout("Navigation did not reach the expected URL")
        page.url = "https://example.test/payment"
        assert predicate(page.url)

    async def evaluate(script):
        if script == runner._OBSERVE:
            if not settled:
                raise PlaywrightError("Execution context was destroyed")
            return {"url": page.url}
        return None

    page.wait_for_url = wait_for_url
    page.evaluate = evaluate

    @asynccontextmanager
    async def open_test_page(*_args, **_kwargs):
        yield page

    monkeypatch.setattr(runner, "open_page", open_test_page)
    report = await Scenario(page.url).expect_url("/payment").run()

    assert settled
    assert report.gate_status == ("pass" if matches else "fail")
    assert not report.incomplete_reasons
    assert report.steps[0].after["url"] == page.url
