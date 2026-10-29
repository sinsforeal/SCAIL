"""Hidden launcher for the gateway: `pythonw launch.py` (or start.cmd). Never a visible window."""
import os
import subprocess
import sys

PY = r"C:\Python314\pythonw.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
VAR = r"H:\SCAIL\bzombie\var"


def main():
    os.makedirs(VAR, exist_ok=True)
    os.makedirs(r"H:\SCAIL\temp", exist_ok=True)
    env = dict(os.environ, TEMP=r"H:\SCAIL\temp", TMP=r"H:\SCAIL\temp", PYTHONIOENCODING="utf-8")
    # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP. Never DETACHED_PROCESS: with CREATE_NO_WINDOW it flashed a console (meta 10-22 17:14).
    flags = 0x08000000 | 0x00000200
    subprocess.Popen([PY, os.path.join(HERE, "server.py")] + sys.argv[1:], env=env, cwd=HERE,
                     creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
