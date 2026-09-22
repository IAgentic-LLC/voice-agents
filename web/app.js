// Chapter 3: a browser voice call to the agent, with the wait measured.
//
// The page joins a fresh LiveKit room with the microphone, plays the
// agent's audio, and watches both with the browser's audio analysers.
// Time to first audio (TTFA) is the time from the last loud moment of
// your speech to the first loud moment of the agent's answer, measured the
// same way as caller.py in Chapter 1.

const LOUD = 300 / 32768; // the Chapter 1 loudness threshold, as a fraction
const params = new URLSearchParams(location.search);
const agent = params.get("agent") || "realtime";
const run = params.get("run") || "runs/mine-browser";
const auto = params.get("auto") === "1"; // started by browser_caller.py
// raw=1 turns off the browser's echo cancellation, noise suppression and
// automatic gain control, which are on by default (Chapter 3 experiment).
const raw = params.get("raw") === "1";

const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
let room = null;
let timer = null;

function show(line) {
  logEl.textContent += line + "\n";
  console.log(line);
}

function loudness(analyser, buffer) {
  analyser.getFloatTimeDomainData(buffer);
  let sum = 0;
  for (const x of buffer) sum += x * x;
  return Math.sqrt(sum / buffer.length);
}

function analyserFor(ctx, mediaStreamTrack) {
  const source = ctx.createMediaStreamSource(
    new MediaStream([mediaStreamTrack]));
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);
  return analyser;
}

async function start() {
  // Browsers only allow the microphone on secure pages: https, or
  // http://localhost. Anywhere else this is undefined.
  if (!navigator.mediaDevices) {
    statusEl.textContent =
      "No microphone access: this page is not a secure context.";
    show(`isSecureContext = ${window.isSecureContext}`);
    await report({ ok: false, error: "not a secure context",
                   secure: window.isSecureContext });
    return;
  }
  document.getElementById("start").disabled = true;
  statusEl.textContent = "Connecting...";
  const resp = await fetch(
    `/token?agent=${encodeURIComponent(agent)}` +
    `&run=${encodeURIComponent(run)}`);
  const { url, token, room: roomName } = await resp.json();

  room = new LivekitClient.Room();
  const ctx = new AudioContext();
  let agentAnalyser = null;

  room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
    if (track.kind !== "audio") return;
    document.body.appendChild(track.attach()); // play the agent
    agentAnalyser = analyserFor(ctx, track.mediaStreamTrack);
    show("agent audio connected");
  });

  await room.connect(url, token);
  await room.localParticipant.setMicrophoneEnabled(true, raw ? {
    echoCancellation: false, noiseSuppression: false, autoGainControl: false,
  } : undefined);
  await room.startAudio();
  const mic = room.localParticipant.getTrackPublication(
    LivekitClient.Track.Source.Microphone).track;
  const micAnalyser = analyserFor(ctx, mic.mediaStreamTrack);
  statusEl.textContent = `In room ${roomName}. Ask your question.`;
  document.getElementById("stop").disabled = false;

  // Check both sides every 10 ms.
  const buffer = new Float32Array(512);
  let turn = 0, speaking = false, lastLoud = null, answered = true;
  let micOnset = null, echoReported = false;
  timer = setInterval(async () => {
    const now = performance.now();
    if (agent === "echo") {
      // Transport only: from the first loud moment of your speech to the
      // first loud moment of it coming back.
      if (micOnset === null && loudness(micAnalyser, buffer) > LOUD) {
        micOnset = now;
      }
      if (micOnset !== null && !echoReported && agentAnalyser &&
          loudness(agentAnalyser, buffer) > LOUD) {
        echoReported = true;
        const delay = (now - micOnset) / 1000;
        show(`echo delay ${delay.toFixed(3)} s`);
        await report({ ok: true, echo_delay_s: +delay.toFixed(3),
                       room: roomName, agent, raw });
      }
      return;
    }
    if (loudness(micAnalyser, buffer) > LOUD) {
      if (answered) { turn += 1; answered = false; show(`turn ${turn}`); }
      speaking = true;
      lastLoud = now;
    }
    if (agentAnalyser && speaking && !answered &&
        loudness(agentAnalyser, buffer) > LOUD) {
      answered = true;
      speaking = false;
      const ttfa = (now - lastLoud) / 1000;
      show(`turn ${turn}: time to first audio ${ttfa.toFixed(3)} s`);
      await report({ ok: true, turn, ttfa_s: +ttfa.toFixed(3),
                     room: roomName, agent, raw });
    }
  }, 10);
}

async function report(record) {
  await fetch(`/log?run=${encodeURIComponent(run)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "browser", ...record }),
  });
}

async function stop() {
  clearInterval(timer);
  if (room) await room.disconnect();
  statusEl.textContent = "Hung up.";
  document.getElementById("stop").disabled = true;
  document.getElementById("start").disabled = false;
}

document.getElementById("start").onclick = start;
document.getElementById("stop").onclick = stop;
if (auto) start();
