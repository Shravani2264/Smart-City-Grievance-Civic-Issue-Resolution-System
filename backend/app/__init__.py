"""Load backend/.env (KEY=value lines) into the environment so GROQ_API_KEY can live in a file."""
import os

_env = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env):
    with open(_env, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
