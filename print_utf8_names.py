import winreg

def get_reg_raw(key, subkey_path, value_name):
    try:
        with winreg.OpenKey(key, subkey_path) as subkey:
            return winreg.QueryValueEx(subkey, value_name)
    except Exception as e:
        return None

def print_utf8_names():
    root_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
    guids = ["{104fdcbd-e13d-4473-ab53-a87a55a29f26}", "{56d2e788-1dbc-48f4-8843-a8d8fdc7d422}", "{92e9d473-beae-4d72-91ab-1f95d92a1f0d}"]
    for guid in guids:
        properties_path = f"{root_path}\\{guid}\\Properties"
        res = get_reg_raw(winreg.HKEY_LOCAL_MACHINE, properties_path, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")
        if res:
            val, vtype = res
            print(f"GUID: {guid}")
            print(f"  Type: {vtype}")
            print(f"  Repr: {repr(val)}")
            if isinstance(val, str):
                print(f"  Bytes from string (utf-8): {list(val.encode('utf-8'))}")
                # Try decoding string using other encodings
                try:
                    raw_bytes = val.encode('cp1251', errors='ignore')
                    print(f"  Decoded from cp1251: {raw_bytes.decode('cp1251')}")
                except Exception:
                    pass

if __name__ == "__main__":
    print_utf8_names()
