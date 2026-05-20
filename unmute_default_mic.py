from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def unmute_default_mic():
    try:
        device = AudioUtilities.GetMicrophone()
        print("Default Microphone retrieved successfully.")
        
        # Activate volume interface
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        is_muted = volume.GetMute()
        print(f"Current Mute Status: {bool(is_muted)}")
        
        cur_vol = volume.GetMasterVolumeLevelScalar()
        print(f"Current Master Volume Scalar: {cur_vol:.2f}")
        
        if is_muted:
            print("Microphone is muted! Unmuting...")
            volume.SetMute(0, None)
            print("Successfully unmuted.")
            
        if cur_vol < 0.8:
            print(f"Volume is {cur_vol:.2f}, setting to 90%...")
            volume.SetMasterVolumeLevelScalar(0.9, None)
            print("Successfully set volume to 90%.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    unmute_default_mic()
