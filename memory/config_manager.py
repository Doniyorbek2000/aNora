import json
import sys
from pathlib import Path
from typing import Any


def get_base_dir() -> Path:
    """Return the repository root directory.

    When the app is frozen with a bundler like PyInstaller, return the
    executable directory. Otherwise return the project root based on this
    module location.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_KEYS_FILE = "api_keys.json"
CONFIG_FILE = CONFIG_DIR / API_KEYS_FILE


def ensure_config_dir() -> None:
    """Create the config directory if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    """Return True if the API config file exists."""
    return CONFIG_FILE.is_file()


def save_api_keys(gemini_api_key: str) -> None:
    """Save Gemini API key into the JSON config file."""
    ensure_config_dir()

    data = load_api_keys()
    if not isinstance(data, dict):
        data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_api_keys() -> dict[str, str]:
    """Load API keys from the config file.

    Returns an empty dict for missing or invalid config data.
    """
    if not config_exists():
        return {}

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON in {CONFIG_FILE}: {exc}")
    except OSError as exc:
        print(f"❌ Failed to read {CONFIG_FILE}: {exc}")

    return {}


def get_gemini_key() -> str | None:
    """Return the stored Gemini API key, or None if not available."""
    key = load_api_keys().get("gemini_api_key")
    if isinstance(key, str):
        key = key.strip()
        return key or None
    return None


def is_configured() -> bool:
    """Return True when a valid-looking Gemini key is configured."""
    key = get_gemini_key()
    return bool(key and len(key) >= 20)
