"""Stop the gateway: ask it to shut down, else kill the pid in var/bzombie/gateway.pid."""
import os
import subprocess
import sys
import urllib.request

VAR = r"H:\SCAIL\bzombie\var"
PORT = 18330


def main():
    try:
        req = urllib.request.Request("http://127.0.0.1:%d/shutdown" % PORT, data=b"{}", method="POST")
        urllib.request.urlopen(req, timeout=5).read()
        print("gateway stopped")
    except Exception:  # noqa: BLE001
        pid_file = os.path.join(VAR, "gateway.pid")
        pid = open(pid_file).read().strip() if os.path.exists(pid_file) else ""
        if pid:
            subprocess.run(["taskkill", "/F", "/PID", pid], creationflags=0x08000000, capture_output=True)
            print("gateway killed, pid", pid)
        else:
            print("gateway not running")
            return 0
    with open(os.path.join(VAR, "gateway.pid"), "w") as f:  # blank it so a stale pid is never killed
        f.write("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
