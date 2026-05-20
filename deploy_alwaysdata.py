import paramiko
import time

def deploy():
    host = "ssh-nora1.alwaysdata.net"
    user = "nora1"
    password = "949392250a"

    print("Connecting to Alwaysdata SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)

    commands = [
        "cd ~/www && rm -rf *",
        "cd ~/www && git clone https://github.com/Doniyorbek2000/aNora.git .",
        "pip install fastapi uvicorn pydantic --user",
        "mkdir -p ~/www/tmp && touch ~/www/tmp/restart.txt" # Create tmp and restart Passenger
    ]

    for cmd in commands:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        print("OUT:", stdout.read().decode())
        print("ERR:", stderr.read().decode())

    client.close()
    print("Deployment to AlwaysData finished successfully!")

if __name__ == "__main__":
    deploy()
