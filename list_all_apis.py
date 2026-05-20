import sounddevice as sd

hostapis = sd.query_hostapis()
devices = sd.query_devices()

print("Available Host APIs:")
for idx, api in enumerate(hostapis):
    print(f"[{idx}] {api.get('name')}")

print("\nAvailable Input Devices:")
for idx, dev in enumerate(devices):
    if dev.get('max_input_channels', 0) > 0:
        api_idx = dev.get('hostapi')
        api_name = hostapis[api_idx].get('name') if api_idx < len(hostapis) else "Unknown"
        print(f"Device {idx}: {dev.get('name')}")
        print(f"  Host API: {api_name}")
        print(f"  Channels: {dev.get('max_input_channels')}")
        print(f"  Default Samplerate: {dev.get('default_samplerate')}")
        print("-" * 40)
