# Minimal test
import time
import subprocess
import sys
import platform
import json
import re
from pathlib import Path

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

_OS = platform.system()

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

ACTION_MAP = {"test": lambda: None}

def _detect_action(description: str) -> dict:
    return {"action": "volume_up", "value": None}

def computer_settings(parameters: dict, response=None, player=None, session_memory=None) -> str:
    return "Test"

if __name__ == "__main__":
    print("File loaded successfully")