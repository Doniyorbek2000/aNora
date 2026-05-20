# build_project.py
# Compiles NORA into a single high-performance standalone Windows Executable (Nora.exe)

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Ensure Unicode output works reliably on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def build():
    print("==================================================")
    print("[NORA] Standalone Executable Build System")
    print("==================================================")
    
    # 1. Ensure pyinstaller is installed
    try:
        import PyInstaller
        print("[INFO] PyInstaller is already installed.")
    except ImportError:
        print("[INFO] PyInstaller not found. Installing via pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 2. Verify main.py exists
    main_path = Path("main.py")
    if not main_path.exists():
        print("[ERROR] main.py not found in the current directory!")
        sys.exit(1)
        
    print("[INFO] Preparing compilation settings...")
    
    # 3. Define hidden imports for FastAPI, Uvicorn, Google GenAI, and standard dependencies
    hidden_imports = [
        "fastapi",
        "uvicorn",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "google.genai",
        "google.generativeai",
        "PIL",
        "pyautogui",
        "pyperclip",
        "numpy",
        "sounddevice",
        "comtypes",
        "pycaw",
        "win10toast",
        "psutil",
        "send2trash",
        "send2trash.plat_win"
    ]
    
    # 4. Construct the PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",             # Compile to a single executable
        "--windowed",            # GUI mode (no console popup window)
        "--name=Nora",           # Output name: Nora.exe
        "--icon=logo.ico",       # Use custom Nora logo
        "--clean"                # Clean cache before build
    ]
    
    # Add hidden imports
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
        
    # Target file
    cmd.append("main.py")
    
    print("\n[INFO] Compiling NORA. This may take a few minutes as it packages all dependencies...")
    print(f"Command: {' '.join(cmd)}\n")
    
    # Run PyInstaller
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n==================================================")
        print("[SUCCESS] COMPILATION SUCCESSFUL!")
        print("==================================================")
        
        exe_path = Path("dist/Nora.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"[INFO] Standalone Executable created successfully: {exe_path.resolve()}")
            print(f"[INFO] Size: {size_mb:.2f} MB")
            print("[INFO] Now you can copy Nora.exe to any Windows PC and double-click to run!")
        else:
            print("[WARNING] PyInstaller succeeded but Nora.exe was not found in dist/")
    else:
        print("\n[ERROR] Compilation failed! Check the log output above.")
        sys.exit(1)

if __name__ == "__main__":
    build()
