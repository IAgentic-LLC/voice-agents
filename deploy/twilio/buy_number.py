"""Chapter 15: buy the number this book's outbound calls go out from.

    uv run deploy/twilio/buy_number.py +14155550100

The number given is the one to buy, not a search filter: use
`search.py` first if you do not already know which one you want.
Needs TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, TWILIO_ACCOUNT_SID.
A Standard API key is enough; the master Auth Token is never needed
here or anywhere else in this chapter, on Twilio's own advice against
using it for automation.
"""

import base64
import json
import os
import sys
import urllib.parse
import urllib.request


def buy(number: str) -> dict:
    key = os.environ["TWILIO_API_KEY_SID"]
    secret = os.environ["TWILIO_API_KEY_SECRET"]
    account = os.environ["TWILIO_ACCOUNT_SID"]
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    body = urllib.parse.urlencode({
        "PhoneNumber": number,
        "FriendlyName": "voice-agents-book-ch15",
    }).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account}"
        f"/IncomingPhoneNumbers.json",
        data=body, headers={"Authorization": f"Basic {auth}"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())


if __name__ == "__main__":
    result = buy(sys.argv[1])
    print(f"bought {result['phone_number']}  sid={result['sid']}")
