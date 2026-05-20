import sounddevice as sd

devices = sd.query_devices()
any_ok = False
for idx, dev in enumerate(devices):
    if dev.get('max_input_channels', 0) > 0:
        try:
            stream = sd.RawInputStream(device=idx, samplerate=16000, channels=1, dtype='int16', blocksize=1024)
            stream.start()
            print(f'Device {idx} OK: {dev.get("name")}')
            stream.stop()
            stream.close()
            any_ok = True
        except Exception as e:
            # Also try with default samplerate of this device
            try:
                dsr = int(dev.get('default_samplerate', 16000))
                stream = sd.RawInputStream(device=idx, samplerate=dsr, channels=1, dtype='int16', blocksize=1024)
                stream.start()
                print(f'Device {idx} OK with sample rate {dsr}: {dev.get("name")}')
                stream.stop()
                stream.close()
                any_ok = True
            except Exception as e2:
                print(f'Device {idx} FAILED (both 16000 and {dsr}): {type(e2).__name__}: {e2}')

if not any_ok:
    print('ALL DEVICES FAILED')
