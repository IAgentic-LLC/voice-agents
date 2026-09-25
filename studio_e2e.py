"""Chapter 32: drives the real Studio, in a real browser, end to
end: clicks Run call, waits for the real HTTP response the browser
actually received, and records it.

    uv run --group browser studio_e2e.py runs/ch32-playground dynabook

Needs, already running: the FastAPI backend (`uv run uvicorn
studio_api:app --port 8032`), the frontend dev server (`npm run dev`
inside `studio/`), and a `dynamic_agent.py` worker for the agent
name given, already carrying at least one version.
"""

import sys
import time

from playwright.sync_api import sync_playwright

from voicelab import runlog


def run(run_dir: str, agent: str, base_url: str = "http://localhost:5173",
       timeout_s: float = 45.0) -> dict:
    captured: dict = {}

    def on_response(response):
        if response.request.method == "POST" and "/playground/call" in response.url:
            captured["result"] = response.json()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("response", on_response)
        page.goto(base_url, timeout=15000)
        page.evaluate(f"window.prompt = () => {agent!r}")
        page.get_by_text("+ New agent").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Playground").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Run call").click()

        deadline = time.monotonic() + timeout_s
        while "result" not in captured and time.monotonic() < deadline:
            page.wait_for_timeout(500)
        browser.close()

    result = captured.get("result")
    if result is None:
        result = {"ok": False, "error": "no response observed in the browser"}
    runlog.append(f"{run_dir}/stages.jsonl", {
        "event": "studio playground call", "agent": agent, **result,
    })
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(run(sys.argv[1], sys.argv[2]), indent=2))
