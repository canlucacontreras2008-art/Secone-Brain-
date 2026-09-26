"""Sets a real timer on the user's Android phone.

There's no cloud API for the stock Clock app - a request has to originate
from something running on the phone itself. MacroDroid (free) bridges that
gap: a webhook trigger receives this request and fires Android's public
`ACTION_SET_TIMER` intent locally. See README "Phone timer" for the
one-time MacroDroid macro setup this depends on.
"""

import urllib.error
import urllib.parse
import urllib.request

from . import config


def set_timer(minutes: float, label: str = "", timeout: float = 10.0) -> dict:
    if not config.MACRODROID_WEBHOOK_URL:
        raise RuntimeError(
            "MACRODROID_WEBHOOK_URL is not configured - see README 'Phone timer' "
            "setup to create the MacroDroid macro and webhook URL."
        )
    seconds = round(minutes * 60)
    query = urllib.parse.urlencode({"timer_seconds": seconds, "timer_label": label})
    url = f"{config.MACRODROID_WEBHOOK_URL}?{query}"
    try:
        urllib.request.urlopen(url, timeout=timeout).read()
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Could not reach the MacroDroid webhook: {exc}") from exc
    return {"minutes": minutes, "label": label}
