"""Chapter 3: a small web server for talking to an agent from a browser.

    uv run web_server.py                   # then open http://localhost:8000
    uv run web_server.py --host 0.0.0.0    # reachable from other machines

It serves the page in web/, gives each browser a LiveKit access token for a
fresh room, asks the agent to join that room, and appends the page's
measurements to <run>/trials.jsonl. The Gemini key never reaches the
browser: only the agent uses it.
"""

import argparse
import json
import uuid
from pathlib import Path

from aiohttp import web
from livekit import api

from voicelab import config, runlog

WEB = Path(__file__).parent / "web"


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB / "index.html")


async def token(request: web.Request) -> web.Response:
    agent = request.query.get("agent", "realtime")
    run_dir = request.query.get("run", "runs/mine-browser")
    room = f"web-{uuid.uuid4().hex[:8]}"
    jwt = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(f"browser-{uuid.uuid4().hex[:6]}")
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    http_url = config.LIVEKIT_URL.replace("ws", "http", 1)
    async with api.LiveKitAPI(
        http_url, config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET
    ) as lk:
        request = api.CreateAgentDispatchRequest(
            agent_name=agent,
            room=room,
            metadata=json.dumps({"run_dir": run_dir}),
        )
        await lk.agent_dispatch.create_dispatch(request)
    return web.json_response(
        {"url": config.LIVEKIT_URL, "token": jwt, "room": room}
    )


async def log(request: web.Request) -> web.Response:
    run_dir = request.query.get("run", "runs/mine-browser")
    record = await request.json()
    runlog.append(f"{run_dir}/trials.jsonl", record)
    return web.json_response({"ok": True})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = web.Application()
    app.add_routes([
        web.get("/", index),
        web.static("/web", WEB),
        web.get("/token", token),
        web.post("/log", log),
    ])
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
