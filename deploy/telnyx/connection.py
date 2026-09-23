"""Chapter 16: the same trunk shape, on a second real carrier.

    uv run deploy/telnyx/connection.py profile
    uv run deploy/telnyx/connection.py create
    uv run deploy/telnyx/connection.py destinations US CA DE KE

`profile` prints the account's outbound voice profile: Telnyx creates
one automatically at signup, and an account below Paid may only have
the one, so this reuses it rather than creating a second. `create`
makes a credential connection against that profile and writes its
username and password straight to a local file, never to the
terminal, for the same reason Chapter 15's Twilio credentials script
does. `destinations` widens the profile's whitelisted_destinations,
Telnyx's own equivalent of Twilio's separate Geo Permissions screen:
here it is one field on the profile itself, not another product.

Needs TELNYX_API_KEY.
"""

import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

OUT_PATH = "deploy/oci/.telnyx-outbound-creds"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    key = os.environ["TELNYX_API_KEY"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://api.telnyx.com/v2/{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(e.read().decode())


def default_profile() -> dict:
    """The profile Telnyx creates for every new account, reused rather
    than duplicated: an account below Paid is capped at one."""
    profiles = _req("GET", "outbound_voice_profiles")["data"]
    named = next((p for p in profiles if p["name"] == "Default"), None)
    return named or profiles[0]


def profile() -> None:
    p = default_profile()
    print(f"id: {p['id']}")
    print(f"whitelisted_destinations: {p['whitelisted_destinations']}")
    print(f"connections_count: {p['connections_count']}")


def create() -> None:
    profile_id = default_profile()["id"]
    username = "voiceagentsbook" + secrets.token_hex(4)
    password = secrets.token_urlsafe(24)
    conn = _req("POST", "credential_connections", {
        "connection_name": "voice-agents-book-ch16",
        "user_name": username,
        "password": password,
        "outbound": {"outbound_voice_profile_id": profile_id},
    })["data"]
    with open(OUT_PATH, "w", encoding="utf8") as f:
        f.write(f"TELNYX_CONNECTION_ID={conn['id']}\n"
                f"SIP_USERNAME={username}\nSIP_PASSWORD={password}\n")
    print(f"credential connection {conn['id']} created")
    print(f"username and password written to {OUT_PATH}")
    print("not printed here")


def destinations(codes: list[str]) -> None:
    p = default_profile()
    merged = sorted(set(p["whitelisted_destinations"]) | set(codes))
    updated = _req("PATCH", f"outbound_voice_profiles/{p['id']}",
                   {"whitelisted_destinations": merged})["data"]
    print(f"whitelisted_destinations now: {updated['whitelisted_destinations']}")


if __name__ == "__main__":
    if sys.argv[1] == "profile":
        profile()
    elif sys.argv[1] == "create":
        create()
    elif sys.argv[1] == "destinations":
        destinations(sys.argv[2:])
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
