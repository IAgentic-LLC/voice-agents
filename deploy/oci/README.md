# Chapter 15 infrastructure: a self-hosted LiveKit SIP stack on Oracle Cloud

Built 2026-09-23 for the real-number half of Chapter 15. Everything
here is scripted and reproducible; nothing was created by clicking
through the console except the account itself and the API key upload.

## What exists

- **VCN** `voice-agents-sip` (`10.20.0.0/16`), one public subnet
  `voice-agents-sip-public` (`10.20.1.0/24`), internet gateway,
  default route table pointed at it. Created by `provision.py apply`.
- **Instance** `voice-agents-sip`: `VM.Standard.A1.Flex`, 2 OCPU,
  12 GB, Ubuntu 24.04 aarch64, Always Free. Created by `launch.py
  apply`, in `eOvQ:EU-FRANKFURT-1-AD-1`.
  - Public IP: `130.61.18.181`
  - SSH: `ssh -i ~/.ssh/voice_agents_oci ubuntu@130.61.18.181`
- **Firewall, two layers, kept in agreement:**
  - OCI security list: 7880/tcp, 7881/tcp, 7882/udp open to the
    world; 5060 (tcp+udp) and 10000-10020/udp open only to Twilio's
    eight documented SIP CIDRs.
  - The instance's own `iptables` (Ubuntu's OCI image ships one,
    pre-populated, independent of the security list): same scoping,
    applied by `open-ports.sh`. Both must be updated together, or a
    packet the security list allows is dropped here instead, which is
    exactly what happened on the first attempt: SIP and RTP were
    briefly open to the world at this layer while the security list
    restricted them, so only one firewall was actually doing that job.
- **Three containers**, host networking, LiveKit's own recommendation
  for a containerized deployment: `sip-redis` (loopback only),
  `sip-livekit`, `sip-sip`. `use_external_ip: true` on both LiveKit
  services; each found `130.61.18.181` via STUN against
  `global.stun.twilio.com` at startup.
- **API key**: generated fresh for this server, not `devkey`/`secret`.
  Value is in `~/sip/livekit.yaml` and `~/sip/sip-config.yaml` on the
  instance, and nowhere in git.

## Verified working

- `curl http://130.61.18.181:7880/` returns 200 from the public
  internet.
- A raw SIP UDP packet from an allow-listed IP reaches the container
  (confirmed with `tcpdump` on the instance) exactly on schedule with
  the security list and iptables rules being present or absent. A
  bare `OPTIONS` gets no reply, which is expected: nothing answers
  until a trunk and dispatch rule exist.

## Not yet done

- Twilio Elastic SIP Trunk, origination URI, phone number.
- `lk sip inbound create` / `lk sip dispatch create` against this
  server (same commands as Chapter 14, different `--url`).
- A measured call.

## Chapter 35: the Studio itself, running here too

A second, independent compose project, `docker-compose.studio.yml`,
runs `studio_api.py` and `dynamic_agent.py` as real containers on
this same instance, on the same host network as the SIP stack above,
so they reach `127.0.0.1:7880` with no NAT to cross. Brought up with
`docker compose -f docker-compose.studio.yml up -d --build` from
`~/studio` on the instance; the app source and Dockerfile are copied
there by hand (a `git archive HEAD | gzip`, scp'd over), not cloned
from a remote this repository does not yet have.

- **Containers**: `studio-api` (port 8032, bound to `0.0.0.0` but
  only reachable from inside the instance right now, see below) and
  `studio-worker` (`AGENT_NAME=dynabook`, `AGENT_ORG=livedemo`).
- **State**: the registry's SQLite file lives at
  `~/studio/studio-data/registry.db` on the instance's own disk, bind
  mounted into both containers at `/app/runs`, so it survives a
  container restart. Confirmed for real: after `docker restart
  studio-api` and a real `docker kill studio-worker`, a fresh request
  against the API still resolved the exact deployment written before
  either restart.
- **The API is now reachable from the public internet, over real
  HTTPS, at `https://130-61-18-181.sslip.io/`.** Port 8032 itself
  stayed closed; a third compose project, `docker-compose.caddy.yml`,
  runs Caddy on 80/443 (host networking) as the only public path to
  it, proxying to `127.0.0.1:8032`. sslip.io is a free, real
  wildcard-DNS service, `130-61-18-181.sslip.io` resolves to
  `130.61.18.181`, a genuine public A record, so Let's Encrypt's
  HTTP-01 challenge works against it with no domain purchase. Caddy
  requested a real certificate on its own: issuer `Let's Encrypt,
  CN=YE2`, valid `2026-09-25` through `2026-12-24`, confirmed with
  `openssl x509 -noout -issuer -dates` against the live connection,
  not asserted. 80 and 443 were opened on both firewall layers, the
  OCI security list and the instance's `iptables`, the same two-layer
  discipline every other port here already follows. A direct request
  to `130.61.18.181:8032` from outside the instance still times out
  (`curl` exit code 28), confirming the app port itself never became
  public; Caddy is the only way in. Evidence:
  `runs/ch35-public-tls/curl-verbose.txt` and
  `runs/ch35-public-tls/port-8032-not-public.txt`.
- **Real findings, not assumptions**: `google.LLM` and
  `google.beta.GeminiTTS` construction, and `silero.VAD.load`, are
  now warmed once per idle process in `dynamic_agent.py`'s own
  `prewarm`, not rebuilt per call. The synchronous SSL-context cost
  Chapter 34 measured on a different machine did not reproduce here
  at all; what did reproduce, on every call, before the fix, was
  Silero's own ONNX session construction, 143-224ms each time,
  confirmed gone after the fix across three real calls in a row.
- **Killing the worker mid-call breaks that call.** A real,
  precisely-timed `docker kill studio-worker` during an active call
  produced `ok: False, error: "no audible answer"`; there was no
  failover, because there was only the one worker registered for
  `dynabook`. `restart: unless-stopped` did not bring the container
  back either, because Docker treats an operator's own `kill` the
  same as a `stop` for that policy; it only protects against a crash.

## Re-running this from scratch

```bash
uv run deploy/oci/provision.py apply   # network + firewall
uv run deploy/oci/launch.py apply      # instance, retries across ADs
# then copy deploy/oci/{docker-compose.yml,livekit.yaml,sip-config.yaml}
# to ~/sip on the instance and run open-ports.sh, then docker compose up -d
```

`livekit.yaml` and `sip-config.yaml` in this directory have
`__LIVEKIT_KEY__` / `__LIVEKIT_SECRET__` placeholders. Generate a real
pair before filling them in; never reuse the one from this run once
it has been in a chat transcript.
