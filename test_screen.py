#!/usr/bin/env python3
print("Testing screen_processor import...")
try:
    from actions.screen_processor import screen_process
    print("✅ Screen processor imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()