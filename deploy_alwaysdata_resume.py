import paramiko
import sys

# Ensure utf-8 output to avoid Windows console cp1251 crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def deploy():
    host = "ssh-nora1.alwaysdata.net"
    user = "nora1"
    password = "949392250a"

    print("Connecting to Alwaysdata SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)

    commands = [
        "pip install fastapi uvicorn pydantic google-genai --user",
        "cat << 'EOF' > ~/www/passenger_wsgi.py\nimport sys, os\nsys.path.insert(0, os.path.dirname(__file__))\nfrom web_server import app as application\nEOF",
        "mkdir -p ~/www/tmp",
        "touch ~/www/tmp/restart.txt" # This restarts the Passenger app
    ]

    for cmd in commands:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        print("OUT:", out)
        print("ERR:", err)

    client.close()
    print("Deployment to AlwaysData finished successfully!")

if __name__ == "__main__":
    deploy()
