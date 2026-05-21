import sys
import os
from core.offline_engine import OfflineNLU, is_online, HAS_SAPI, speak_offline

def test_offline_engine():
    print("=== Testing Offline Engine ===")
    
    # 1. Test Internet Connection Check
    print("\n[1] Checking Network Connectivity...")
    online = is_online()
    print(f"Connection Status: {'ONLINE' if online else 'OFFLINE'}")
    
    # 2. Test SAPI5 Speech Availability
    print("\n[2] Checking Offline TTS (SAPI5)...")
    print(f"SAPI5 Available: {HAS_SAPI}")
    if HAS_SAPI:
        try:
            print("Triggering quick silent/background offline TTS test...")
            # We won't block the main test thread
            speak_offline("Salom, men NORA yordamchingizman. Offline rejim tekshirilmoqda.")
            print("TTS triggered successfully.")
        except Exception as e:
            print(f"TTS Error: {e}")
    else:
        print("TTS SAPI5 not available on this system.")

    # 3. Test Local NLU Command Parsing
    print("\n[3] Testing Offline NLU (Uzbek & English Command Matching)...")
    nlu = OfflineNLU()
    
    test_cases = [
        "Salom NORA",
        "Isming nima?",
        "nimalar qila olasan",
        "Kalkulyatorni och",
        "bloknot och",
        "Open Chrome",
        "ovozni balandlat",
        "tovushni o'chir",
        "yorug'likni 80 ga qo'y",
        "skrinshot ol",
        "kompyuterni qulfla",
        "ish stolini tartibla",
        "samolyot biletlarini qidir",
        "noma'lum buyruq testi"
    ]
    
    for case in test_cases:
        result = nlu.parse_command(case)
        print(f"\nCommand: '{case}'")
        print(f"  Parsed Action: {result.get('action')}")
        print(f"  Params:        {result.get('params')}")
        print(f"  Response Msg:  {result.get('response')}")

if __name__ == "__main__":
    test_offline_engine()
