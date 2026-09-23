import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("BRAIN_MODEL", "claude-opus-5")
DB_PATH = os.getenv("BRAIN_DB_PATH", "brain.db")
MAX_TOOL_ITERATIONS = int(os.getenv("BRAIN_MAX_TOOL_ITERATIONS", "8"))
MEMORY_RECALL_LIMIT = int(os.getenv("BRAIN_MEMORY_RECALL_LIMIT", "6"))

# Google Calendar - see README "Calendar" section for how to get credentials.json.
GOOGLE_CALENDAR_CREDENTIALS_PATH = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "credentials.json")
GOOGLE_CALENDAR_TOKEN_PATH = os.getenv("GOOGLE_CALENDAR_TOKEN_PATH", "token.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
# Empty means "use the server's own local timezone" - set this if the brain
# runs somewhere (e.g. a cloud box) whose local timezone isn't yours, so
# relative dates ("tomorrow", "next Tuesday") resolve against your timezone
# instead of the server's.
BRAIN_TIMEZONE = os.getenv("BRAIN_TIMEZONE", "")
