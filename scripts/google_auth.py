"""One-time interactive setup for Google Calendar + Gmail access.

Run this once, locally, after downloading credentials.json from the Google
Cloud Console (see README "Calendar" / "Gmail" sections for the full
walkthrough):

    python scripts/google_auth.py

It opens your browser for you to sign in and grant access to both scopes at
once, then saves the resulting token to token.json. After that, the server
reads and silently refreshes that token on its own - this script never
needs to run again unless you revoke access, delete token.json, or add a
new scope in the future.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app import config, google_auth  # noqa: E402


def main() -> None:
    if not os.path.exists(config.GOOGLE_CREDENTIALS_PATH):
        print(
            f"Couldn't find {config.GOOGLE_CREDENTIALS_PATH} - download it from the "
            'Google Cloud Console first (see README "Calendar" section).'
        )
        raise SystemExit(1)

    flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_PATH, google_auth.SCOPES)
    creds = flow.run_local_server(port=0)

    with open(config.GOOGLE_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"Saved {config.GOOGLE_TOKEN_PATH} - the brain can now read/manage your calendar and Gmail.")


if __name__ == "__main__":
    main()
