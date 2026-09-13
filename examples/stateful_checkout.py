"""Run a local checkout flow in Chromium, Firefox, and WebKit without an API key."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from layoutlens import Scenario


async def main() -> None:
    with TemporaryDirectory(prefix="layoutlens-checkout-") as directory:
        root = Path(directory)
        (root / "checkout.html").write_text("""<!doctype html>
<html lang="en"><head><title>Checkout</title></head><body>
<label for="email">Email</label><input id="email" type="email">
<button onclick="sessionStorage.setItem('email',document.querySelector('#email').value);
location.href='payment.html'">Continue</button></body></html>""")
        (root / "payment.html").write_text("""<!doctype html>
<html lang="en"><head><title>Payment</title></head><body>
<h1 id="payment">Payment</h1><p id="email"></p><script>
document.querySelector('#email').textContent=sessionStorage.getItem('email');
</script></body></html>""")
        scenario = (
            Scenario(root / "checkout.html")
            .tab()
            .expect_focus("email")
            .type("me@example.com")
            .checkpoint("contact")
            .click("Continue")
            .expect_url("/payment.html")
            .expect_visible("payment")
            .expect_text("email", "me@example.com")
            .checkpoint("payment")
        )
        for browser in ("chromium", "firefox", "webkit"):
            report = await scenario.run(browser=browser, viewport=(1280, 800))
            report.save(root / browser)
            print(f"{browser}: {report.gate_status}, {len(report.events)} events")
            if report.gate_status != "pass":
                raise RuntimeError(report.to_json())


if __name__ == "__main__":
    asyncio.run(main())
