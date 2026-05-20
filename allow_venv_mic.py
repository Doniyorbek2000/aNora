import winreg
import sys
from pathlib import Path

def register_executable(exe_path):
    print(f"Registering microphone access for: {exe_path}")
    path_str = str(exe_path)
    if path_str[1] == ':':
        path_str = path_str[0].upper() + path_str[1:]
    hash_path = path_str.replace('\\', '#')
    
    reg_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged\{hash_path}"
    
    try:
        # Create key
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        # Set LastUserAnnotatedLabel to 2 (Allow)
        winreg.SetValueEx(key, "LastUserAnnotatedLabel", 0, winreg.REG_DWORD, 2)
        winreg.CloseKey(key)
        print(f"  Successfully registered: {hash_path}")
    except Exception as e:
        print(f"  Failed to register {exe_path}: {e}")

def main():
    base_dir = Path(__file__).resolve().parent
    venv_python = base_dir / ".venv" / "Scripts" / "python.exe"
    venv_pythonw = base_dir / ".venv" / "Scripts" / "pythonw.exe"
    
    register_executable(venv_python)
    register_executable(venv_pythonw)
    
    sys_exe = Path(sys.executable)
    register_executable(sys_exe)

if __name__ == "__main__":
    main()
