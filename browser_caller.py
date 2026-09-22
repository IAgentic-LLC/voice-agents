"""Chapter 3: call the agent from a real browser with a recorded "mic".

    uv run --group browser playwright install chromium   # once
    uv run --group browser browser_caller.py --calls 10 --run runs/mine-web

It opens the page from web_server.py in Chromium, with the Chapter 1
question fed in as the microphone, and lets the page measure time to first
audio. The web server and an agent must already be running. The page's
records land in <run>/trials.jsonl, like caller.py's.
"""

import argparse
import tempfile
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

from voicelab import runlog
from voicelab.audio import read_wav, write_wav

QUESTION = "audio/refund_question.wav"
LEAD_S = 3.0  # silence before the question, while the call connects
LISTEN_S = 15.0  # silence after it, while the agent answers


def padded_question(folder: str) -> str:
    """Chromium plays the fake microphone file once from the moment the
    page asks for the microphone, so pad the question with silence."""
    pcm, rate = read_wav(QUESTION)
    lead = np.zeros(int(LEAD_S * rate), dtype=np.int16)
    tail = np.zeros(int(LISTEN_S * rate), dtype=np.int16)
    path = str(Path(folder) / "question-padded.wav")
    write_wav(path, np.concatenate([lead, pcm, tail]), rate)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calls", type=int, default=1)
    parser.add_argument("--agent", default="realtime")
    parser.add_argument("--run", required=True)
    parser.add_argument("--url", default="http://localhost:8000/")
    parser.add_argument("--raw", action="store_true",
                        help="turn off the browser's audio processing")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        wav = padded_question(tmp)
        for n in range(1, args.calls + 1):
            browser = p.chromium.launch(args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={wav}%noloop",
                "--autoplay-policy=no-user-gesture-required",
            ])
            page = browser.new_page()
            page.on("console", lambda m: print(f"  page: {m.text}"))
            query = f"auto=1&agent={args.agent}&run={args.run}"
            if args.raw:
                query += "&raw=1"
            page.goto(f"{args.url}?{query}")
            time.sleep(LEAD_S + 6.8 + LISTEN_S)
            log = page.inner_text("#log")
            print(f"call {n}: {page.inner_text('#status')}")
            measured = (
                "time to first audio", "echo delay", "isSecureContext"
            )
            if not any(m in log for m in measured):
                # The page writes a record only when it measures something,
                # so count a silent call here, or it would vanish.
                runlog.append(f"{args.run}/trials.jsonl", {
                    "source": "browser", "ok": False,
                    "error": "nothing measured", "agent": args.agent,
                })
            browser.close()
            time.sleep(2)


if __name__ == "__main__":
    main()
