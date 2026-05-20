from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def inspect_mics():
    print("Checking microphones and recording devices via pycaw:")
    try:
        devices = AudioUtilities.GetAllDevices()
        print(f"Total devices found: {len(devices)}")
        for idx, device in enumerate(devices):
            try:
                # We want to print details safely
                friendly_name = getattr(device, "FriendlyName", "Unknown")
                dev_id = getattr(device, "id", "Unknown")
                state = getattr(device, "State", "Unknown")
                
                # Check if it is an input device (microphone) by checking the name or state
                # Usually we want to look at both input and output
                print(f"\n[{idx}] Device: {friendly_name}")
                print(f"  ID: {dev_id}")
                print(f"  State: {state}")
                
                try:
                    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = cast(interface, POINTER(IAudioEndpointVolume))
                    
                    is_muted = volume.GetMute()
                    cur_vol = volume.GetMasterVolumeLevelScalar()
                    print(f"  Is Muted: {bool(is_muted)}")
                    print(f"  Volume Scalar: {cur_vol:.2f}")
                    
                    if is_muted:
                        print("  -> Unmuting device...")
                        volume.SetMute(0, None)
                    if cur_vol < 0.2:
                        print("  -> Setting volume to 90%...")
                        volume.SetMasterVolumeLevelScalar(0.9, None)
                except Exception as inner_err:
                    print(f"  Activate failed: {inner_err}")
            except Exception as item_err:
                print(f"Error printing device {idx}: {item_err}")
    except Exception as outer_err:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_mics()
