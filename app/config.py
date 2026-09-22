import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("BRAIN_MODEL", "claude-opus-5")
DB_PATH = os.getenv("BRAIN_DB_PATH", "brain.db")
MAX_TOOL_ITERATIONS = int(os.getenv("BRAIN_MAX_TOOL_ITERATIONS", "8"))
MEMORY_RECALL_LIMIT = int(os.getenv("BRAIN_MEMORY_RECALL_LIMIT", "6"))
