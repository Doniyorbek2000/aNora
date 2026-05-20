import sounddevice as sd
import time

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"Callback status: {status}")
    # Simply do nothing
    pass

devices = sd.query_devices()
any_ok = False
for idx, dev in enumerate(devices):
    if dev.get('max_input_channels', 0) > 0:
        samplerate = int(dev.get('default_samplerate', 16000))
        try:
            # Open stream using a non-blocking callback
            stream = sd.RawInputStream(
                device=idx,
                samplerate=samplerate,
                channels=1,
                dtype='int16',
                blocksize=1024,
                callback=audio_callback
            )
            stream.start()
            print(f"Device {idx} OK (CALLBACK) with sample rate {samplerate}: {dev.get('name')}")
            time.sleep(0.5)
            stream.stop()
            stream.close()
            any_ok = True
        except Exception as e:
            print(f"Device {idx} FAILED (CALLBACK): {type(e).__name__}: {e}")

if not any_ok:
    print("ALL DEVICES FAILED WITH CALLBACK")
