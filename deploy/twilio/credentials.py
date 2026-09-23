"""Chapter 15: the credential list that authenticates an outbound call.

    uv run deploy/twilio/credentials.py create
    uv run deploy/twilio/credentials.py attach CL... TK...

`create` makes a credential list and one credential inside it, and
writes the username and password straight to a local file, never to
the terminal: a password printed once is a password that has appeared
in a scrollback buffer and a log file forever after. `attach` puts
that credential list on a trunk, which is what makes the trunk accept
authenticated calls from your own SIP outbound trunk.

Needs TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_ACCOUNT_SID.
"""

import base64
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

OUT_PATH = "deploy/oci/.twilio-outbound-creds"


def _post(path: str, fields: dict) -> dict:
    key = os.environ["TWILIO_API_KEY_SID"]
    secret = os.environ["TWILIO_API_KEY_SECRET"]
    account = os.environ["TWILIO_ACCOUNT_SID"]
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account}/{path}",
        data=body, headers={"Authorization": f"Basic {auth}"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())


def create() -> None:
    cl = _post("SIP/CredentialLists.json",
              {"FriendlyName": "voice-agents-book-ch15-outbound"})
    username = "voiceagents" + secrets.token_hex(4)
    password = secrets.token_urlsafe(24)
    _post(f"SIP/CredentialLists/{cl['sid']}/Credentials.json",
         {"Username": username, "Password": password})
    with open(OUT_PATH, "w", encoding="utf8") as f:
        f.write(f"CREDENTIAL_LIST_SID={cl['sid']}\n"
                f"SIP_USERNAME={username}\nSIP_PASSWORD={password}\n")
    print(f"credential list {cl['sid']} created")
    print(f"username and password written to {OUT_PATH}, not printed here")


def attach(credential_list_sid: str, trunk_sid: str) -> None:
    import base64 as b64

    key = os.environ["TWILIO_API_KEY_SID"]
    secret = os.environ["TWILIO_API_KEY_SECRET"]
    auth = b64.b64encode(f"{key}:{secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {"CredentialListSid": credential_list_sid}).encode()
    req = urllib.request.Request(
        f"https://trunking.twilio.com/v1/Trunks/{trunk_sid}"
        f"/CredentialLists",
        data=body, headers={"Authorization": f"Basic {auth}"},
        method="POST",
    )
    result = json.loads(urllib.request.urlopen(req).read())
    print(f"attached to trunk {trunk_sid}: {result['sid']}")


if __name__ == "__main__":
    if sys.argv[1] == "create":
        create()
    elif sys.argv[1] == "attach":
        attach(sys.argv[2], sys.argv[3])
