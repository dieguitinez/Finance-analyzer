import subprocess
import sys

def run_ssh(command):
    try:
        full_command = f'ssh diego@192.168.1.240 "{command}"'
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_ssh(sys.argv[1])
    else:
        run_ssh("journalctl -u nivo-sentinel.service -n 20")
