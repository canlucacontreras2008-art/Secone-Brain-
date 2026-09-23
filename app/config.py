import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# A PyInstaller-frozen exe's __file__/cwd tricks don't point somewhere
# stable: a --onefile build re-extracts to a fresh temp dir on every single
# launch, so anchoring default paths to that (or trusting whatever cwd the
# exe happened to be double-clicked from) would silently reset the database
# and "forget" .env/credentials.json every run. sys.executable, in a frozen
# build, is the actual exe's own path - stable across launches - so anchor
# there instead. Unfrozen (normal `uvicorn app.main:app` usage), this is
# just the current directory, i.e. unchanged from before.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path.cwd()

load_dotenv(BASE_DIR / ".env")


def _default_path(name: str) -> str:
    return str(BASE_DIR / name)


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("BRAIN_MODEL", "claude-opus-5")
DB_PATH = os.getenv("BRAIN_DB_PATH", _default_path("brain.db"))
MAX_TOOL_ITERATIONS = int(os.getenv("BRAIN_MAX_TOOL_ITERATIONS", "8"))
MEMORY_RECALL_LIMIT = int(os.getenv("BRAIN_MEMORY_RECALL_LIMIT", "6"))

# Google Calendar + Gmail share one OAuth app and one granted token - see
# README "Calendar" / "Gmail" sections for how to get credentials.json.
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", _default_path("credentials.json"))
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", _default_path("token.json"))
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
# Empty means "use the server's own local timezone" - set this if the brain
# runs somewhere (e.g. a cloud box) whose local timezone isn't yours, so
# relative dates ("tomorrow", "next Tuesday") resolve against your timezone
# instead of the server's.
BRAIN_TIMEZONE = os.getenv("BRAIN_TIMEZONE", "")
