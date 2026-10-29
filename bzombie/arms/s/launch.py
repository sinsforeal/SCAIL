"""Start one S arm control server hidden (CREATE_NO_WINDOW, pythonw, TEMP=F:\\temp).

    python bzombie/arms/s/launch.py 18331        prints the pid; log in var/bzombie/s_control_<port>.log
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def launch(port, env_extra=None):
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else py
    env = dict(os.environ, TEMP=r"H:\SCAIL\temp", TMP=r"H:\SCAIL\temp", PYTHONIOENCODING="utf-8", **(env_extra or {}))
    logdir = r"H:\SCAIL\bzombie\var"
    os.makedirs(logdir, exist_ok=True)
    log = open(os.path.join(logdir, f"s_control_{port}.log"), "ab")
    p = subprocess.Popen([exe, os.path.join(HERE, "control.py"), "--port", str(port)], cwd=ROOT, env=env,
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return p


if __name__ == "__main__":
    print(launch(int(sys.argv[1])).pid)
