# voice-agents

Companion code for *Building Production Voice AI Agents* (Book 5 of the Production AI Agent Engineering series, IAgentic LLC). Every number in the book comes from a command in this repository, and the recorded runs ship with it, so `report.py` reproduces the book's tables with no key and no server.

Each chapter's code is at the tag `chNN-end`, for example `git checkout ch01-end`.

## Reproduce a chapter's tables (no key needed)

```bash
uv sync
uv run report.py runs/ch01-*
uv run timeline.py runs/ch01-cascaded-split
uv run pytest -q
```

## Place your own calls

You need Docker, [uv](https://docs.astral.sh/uv/) and a Gemini API key from Google AI Studio.

```bash
cp .env.example .env        # then paste your key into .env
docker run -d --name livekit -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
  livekit/livekit-server:latest --dev --bind 0.0.0.0 --node-ip 127.0.0.1
uv run realtime_agent.py start          # terminal 1, leave running
uv run caller.py --agent realtime --calls 10 --run runs/mine-realtime
uv run report.py runs/mine-realtime
```

For the cascaded agent, start `uv run cascaded_agent.py start` instead and call it with `--agent cascaded`. Settings are environment variables documented at the top of each file.

## What is here

| File | What it does |
|---|---|
| `realtime_agent.py` | One speech-to-speech model hears and answers (`gemini-3.8-live`). |
| `cascaded_agent.py` | Speech to text, a text model, then text to speech. |
| `caller.py` | A synthetic caller: plays `audio/refund_question.wav` in real time and measures time to first audio. |
| `timeline.py` | Lists what the cascaded agent heard, sent to the model and spoke in each call, in order. |
| `report.py` | Summarizes runs: answered calls with a 95% interval, time to first audio with a bootstrap interval for the median, and stage timings. |
| `web_server.py`, `web/` | Chapter 3: a page for talking to an agent from a browser, and the small server that gives it a room. |
| `browser_caller.py` | Chapter 3: drives a real Chromium with the recorded question as its microphone (`uv run --group browser ...`). |
| `echo_agent.py` | Chapter 3: an agent that only sends back what it hears, to measure the transport with no model. |
| `pauses.py` | Chapter 6: writes the question with a longer or shorter pause in the middle, taking the room tone from the pause itself. |
| `endpoint.py` | Chapter 6: counts the turns each question was split into and when the whole question reached the model; `--stops` and `--events` show one run's detail. |
| `talker_agent.py` | Chapter 7: an agent that says one recorded answer, so barge-in can be measured with no model and no speech service. |
| `say.py` | Chapter 7: records one spoken line with the speech model and keeps it as a WAV file. |
| `bargein.py` | Chapter 7: how long the agent kept talking after the caller cut in, with `--sweep` and `--anatomy`. |
| `voicelab/` | Settings, run records and statistics shared by the scripts. |
| `runs/` | Recorded runs used in the book. |

`audio/refund_question.wav` is a 6.8 second question made with Windows' built-in speech synthesis, 16 kHz mono. `audio/agent_answer.wav`, `audio/interruption.wav` and `audio/backchannel.wav` were each made by one run of `say.py` and are replayed by Chapter 7, so its experiments cost nothing to repeat.

## Costs and limits

Calls use Google's paid or free tier depending on your key. The key used for the book allowed 100 requests a day to each text-to-speech model; a cascaded call makes about two. Check your own limits in Google AI Studio.

## License

MIT, see `LICENSE`.
