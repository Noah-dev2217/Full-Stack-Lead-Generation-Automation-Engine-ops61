"""
OPS-61 SPIKE — Validate Chromium auto-tab-select with ScreenFlow

Tests whether Playwright + Chromium launch flag
`--auto-select-tab-capture-source-by-title` bypasses the native
getDisplayMedia picker when ScreenFlow calls it.

Pass criteria: clicking RECORD in ScreenFlow starts recording immediately
without any native browser picker appearing.

Fail criteria: Chrome shows a native "choose a tab/window/screen" dialog.

Run:
    pip install playwright
    playwright install chromium
    python spike.py
"""

import asyncio
import http.server
import socketserver
import threading
import os
from pathlib import Path
from playwright.async_api import async_playwright

PORT = 8765
ROOT = Path(__file__).parent.resolve()


def serve():
    """Background HTTP server so ScreenFlow loads over http:// (service worker needs this)."""
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    # SO_REUSEADDR so we can restart the spike without socket-in-use errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"[server] serving {ROOT} on http://localhost:{PORT}")
        httpd.serve_forever()


async def main():
    # Start HTTP server in background thread
    server_thread = threading.Thread(target=serve, daemon=True)
    server_thread.start()
    await asyncio.sleep(1)

    async with async_playwright() as p:
        # Launch Chromium with the auto-tab-select flags we're validating.
        # If the spike passes, these are the flags Pipeline 3 will use.
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--auto-select-tab-capture-source-by-title=Prospect-test",
                "--enable-features=AutoSelectTabCaptureSourceByTitle",
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            permissions=["camera", "microphone"],
        )

        # Tab 1: ScreenFlow (the recorder)
        screenflow = await context.new_page()
        await screenflow.goto(f"http://localhost:{PORT}/screenflow/index.html")

        # Tab 2: test prospect page (title="Prospect-test" — matches the flag)
        prospect = await context.new_page()
        await prospect.goto(f"http://localhost:{PORT}/prospect_test.html")

        # Bring ScreenFlow tab back into focus so user clicks Record there
        await screenflow.bring_to_front()

        print()
        print("=" * 64)
        print("  SPIKE READY — manual verification")
        print("=" * 64)
        print()
        print("  Two tabs are open in the Chromium window:")
        print("    1. ScreenFlow (focused)")
        print("    2. Prospect-test (the test prospect page)")
        print()
        print("  In the ScreenFlow tab:")
        print("    1. Open Settings (gear icon)")
        print("    2. Mic: OFF, System Audio: ON")
        print("    3. Click the big RECORD button")
        print()
        print("  PASS:  Recording starts immediately, no picker appears.")
        print("         Recording captures the Prospect-test tab.")
        print()
        print("  FAIL:  Chrome shows a native picker dialog asking")
        print("         which tab/window/screen to share.")
        print()
        print("  Screenshot whichever result you get and post in Discord.")
        print()
        print("  Press Ctrl+C in this terminal when done.")
        print("=" * 64)

        # Keep browser open for manual testing
        try:
            await asyncio.sleep(3600)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

        await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[spike] shutting down")
