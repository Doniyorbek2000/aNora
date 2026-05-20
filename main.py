import asyncio
import threading
import json
import re
import sys
import traceback
from pathlib import Path

# Ensure emoji and Unicode output works reliably on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import sounddevice as sd
from google import genai
from google.genai import types
import time 
from ui import NoraUI
from memory.memory_manager import load_memory, update_memory, format_memory_for_prompt
from memory.config_manager import get_gemini_key, is_configured

from agent.task_queue import get_queue

from actions.flight_finder import flight_finder
from actions.open_app         import open_app
from actions.weather_report   import weather_action
from actions.send_message     import send_message
from actions.reminder         import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor import screen_process, auto_screen_analysis, monitor_screen_changes
from actions.youtube_video    import youtube_video
from actions.cmd_control      import cmd_control
from actions.desktop          import desktop_control
from actions.browser_control  import browser_control
from actions.file_controller  import file_controller
from actions.code_helper      import code_helper
from actions.dev_agent        import dev_agent
from actions.web_search       import web_search as web_search_action
from actions.computer_control import computer_control
from actions.game_player      import game_player

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR            = get_base_dir()
PROMPT_PATH         = BASE_DIR / "core" / "prompt.txt"
COMMANDS_FILE       = BASE_DIR / "commands.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

def _get_api_key() -> str:
    api_key = get_gemini_key()
    if not api_key:
        raise RuntimeError(
            "Gemini API key is missing or invalid. "
            "Please enter it in config/api_keys.json or through the UI."
        )
    return api_key

def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are NORA, a reliable and friendly female AI assistant. "
            "Speak gently and clearly, using a warm feminine tone. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_memory_turn_counter  = 0
_memory_turn_lock     = threading.Lock()
_MEMORY_EVERY_N_TURNS = 5
_last_memory_input    = ""


def _update_memory_async(user_text: str, nora_text: str) -> None:
    """
    Multilingual memory updater.
    Model  : gemini-2.5-flash-lite (lowest cost)
    Stage 1: Quick YES/NO check  → ~5 tokens output
    Stage 2: Full extraction     → only if Stage 1 says YES
    Result : ~80% fewer API calls vs original
    """
    global _memory_turn_counter, _last_memory_input

    with _memory_turn_lock:
        _memory_turn_counter += 1
        current_count = _memory_turn_counter

    if current_count % _MEMORY_EVERY_N_TURNS != 0:
        return

    text = user_text.strip()
    if len(text) < 10:
        return
    if text == _last_memory_input:
        return
    _last_memory_input = text

    try:
        import google.generativeai as genai
        genai.configure(api_key=_get_api_key())
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        check = model.generate_content(
            f"Does this message contain personal facts about the user "
            f"(name, age, city, job, hobby, relationship, birthday, preference)? "
            f"Reply only YES or NO.\n\nMessage: {text[:300]}"
        )
        if "YES" not in check.text.upper():
            return

        raw = model.generate_content(
            f"Extract personal facts from this message. Any language.\n"
            f"Return ONLY valid JSON or {{}} if nothing found.\n"
            f"Extract: name, age, birthday, city, job, hobbies, preferences, relationships, language.\n"
            f"Skip: weather, reminders, search results, commands.\n\n"
            f"Format:\n"
            f'{{"identity":{{"name":{{"value":"..."}}}}}}, '
            f'"preferences":{{"hobby":{{"value":"..."}}}}, '
            f'"notes":{{"job":{{"value":"..."}}}}}}\n\n'
            f"Message: {text[:500]}\n\nJSON:"
        ).text.strip()

        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        if not raw or raw == "{}":
            return

        data = json.loads(raw)
        if data:
            update_memory(data)
            print(f"[Memory] ✅ Updated: {list(data.keys())}")

    except json.JSONDecodeError:
        pass
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")


TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the Windows computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
{
    "name": "web_search",
    "description": "Searches the web for any information.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query":  {"type": "STRING", "description": "Search query"},
            "mode":   {"type": "STRING", "description": "search (default) or compare"},
            "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
            "aspect": {"type": "STRING", "description": "price | specs | reviews"}
        },
        "required": ["query"]
    }
},
    {
        "name": "weather_report",
        "description": "Gets real-time weather information for a city.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
    "name": "youtube_video",
    "description": (
        "Controls YouTube. Use for: playing videos, summarizing a video's content, "
        "getting video info, or showing trending videos."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "play | summarize | get_info | trending (default: play)"
            },
            "query":  {"type": "STRING", "description": "Search query for play action"},
            "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
            "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
            "url":    {"type": "STRING", "description": "Video URL for get_info action"},
        },
        "required": []
    }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, describe what's visible, "
            "what's on my computer, check the display, etc. "
            "You have NO visual ability without this tool. "
            "ALWAYS use this when user wants to know what's visible on screen. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {
                    "type": "STRING",
                    "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"
                },
                "text": {
                    "type": "STRING",
                    "description": "The question or instruction about the captured image"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "auto_screen_analysis",
        "description": (
            "Automatically captures and analyzes the current screen content. "
            "Use when you need to see what's currently on the user's screen without asking a specific question. "
            "Perfect for monitoring work progress, checking application states, or understanding user context. "
            "After calling this tool, stay SILENT — vision module will speak directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "question": {
                    "type": "STRING",
                    "description": "Optional custom question about the screen. Default: 'What's currently visible on the computer screen? Describe what you see and any important information.'"
                }
            },
            "required": []
        }
    },
    {
        "name": "monitor_screen_changes",
        "description": (
            "Starts continuous monitoring of screen changes in the background. "
            "Automatically analyzes the screen when significant changes are detected. "
            "Use when user wants you to keep an eye on their screen activity or work progress. "
            "Runs indefinitely until stopped. After starting, confirm activation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "interval_seconds": {
                    "type": "INTEGER",
                    "description": "How often to check for changes (default: 30 seconds)"
                },
                "change_threshold": {
                    "type": "NUMBER",
                    "description": "Sensitivity for detecting changes 0.0-1.0 (default: 0.1, lower = more sensitive)"
                }
            },
            "required": []
        }
    },
    {
    "name": "computer_settings",
    "description": (
        "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
        "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
        "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
        "ALSO use for repeated actions: 'refresh 10 times', 'reload page 5 times' → action: reload_n, value: 10. "
        "Use for ANY single computer control command — even if repeated N times. "
        "NEVER route simple computer commands to agent_task."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action":      {"type": "STRING", "description": "The action to perform (if known). For repeated reload: 'reload_n'"},
            "description": {"type": "STRING", "description": "Natural language description of what to do"},
            "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, number of times, etc."}
        },
        "required": []
    }
},
    {
        "name": "browser_control",
        "description": (
            "Controls the web browser. Use for: opening websites, searching the web, "
            "downloading files, clicking elements, filling forms, scrolling, finding "
            "cheapest products, booking flights, any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | press | download | close"},
                "url":         {"type": "STRING", "description": "URL for go_to or download action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type/download"},
                "text":        {"type": "STRING", "description": "Text to click, type, or download"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "save_as":     {"type": "STRING", "description": "Filename to save a download as (optional)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": (
            "Manages files and folders. Use for: listing files, creating/deleting/moving/copying "
            "files, reading file contents, finding files by name or extension, checking disk usage, "
            "organizing the desktop, getting file info."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "cmd_control",
        "description": (
            "Runs CMD/terminal commands by understanding natural language. "
            "Use when user wants to: find large files, check disk space, list processes, "
            "get system info, navigate folders, check network, find files by name, "
            "or do ANYTHING in the command line they don't know how to do themselves."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task":    {"type": "STRING", "description": "Natural language description of what to do. Example: 'find the 10 largest files on C drive'"},
                "visible": {"type": "BOOLEAN", "description": "Open visible CMD window so user can see. Default: true"},
                "command": {"type": "STRING", "description": "Optional: exact command if already known"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "desktop_control",
        "description": (
            "Controls the desktop. Use for: changing wallpaper, organizing desktop files, "
            "cleaning the desktop, listing desktop contents, or ANY other desktop-related task "
            "the user describes in natural language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language description of any desktop task"},
            },
            "required": ["action"]
        }
    },
    {
    "name": "code_helper",
    "description": (
        "Writes, edits, explains, runs, or self-builds code files. "
        "Use for ANY coding request: writing a script, fixing a file, "
        "editing existing code, running a file, or building and testing automatically."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
            "description": {"type": "STRING", "description": "What the code should do, or what change to make"},
            "language":    {"type": "STRING", "description": "Programming language (default: python)"},
            "output_path": {"type": "STRING", "description": "Where to save the file (full path or filename)"},
            "file_path":   {"type": "STRING", "description": "Path to existing file for edit / explain / run / build"},
            "code":        {"type": "STRING", "description": "Raw code string for explain"},
            "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
            "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
        },
        "required": ["action"]
    }
    },
    {
    "name": "dev_agent",
    "description": (
        "Builds complete multi-file projects from scratch. "
        "Plans structure, writes all files, installs dependencies, "
        "opens VSCode, runs the project, and fixes errors automatically. "
        "Use for any project larger than a single script."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description":  {"type": "STRING", "description": "What the project should do"},
            "language":     {"type": "STRING", "description": "Programming language (default: python)"},
            "project_name": {"type": "STRING", "description": "Optional project folder name"},
            "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
        },
        "required": ["description"]
    }
    },
    {
    "name": "agent_task",
    "description": (
        "Executes complex multi-step tasks that require MULTIPLE DIFFERENT tools. "
        "Always respond to the user in the language they spoke. "
        "Examples: 'research X and save to file', 'find files and organize them', "
        "'fill a form on a website', 'write and test code', "
        "'open Telegram and switch to second account', 'navigate app and perform actions', "
        "'open app, find contact, send message', 'complex app navigation tasks'. "
        "USE THIS for: app navigation with multiple steps, account switching, "
        "complex messaging workflows, multi-step computer tasks. "
        "DO NOT use for simple computer commands like volume, refresh, close, scroll, "
        "minimize, screenshot, restart, shutdown — use computer_settings for those. "
        "DO NOT use if the task can be done with a single tool call."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "Complete description of what needs to be accomplished"
            },
            "priority": {
                "type": "STRING",
                "description": "low | normal | high (default: normal)"
            }
        },
        "required": ["goal"]
    }
},
    {
    "name": "computer_control",
    "description": (
        "Direct computer control: type text, click buttons, use keyboard shortcuts, "
        "scroll, move mouse, take screenshots, fill forms, find elements on screen. "
        "Use when the user wants to interact with any app on the computer directly. "
        "Can generate random data for forms or use user's real info from memory."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
            "text":        {"type": "STRING", "description": "Text to type or paste"},
            "x":           {"type": "INTEGER", "description": "X coordinate for click/move"},
            "y":           {"type": "INTEGER", "description": "Y coordinate for click/move"},
            "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
            "key":         {"type": "STRING", "description": "Single key to press e.g. 'enter'"},
            "direction":   {"type": "STRING", "description": "Scroll direction: up | down | left | right"},
            "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
            "seconds":     {"type": "NUMBER", "description": "Seconds to wait"},
            "title":       {"type": "STRING", "description": "Window title for focus_window"},
            "description": {"type": "STRING", "description": "Element description for screen_find/screen_click"},
            "type":        {"type": "STRING", "description": "Data type for random_data: name|email|username|password|phone|birthday|address"},
            "field":       {"type": "STRING", "description": "Field for user_data: name|email|city"},
            "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            "path":        {"type": "STRING", "description": "Save path for screenshot"},
        },
        "required": ["action"]
    }
},

{
    "name": "game_player",
    "description": (
        "Autonomous game playing AI. Can launch games, analyze screens, make decisions, "
        "and play games autonomously. Supports PUBG Mobile and other FPS games. "
        "Use for: starting games, autonomous gameplay, game analysis, AI decision making."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action":           {"type": "STRING", "description": "start | play | analyze | decide | execute | stop"},
            "game_name":        {"type": "STRING", "description": "pubg_mobile | generic_fps (default: pubg_mobile)"},
            "duration_minutes": {"type": "INTEGER", "description": "How long to play autonomously (default: 10)"},
        },
        "required": ["action"]
    }
},

{
    "name": "flight_finder",
    "description": (
        "Searches for flights on Google Flights and speaks the best options. "
        "Use when user asks about flights, plane tickets, uçuş, bilet, etc."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "origin":       {"type": "STRING",  "description": "Departure city or airport code"},
            "destination":  {"type": "STRING",  "description": "Arrival city or airport code"},
            "date":         {"type": "STRING",  "description": "Departure date (any format)"},
            "return_date":  {"type": "STRING",  "description": "Return date for round trips"},
            "passengers":   {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
            "cabin":        {"type": "STRING",  "description": "economy | premium | business | first"},
            "save":         {"type": "BOOLEAN", "description": "Save results to Notepad"},
        },
        "required": ["origin", "destination", "date"]
    }
}
]

class NoraLive:

    def __init__(self, ui: NoraUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._last_command  = ""
        self._last_command_time = 0
        self._command_lock  = threading.Lock()

        # Premium NORA Upgrades
        self.dictation_mode  = False
        self.alwaysdata_url  = "https://nora-remote.alwaysdata.net"
        self.noise_threshold = 15
        self.speak           = True
        self._last_hearing_time = 0.0

        # Intercept UI write_log for real-time Alwaysdata dashboard logs
        from collections import deque
        self.log_queue = deque()
        old_write_log = self.ui.write_log
        def new_write_log(text: str):
            old_write_log(text)
            self.log_queue.append(text)
        self.ui.write_log = new_write_log

        # Load Cloud Server URL from config or default to localhost FastAPI server
        from memory.config_manager import load_api_keys
        config = load_api_keys()
        self.alwaysdata_url = config.get("alwaysdata_url", "http://127.0.0.1:8000").rstrip("/")

    def speak(self, text: str):
        """Thread-safe speak — any thread can call this."""
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
         )

    async def _send_text_command(self, text: str) -> None:
        """Send a text command to the Live session as if the user spoke it."""
        if not self.session:
            return
        text = text.strip()
        if not text:
            return
        self.ui.write_log(f"[File cmd] {text}")
        await self.session.send_client_content(
            turns={"parts": [{"text": text}]},
            turn_complete=True
        )

    async def _watch_command_file(self):
        """Watch commands.txt and send new commands to NORA automatically."""
        last_mtime = 0.0
        while True:
            try:
                if COMMANDS_FILE.exists():
                    stat = COMMANDS_FILE.stat()
                    if stat.st_mtime > last_mtime:
                        last_mtime = stat.st_mtime
                        text = COMMANDS_FILE.read_text(encoding="utf-8").strip()
                        if text:
                            for line in text.splitlines():
                                cmd = line.strip()
                                if cmd:
                                    await self._send_text_command(cmd)
                            COMMANDS_FILE.write_text("", encoding="utf-8")
            except Exception as e:
                print(f"[NORA] ⚠️ Command file watcher error: {e}")
            await asyncio.sleep(2)

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime 

        memory  = load_memory()
        mem_str = format_memory_for_prompt(memory)

        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders. "
            f"If user says 'in 2 minutes', add 2 minutes to this time.\n\n"
        )

        if mem_str:
            sys_prompt = time_ctx + mem_str + "\n\n" + sys_prompt
        else:
            sys_prompt = time_ctx + sys_prompt

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=sys_prompt,
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voiceName="Kore"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[NORA] 🔧 TOOL: {name}  ARGS: {args}")

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(
                    None, lambda: open_app(parameters=args, response=None, player=self.ui)
                )
                result = r or f"Opened {args.get('app_name')} successfully."

            elif name == "weather_report":
                r = await loop.run_in_executor(
                    None, lambda: weather_action(parameters=args, player=self.ui)
                )
                result = r or f"Weather report for {args.get('city')} delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(parameters=args, player=self.ui)
                )
                result = r or "Browser action completed."

            elif name == "file_controller":
                r = await loop.run_in_executor(
                    None, lambda: file_controller(parameters=args, player=self.ui)
                )
                result = r or "File operation completed."

            elif name == "send_message":
                r = await loop.run_in_executor(
                    None, lambda: send_message(
                        parameters=args, response=None,
                        player=self.ui, session_memory=None
                    )
                )
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(
                    None, lambda: reminder(parameters=args, response=None, player=self.ui)
                )
                result = r or f"Reminder set for {args.get('date')} at {args.get('time')}."

            elif name == "youtube_video":
                r = await loop.run_in_executor(
                    None, lambda: youtube_video(parameters=args, response=None, player=self.ui)
                )
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = (
                    "Vision module activated. "
                    "Stay completely silent — vision module will speak directly."
                )

            elif name == "auto_screen_analysis":
                question = args.get("question", "What's currently visible on the computer screen? Describe what you see and any important information.")
                threading.Thread(
                    target=auto_screen_analysis,
                    kwargs={"question": question, "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = (
                    "Automatic screen analysis started. "
                    "Stay completely silent — vision module will speak directly."
                )

            elif name == "monitor_screen_changes":
                interval = args.get("interval_seconds", 30)
                threshold = args.get("change_threshold", 0.1)
                threading.Thread(
                    target=monitor_screen_changes,
                    kwargs={"interval_seconds": interval, "change_threshold": threshold,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = f"Screen monitoring activated with {interval}s intervals and {threshold} sensitivity threshold."

            elif name == "computer_settings":
                r = await loop.run_in_executor(
                    None, lambda: computer_settings(
                        parameters=args, response=None, player=self.ui
                    )
                )
                result = r or "Done."

            elif name == "cmd_control":
                r = await loop.run_in_executor(
                    None, lambda: cmd_control(parameters=args, player=self.ui)
                )
                result = r or "Command executed."

            elif name == "desktop_control":
                r = await loop.run_in_executor(
                    None, lambda: desktop_control(parameters=args, player=self.ui)
                )
                result = r or "Desktop action completed."
            elif name == "code_helper":
                r = await loop.run_in_executor(
                    None, lambda: code_helper(
                        parameters=args,
                        player=self.ui,
                        speak=self.speak 
                    )
                )
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(
                    None, lambda: dev_agent(
                        parameters=args,
                        player=self.ui,
                        speak=self.speak
                    )
                )
                result = r or "Done."
            elif name == "agent_task":
                goal         = args.get("goal", "")
                priority_str = args.get("priority", "normal").lower()

                from agent.task_queue import get_queue, TaskPriority
                priority_map = {
                    "low":    TaskPriority.LOW,
                    "normal": TaskPriority.NORMAL,
                    "high":   TaskPriority.HIGH,
                }
                priority = priority_map.get(priority_str, TaskPriority.NORMAL)

                queue   = get_queue()
                task_id = queue.submit(
                    goal=goal,
                    priority=priority,
                    speak=self.speak,
                )
                result = f"Task started (ID: {task_id}). I'll update you as I make progress."

            elif name == "web_search":
                r = await loop.run_in_executor(
                    None, lambda: web_search_action(parameters=args, player=self.ui)
                    )
                result = r or "Search completed."
            elif name == "computer_control":
                r = await loop.run_in_executor(
                    None, lambda: computer_control(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(
                    None, lambda: flight_finder(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "game_player":
                r = await loop.run_in_executor(
                    None, lambda: game_player(parameters=args, player=self.ui)
                )
                result = r or "Game action completed."

            else:
                result = f"Unknown tool: {name}"
            
        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()

        print(f"[NORA] 📤 {name} → {result[:80]}")

        return types.FunctionResponse(
            id=fc.id,
            name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            audio_data = None

            if isinstance(msg, dict):
                audio_data = msg.get("data")
            elif isinstance(msg, (bytes, bytearray)):
                audio_data = msg

            if audio_data is None:
                print(f"[NORA] ❌ Unexpected audio queue item: {type(msg)}")
                continue

            if not isinstance(audio_data, (bytes, bytearray)):
                audio_data = bytes(audio_data)

            await self.session.send_realtime_input(
                audio={"data": audio_data, "mime_type": "audio/pcm;rate=16000"}
            )

    async def _listen_audio(self):
        print("[NORA] 🎤 Audio capture task started")
        import numpy as np
        loop = asyncio.get_running_loop()
        
        while True:
            audio_data_queue = asyncio.Queue()
            
            def audio_callback(indata, frames, time_info, status):
                if status:
                    print(f"[NORA] 🎤 Audio callback status: {status}")
                try:
                    data_bytes = bytes(indata)
                    loop.call_soon_threadsafe(audio_data_queue.put_nowait, data_bytes)
                except Exception:
                    pass

            stream = None
            opened_idx = None
            opened_channels = None
            opened_sr = None
            
            # Scan devices
            try:
                devices = sd.query_devices()
                device_indices = list(range(len(devices)))
                
                # Prioritize WDM-KS/WASAPI and physical voice-centric microphones
                def get_priority(i):
                    try:
                        dev = devices[i]
                        if dev.get('max_input_channels', 0) <= 0:
                            return -100
                        
                        score = 0
                        # 1. Host API priority
                        api = dev.get('hostapi', 0)
                        if api == 2: # WASAPI
                            score += 40
                        elif api == 1: # DirectSound
                            score += 30
                        elif api == 3: # WDM-KS
                            score -= 20
                            
                        # 2. Name priority (voice vs line/stereo/aux)
                        name_lower = dev.get('name', '').lower()
                        if any(k in name_lower for k in ["mic", "micro", "input", "запис", "микр"]):
                            score += 50
                        if any(k in name_lower for k in ["line", "лин", "stereo", "стерео", "mix", "микш", "aux"]):
                            score -= 25
                            
                        return score
                    except Exception:
                        return -100
                
                sorted_indices = sorted(device_indices, key=get_priority, reverse=True)
                
                for idx in sorted_indices:
                    dev = devices[idx]
                    if dev.get('max_input_channels', 0) <= 0:
                        continue
                    
                    dsr = int(dev.get('default_samplerate', 16000))
                    # Check channels and sample rate combos
                    combos = [
                        (2, dsr),
                        (2, 16000),
                        (1, dsr),
                        (1, 16000)
                    ]
                    
                    success = False
                    for ch, sr in combos:
                        try:
                            stream = sd.RawInputStream(
                                device=idx,
                                samplerate=sr,
                                channels=ch,
                                dtype='int16',
                                blocksize=CHUNK_SIZE,
                                callback=audio_callback
                            )
                            stream.start()
                            await asyncio.sleep(0.1)
                            
                            if stream.active:
                                opened_idx = idx
                                opened_channels = ch
                                opened_sr = sr
                                success = True
                                device_name = dev.get('name', 'Unknown')
                                safe_name = device_name.encode('ascii', errors='replace').decode('ascii')
                                print(f"[NORA] 🎤 Successfully opened Device {idx} ({safe_name}): ch={ch}, sr={sr}")
                                self.ui.write_log(f"SYS: Mikrofon faollashdi ({safe_name})")
                                break
                            else:
                                stream.close()
                        except Exception:
                            if stream:
                                try:
                                    stream.close()
                                except Exception:
                                    pass
                                stream = None
                    if success:
                        break
            except Exception as scan_err:
                print(f"[NORA] ⚠️ Error scanning audio devices: {scan_err}")

            if not stream:
                print("[NORA] ❌ No working audio input device could be initialized. Retrying in 5 seconds...")
                self.ui.write_log("SYS: Mikrofon topilmadi. Qayta ulanish 5 soniyadan keyin...")
                await asyncio.sleep(5.0)
                continue

            # Stream processing loop
            try:
                while stream.active:
                    try:
                        raw_bytes = await audio_data_queue.get()
                        audio_flat = np.frombuffer(raw_bytes, dtype=np.int16)
                        
                        if len(audio_flat) == 0:
                            continue
                            
                        # 1. Mono downmixing
                        if opened_channels == 2:
                            mono_data = audio_flat[0::2]
                        else:
                            mono_data = audio_flat
                            
                        # 2. Linear resampling to 16000Hz if needed
                        if opened_sr != 16000:
                            n_in = len(mono_data)
                            n_out = int(n_in * 16000 / opened_sr)
                            if n_out > 0:
                                x_in = np.arange(n_in)
                                x_out = np.linspace(0, n_in - 1, num=n_out)
                                resampled = np.interp(x_out, x_in, mono_data).astype(np.int16)
                            else:
                                continue
                        else:
                            resampled = mono_data
                            
                        # 3. Dynamic Noise Gate (RMS check)
                        try:
                            rms = np.sqrt(np.mean(resampled.astype(np.float32) ** 2))
                        except Exception:
                            rms = 9999
                            
                        if rms < self.noise_threshold:
                            data_to_send = bytes(len(resampled) * 2)
                            # Revert HEARING to ONLINE after 1.5 seconds of silence
                            if self.ui.status_text == "HEARING" and (time.time() - self._last_hearing_time > 1.5):
                                self.ui.status_text = "ONLINE"
                        else:
                            data_to_send = resampled.tobytes()
                            self._last_hearing_time = time.time()
                            if not self.ui.speaking and self.ui.status_text == "ONLINE":
                                self.ui.status_text = "HEARING"
                            
                        await self.out_queue.put(data_to_send)
                        
                    except asyncio.CancelledError:
                        raise
                    except Exception as inner_err:
                        print(f"[NORA] ⚠️ Audio loop process error: {inner_err}")
                        await asyncio.sleep(0.05)
                        
            except asyncio.CancelledError:
                print("[NORA] 🎤 Audio capture cancelled.")
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                raise
            except Exception as stream_err:
                print(f"[NORA] ❌ Active stream crashed: {stream_err}. Reconnecting...")
                self.ui.write_log("SYS: Mikrofon uzildi, qayta ulanmoqda...")
            finally:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                print("[NORA] 🎤 Stream closed.")
                await asyncio.sleep(2.0)


    async def _receive_audio(self):
        print("[NORA] 👂 Recv started")
        out_buf = []
        in_buf  = []

        try:
            while True:
                turn = self.session.receive()
                async for response in turn:

                    if response.data:
                        if not self.dictation_mode:
                            self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        if sc.turn_complete:
                            full_in  = ""
                            full_out = ""

                            if in_buf:
                                full_in = " ".join(in_buf).strip()
                                if full_in:
                                    self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            if out_buf:
                                full_out = " ".join(out_buf).strip()
                                if full_out and not self.dictation_mode:
                                    self.ui.write_log(f"Nora: {full_out}")
                            out_buf = []

                            # Ovozli Yozish (Dictation Mode) Triggering & Handling
                            lower_in = full_in.lower()
                            if any(kw in lower_in for kw in ["yozishni boshla", "yozishni yoq", "ovozli yozish"]):
                                if not self.dictation_mode:
                                    self.dictation_mode = True
                                    self.ui.write_log("SYS: Ovozli yozish rejimi faollashdi.")
                                    self.speak("Ovozli yozish rejimi yoqildi. Word yoki matn muharririni oching.")
                                full_in = ""
                            elif any(kw in lower_in for kw in ["yozishni to'xtat", "yozishni toxtat", "yozishni o'chir"]):
                                if self.dictation_mode:
                                    self.dictation_mode = False
                                    self.ui.write_log("SYS: Ovozli yozish rejimi o'chirildi.")
                                    self.speak("Ovozli yozish rejimi o'chirildi.")
                                full_in = ""

                            if self.dictation_mode and full_in:
                                import pyperclip
                                import pyautogui
                                old_clip = ""
                                try:
                                    old_clip = pyperclip.paste()
                                except Exception:
                                    pass
                                try:
                                    pyperclip.copy(full_in + " ")
                                    pyautogui.hotkey('ctrl', 'v')
                                    self.ui.write_log(f"[Dictation] Pasted: {full_in}")
                                except Exception as e:
                                    self.ui.write_log(f"[Dictation] Paste error: {e}")
                                try:
                                    if old_clip:
                                        pyperclip.copy(old_clip)
                                except Exception:
                                    pass

                            # Deduplication: prevent processing same command within 3 seconds
                            current_time = time.time()
                            with self._command_lock:
                                if (full_in and len(full_in) > 5 and not self.dictation_mode and 
                                    (full_in != self._last_command or 
                                     current_time - self._last_command_time > 3.0)):
                                    self._last_command = full_in
                                    self._last_command_time = current_time
                                    threading.Thread(
                                        target=_update_memory_async,
                                        args=(full_in, full_out),
                                        daemon=True
                                    ).start()
                                elif full_in and len(full_in) > 5 and not self.dictation_mode:
                                    print(f"[NORA] ⏭️  Skipped duplicate command: {full_in[:50]}...")

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            # Check if this tool call is a duplicate within last 2 seconds
                            tool_key = f"{fc.name}:{str(fc.args) if fc.args else ''}"
                            current_time = time.time()
                            
                            with self._command_lock:
                                if (tool_key != self._last_command or 
                                    current_time - self._last_command_time > 2.0):
                                    self._last_command = tool_key
                                    self._last_command_time = current_time
                                    print(f"[NORA] 📞 Tool call: {fc.name}")
                                    fr = await self._execute_tool(fc)
                                    fn_responses.append(fr)
                                else:
                                    print(f"[NORA] ⏭️  Skipped duplicate tool call: {fc.name}")
                                    
                        if fn_responses:
                            await self.session.send_tool_response(
                                function_responses=fn_responses
                            )

        except Exception as e:
            print(f"[NORA] ❌ Recv error: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[NORA] 🔊 Play started")
        try:
            stream = sd.RawOutputStream(
                samplerate=RECEIVE_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
            )
            stream.start()
        except Exception as e:
            print(f"[NORA] ⚠️ Speaker failed to start: {e}")
            self.ui.write_log("SYS: Speaker initialization failed. Audio output disabled.")
            while True:
                await asyncio.sleep(3600)

        try:
            while True:
                chunk = await self.audio_in_queue.get()
                try:
                    if not self.ui.speaking:
                        self.ui.start_speaking()
                    await asyncio.to_thread(stream.write, chunk)
                    
                    if self.audio_in_queue.empty():
                        await asyncio.sleep(0.15)
                        if self.audio_in_queue.empty():
                            self.ui.stop_speaking()
                except Exception as e:
                    print(f"[NORA] ⚠️ Play chunk error: {e}")
        finally:
            try:
                self.ui.stop_speaking()
            except Exception:
                pass
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass


    async def _poll_web_server(self):
        """Poll the Alwaysdata FastAPI web server for commands and push local NORA logs."""
        print(f"[NORA] Cloud sync polling active for: {self.alwaysdata_url}")
        import requests
        while True:
            try:
                # 1. Post any accumulated local UI logs to the dashboard
                if self.log_queue:
                    logs_to_send = []
                    while self.log_queue:
                        logs_to_send.append(self.log_queue.popleft())
                    
                    def post_logs():
                        try:
                            requests.post(f"{self.alwaysdata_url}/api/post_logs", json={"logs": logs_to_send}, timeout=2)
                        except Exception as e:
                            print(f"[NORA] Cloud log sync failed: {e}")
                            return logs_to_send
                        return None
                        
                    failed_logs = await asyncio.to_thread(post_logs)
                    if failed_logs:
                        # Put back failed logs at the start of queue
                        for l in reversed(failed_logs):
                            self.log_queue.appendleft(l)

                # 2. Get remote commands from the dashboard
                def get_commands():
                    try:
                        res = requests.get(f"{self.alwaysdata_url}/api/get_commands", timeout=2)
                        if res.status_code == 200:
                            return res.json().get("commands", [])
                    except Exception:
                        pass
                    return []

                cmds = await asyncio.to_thread(get_commands)
                for cmd in cmds:
                    if cmd:
                        print(f"[NORA] ☁️ Remote command received: {cmd}")
                        await self._send_text_command(cmd)

            except Exception as e:
                print(f"[NORA] ⚠️ Cloud poll sync error: {e}")
                
            await asyncio.sleep(1.5)

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        while True:
            try:
                print("[NORA] 🔌 Connecting...")
                self.ui.status_text = "CONNECTING"
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop() 
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)

                    print("[NORA] ✅ Connected.")
                    self.ui.status_text = "ONLINE"
                    self.ui.write_log("NORA online.")

                    # Send initial Uzbek greeting
                    await asyncio.sleep(1)  # Brief pause after connection
                    await session.send_client_content(
                        turns={"parts": [{"text": "Salom! Men NORAman, sizning aqlli yordamchingiz. Qanday yordam bera olaman?"}]},
                        turn_complete=True
                    )
                    self.ui.write_log("Nora: Salom! Men NORAman, sizning aqlli yordamchingiz. Qanday yordam bera olaman?")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._watch_command_file())
                    tg.create_task(self._poll_web_server())

            except (Exception, ExceptionGroup) as e:
                print(f"[NORA] ⚠️  Error: {e}")
                self.ui.status_text = "RECONNECTING"
                traceback.print_exc()

            print("[NORA] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)

def main():
    ui = NoraUI("Nora_logo.png")

    def runner():
        ui.wait_for_api_key()
        
        nora = NoraLive(ui)
        try:
            asyncio.run(nora.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()