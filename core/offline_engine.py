import socket
import re
import threading
import time
import asyncio
import traceback
import sys

# Ensure win32com is importable for SAPI5 TTS
try:
    import win32com.client
    HAS_SAPI = True
except ImportError:
    HAS_SAPI = False

_tts_lock = threading.Lock()

def is_online() -> bool:
    """
    Checks if there is an active internet connection.
    Attempts to resolve google's generative AI host and connect to 8.8.8.8.
    """
    # 1. Quick DNS lookup test
    try:
        socket.gethostbyname("generativelanguage.googleapis.com")
        dns_ok = True
    except socket.gaierror:
        dns_ok = False
        
    if dns_ok:
        return True
        
    # 2. Fallback direct IP connection test
    try:
        # Connect to Google Public DNS on port 53 (DNS)
        s = socket.create_connection(("8.8.8.8", 53), timeout=2.0)
        s.close()
        return True
    except Exception:
        return False

def speak_offline(text: str, ui=None):
    """
    Speaks the given text offline using Windows SAPI5 in a background thread.
    Animates the NORA UI avatar while speaking if the UI is provided.
    """
    if not HAS_SAPI:
        print("[Offline TTS] SAPI5 (win32com) is not available.")
        if ui:
            ui.write_log(f"SYS: SAPI5 TTS is not available on this system.")
        return

    def run():
        with _tts_lock:
            try:
                if ui:
                    # Sync UI state to trigger speaking animations
                    ui.root.after(0, ui.start_speaking)
                
                # Initialize COM in the worker thread
                import pythoncom
                pythoncom.CoInitialize()
                
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                
                # Search for preferred female or language-specific voices
                voices = speaker.GetVoices()
                preferred_voice = None
                for i in range(voices.Count):
                    voice = voices.Item(i)
                    voice_name = voice.GetDescription().lower()
                    # Irina (Russian) or Zira (English) are great default fallbacks
                    if "irina" in voice_name or "zira" in voice_name or "hazel" in voice_name:
                        preferred_voice = voice
                        break
                
                if preferred_voice:
                    speaker.Voice = preferred_voice
                
                speaker.Rate = 1 # Slightly faster for natural speaking
                speaker.Speak(text)
                
                pythoncom.CoUninitialize()
            except Exception as e:
                print(f"[Offline TTS Error] {e}")
            finally:
                if ui:
                    ui.root.after(0, ui.stop_speaking)

    threading.Thread(target=run, daemon=True).start()


class OfflineNLU:
    """
    A robust rule-based Natural Language Understanding (NLU) parser for offline mode.
    Maps Uzbek and English user commands to local NORA system tools.
    """
    
    def __init__(self):
        # App mappings for Uzbek synonyms
        self.app_aliases = {
            "kalkulyator": "Calculator",
            "calculator": "Calculator",
            "bloknot": "Notepad",
            "notepad": "Notepad",
            "brauzer": "Chrome",
            "chrome": "Chrome",
            "telegram": "Telegram",
            "whatsapp": "WhatsApp",
            "spotify": "Spotify",
            "paint": "mspaint",
            "word": "Word",
            "excel": "Excel"
        }

    def parse_command(self, text: str) -> dict:
        """
        Parses user command text and returns a dict with 'action', 'params', and 'response'.
        """
        raw = text.strip()
        cmd = raw.lower()
        
        # 1. Simple greetings & chit-chat
        words = set(re.findall(r"\b\w+\b", cmd))
        if "salom" in cmd or "hello" in words or "hi" in words:
            return {
                "action": "reply",
                "response": "Salom! Men NORAman. Hozirda oflayn rejimdaman, lekin kompyuteringizni boshqarishga doir buyruqlaringizni bajara olaman! Qanday yordam bera olaman?"
            }
            
        if any(w in cmd for w in ["isming nima", "what is your name", "who are you"]):
            return {
                "action": "reply",
                "response": "Mening ismim NORA, sizning shaxsiy sun'iy intellekt yordamchingizman."
            }
            
        if any(w in cmd for w in ["nimalar qila olasan", "nima qila olasan", "what can you do", "yordam ber"]):
            return {
                "action": "reply",
                "response": "Men oflayn rejimda quyidagi amallarni bajara olaman: dasturlarni ochish (masalan: 'bloknotni och'), ovoz va yorug'likni sozlash (masalan: 'ovozni 50 ga qo'y'), ish stolini tozalash yoki tartiblash, fayllar bilan ishlash, eslatmalar o'rnatish va siz bilan suhbatlashish!"
            }
            
        if any(w in cmd for w in ["rahmat", "thanks", "thank you"]):
            return {
                "action": "reply",
                "response": "Arziydi! Har doim sizga yordam berishdan xursandman."
            }
            
        if "xayr" in cmd or "bye" in words or "goodbye" in words:
            return {
                "action": "reply",
                "response": "Xayr! Salomat bo'ling. Ishingiz muvaffaqiyatli bo'lsin!"
            }

        # 2. App Opening Intent
        # Uzbek: "kalkulyatorni och", "bloknot och", "brauzerni ishga tushir"
        # English: "open notepad", "run chrome"
        open_match = re.search(r"(?:och(?:ish)?|ishga\s+tushir|open|run|launch)\s+([a-zA-Z0-9а-яА-ЯёЁ\s_'-]+)", cmd)
        if not open_match:
            # Check reverse pattern: "notepadni och" / "bloknot och"
            open_match = re.search(r"([a-zA-Z0-9а-яА-ЯёЁ\s_'-]+?)(?:ni|nii)?\s*(?:och(?:ish)?|ishga\s+tushir|open|run|launch)$", cmd)
            
        if open_match:
            app_raw = open_match.group(1).strip()
            # Normalize app name
            app_name = self.app_aliases.get(app_raw, app_raw)
            return {
                "action": "open_app",
                "params": {"app_name": app_name},
                "response": f"Xo'p bo'ladi. {app_raw} dasturini ochaman."
            }

        # 3. Volume and Brightness controls (Computer Settings)
        # Volume
        if any(w in cmd for w in ["ovoz", "tovush", "volume"]):
            val_match = re.search(r"(\d+)", cmd)
            target_val = val_match.group(1) if val_match else None
            
            if "ko'tar" in cmd or "baland" in cmd or "up" in cmd or "increase" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "volume_up", "description": "ovozni ko'tarish", "value": target_val or "10"},
                    "response": "Ovoz balandligini ko'taraman."
                }
            elif "past" in cmd or "ko'tar" in cmd or "down" in cmd or "decrease" in cmd or "pasay" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "volume_down", "description": "ovozni pasaytirish", "value": target_val or "10"},
                    "response": "Ovoz balandligini pasaytiraman."
                }
            elif "o'chir" in cmd or "mute" in cmd or "tinch" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "mute", "description": "ovozni o'chirish"},
                    "response": "Ovozni o'chiraman."
                }
            elif "yoq" in cmd or "unmute" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "unmute", "description": "ovozni yoqish"},
                    "response": "Ovozni yoqaman."
                }
            elif target_val:
                return {
                    "action": "computer_settings",
                    "params": {"action": "volume_set", "description": "ovoz darajasi", "value": target_val},
                    "response": f"Ovoz balandligini {target_val} foizga sozlayman."
                }

        # Brightness
        if any(w in cmd for w in ["yorug'", "yorit", "qorayt", "brightness"]):
            val_match = re.search(r"(\d+)", cmd)
            target_val = val_match.group(1) if val_match else None
            
            if "ko'tar" in cmd or "oshir" in cmd or "up" in cmd or "yorit" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "brightness_up", "description": "yorug'likni oshirish", "value": target_val or "10"},
                    "response": "Ekran yorug'ligini oshiraman."
                }
            elif "past" in cmd or "qorayt" in cmd or "down" in cmd:
                return {
                    "action": "computer_settings",
                    "params": {"action": "brightness_down", "description": "yorug'likni pasaytirish", "value": target_val or "10"},
                    "response": "Ekran yorug'ligini pasaytiraman."
                }
            elif target_val:
                return {
                    "action": "computer_settings",
                    "params": {"action": "brightness_set", "description": "yorug'lik darajasi", "value": target_val},
                    "response": f"Ekran yorug'ligini {target_val} foizga sozlayman."
                }

        # Screen controls (fullscreen, lock, screenshots)
        if "skrin" in cmd or "screenshot" in cmd or "rasmga ol" in cmd:
            return {
                "action": "computer_settings",
                "params": {"action": "screenshot", "description": "screenshot olish"},
                "response": "Ekran rasmini olaman."
            }
            
        if "qulfla" in cmd or "lock" in cmd:
            return {
                "action": "computer_settings",
                "params": {"action": "lock", "description": "ekranni qulflash"},
                "response": "Kompyuterni qulflayman."
            }

        # 4. Desktop controls
        if any(w in cmd for w in ["ish stoli", "desktop"]):
            if "tartib" in cmd or "organize" in cmd:
                return {
                    "action": "desktop_control",
                    "params": {"action": "organize"},
                    "response": "Ish stolidagi fayllarni tartiblayman."
                }
            elif "toza" in cmd or "clean" in cmd:
                return {
                    "action": "desktop_control",
                    "params": {"action": "clean"},
                    "response": "Ish stolini tozalayman."
                }
            elif "ko'rsat" in cmd or "list" in cmd:
                return {
                    "action": "desktop_control",
                    "params": {"action": "list"},
                    "response": "Ish stolidagi fayllar ro'yxatini olaman."
                }

        # 5. File Operations
        # Read a file: "faylni o'qi [path]"
        if "o'qi" in cmd or "read" in cmd:
            path_match = re.search(r"(?:o'qi|read)\s+([a-zA-Z0-9\s_'.\\/:-]+)", cmd)
            if path_match:
                return {
                    "action": "file_controller",
                    "params": {"action": "read", "path": path_match.group(1).strip()},
                    "response": f"Faylni o'qiyman: {path_match.group(1)}"
                }

        # 6. CMD commands
        if cmd.startswith("cmd ") or cmd.startswith("terminal "):
            raw_cmd = raw[4:].strip() if cmd.startswith("cmd ") else raw[9:].strip()
            return {
                "action": "cmd_control",
                "params": {"task": f"run command {raw_cmd}", "command": raw_cmd},
                "response": f"Terminalda buyruqni bajaraman: {raw_cmd}"
            }

        # 7. Reminders
        if "eslat" in cmd or "reminder" in cmd:
            # Simple offline reminder alert
            return {
                "action": "reply",
                "response": "Eslatmalar o'rnatish uchun quyidagi formatda yozing: 'eslatma: [sana] [vaqt] [xabar]'. Masalan, 'eslatma: 2026-05-22 14:00 Uyga vazifa'"
            }

        # Online-only tools warning
        if any(w in cmd for w in ["ob-havo", "weather", "samolyot", "bilet", "flight", "youtube", "yutub", "qidir", "search", "google"]):
            return {
                "action": "reply",
                "response": "Kechirasiz, bu amalni bajarish uchun internet aloqasi talab etiladi. Hozirda oflayn rejimdaman."
            }

        # 8. Conversational fallback when command is not recognized
        return {
            "action": "reply",
            "response": "Hozirda oflayn rejimdaman. Ushbu buyruqni oflayn tushuna olmadim. Iltimos, boshqacha buyruq bering (masalan: 'bloknotni och', 'ovozni balandlat', 'ish stolini tartibla')."
        }
