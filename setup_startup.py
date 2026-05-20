import os
import sys
from pathlib import Path

# Set console encoding to UTF-8 to prevent any encoding errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def setup_startup():
    print("Initializing Windows Startup Integration...")
    try:
        # Resolve project root and virtual environment pythonw path
        base_dir = Path(__file__).resolve().parent
        venv_pythonw = base_dir / ".venv" / "Scripts" / "pythonw.exe"
        main_py = base_dir / "main.py"
        
        # Fallback to current executable's directory if venv is missing
        if not venv_pythonw.exists():
            venv_pythonw = Path(sys.executable).parent / "pythonw.exe"
            if not venv_pythonw.exists():
                venv_pythonw = Path("pythonw")

        # Get the standard Windows Startup folder
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA environment variable is missing.")
            
        startup_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_bat = startup_dir / "NoraStartup.bat"
        
        # Create a bat file that starts NORA silently using pythonw.exe (no command prompt window)
        # Sets working directory to project root so assets and configs load flawlessly
        bat_content = f'@echo off\ncd /d "{base_dir}"\nstart "" "{venv_pythonw}" "{main_py}"\n'
        
        startup_bat.write_text(bat_content, encoding="utf-8")
        print("[Startup] OK: Windows Startup shortcut bat created successfully.")
        print(f"[Startup] File: {startup_bat}")
        print(f"[Startup] Target command: {venv_pythonw} {main_py}")
        return True
    except Exception as e:
        print(f"[Startup] ERROR: Failed to register NORA in Windows Startup: {e}")
        return False

if __name__ == "__main__":
    setup_startup()
