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
