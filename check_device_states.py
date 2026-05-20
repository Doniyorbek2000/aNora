import winreg

def get_reg_value(key, subkey_path, value_name):
    try:
        with winreg.OpenKey(key, subkey_path) as subkey:
            val, _ = winreg.QueryValueEx(subkey, value_name)
            return val
    except Exception:
        return None

def check_states():
    root_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
    print("Capture Audio Endpoint States in Windows Registry:")
    
    # State mapping
    states = {
        1: "ACTIVE (Active/Enabled)",
        2: "DISABLED",
        4: "NOTPRESENT",
        8: "UNPLUGGED (Cable disconnected)"
    }
    
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path) as root_key:
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(root_key, i)
                    i += 1
                    
                    device_path = f"{root_path}\\{guid}"
                    state_val = get_reg_value(winreg.HKEY_LOCAL_MACHINE, device_path, "DeviceState")
                    
                    properties_path = f"{device_path}\\Properties"
                    # Friendly name key is typically {a45c254e-df1c-4efd-8020-67d146a850e0},2
                    friendly_name = get_reg_value(winreg.HKEY_LOCAL_MACHINE, properties_path, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")
                    if not friendly_name:
                        friendly_name = "Unknown Device"
                        
                    state_str = states.get(state_val, f"Unknown (value: {state_val})")
                    # Check for combined flags
                    if state_val is not None:
                        flag_strs = []
                        for k, v in states.items():
                            if state_val & k:
                                flag_strs.append(v)
                        if flag_strs:
                            state_str = " | ".join(flag_strs)
                    
                    print(f"- [{guid}]")
                    print(f"  Name: {friendly_name}")
                    print(f"  State: {state_str}")
                except OSError:
                    break
    except Exception as e:
        print(f"Error accessing registry: {e}")

if __name__ == "__main__":
    check_states()
