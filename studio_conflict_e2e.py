"""Chapter 32: a real second writer lands a version behind the
UI's back, then the UI tries to write on top of what it still
thinks is current. Records the real error the interface showed.

    uv run --group browser studio_conflict_e2e.py runs/ch32-conflict dynabook

Needs the same three things running as studio_e2e.py, and at least
one version already written for the given agent.
"""

import sys

import httpx
from playwright.sync_api import sync_playwright

from voicelab import runlog
from voicelab.registry import current_version


def run(run_dir: str, agent: str, studio_db: str = "runs/registry.db",
       base_url: str = "http://localhost:5173") -> dict:
    based_on = current_version(studio_db, agent)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        # Open the editor first, on the version this tab still thinks
        # is current, before the second writer lands its own version.
        page.goto(base_url, timeout=15000)
        page.evaluate(f"window.prompt = () => {agent!r}")
        page.get_by_text("+ New agent").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Editor").click()
        page.wait_for_timeout(300)
        page.fill("textarea", "This version is based on stale data.")
        page.check("input[type=checkbox] >> nth=0")

        background = httpx.post(
            f"http://127.0.0.1:8032/api/agents/{agent}/versions",
            json={
                "instructions": "A second writer got here first.",
                "model": "gemini-3.5-flash-lite", "tools": [],
                "based_on": based_on,
            },
        )
        background.raise_for_status()

        page.get_by_role("button", name=f"Create version {based_on + 1}").click()
        page.wait_for_timeout(1000)
        error_text = page.locator("text=Someone else").inner_text()
        browser.close()

    result = {"background_writer_version": background.json()["version"],
             "ui_error": error_text}
    runlog.append(f"{run_dir}/stages.jsonl", {
        "event": "studio conflict", "agent": agent, **result,
    })
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(run(sys.argv[1], sys.argv[2]), indent=2))
