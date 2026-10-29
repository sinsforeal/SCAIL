"""python -m bzombie.viewer start|stop|serve [--data DIR] [--port N]"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request

from .data import DEFAULT_DATA
from .server import PORT, serve

TMP = os.environ.get("TEMP") or r"H:\SCAIL\temp"
if TMP.upper().startswith("C:"):
    TMP = r"H:\SCAIL\temp"


def pidfile(port):
    os.makedirs(TMP, exist_ok=True)
    return os.path.join(TMP, "bz_viewer_%d.pid" % port)


def alive(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/options" % port, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start(a):
    if alive(a.port):
        print("already running on http://127.0.0.1:%d/" % a.port)
        return 0
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.isfile(pw):
        exe = pw
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log = open(os.path.join(TMP, "bz_viewer_%d.log" % a.port), "ab")
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    env = dict(os.environ, TEMP=TMP, TMP=TMP, PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([exe, "-m", "bzombie.viewer", "serve", "--data", a.data, "--port", str(a.port)],
                         cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=flags, env=env, close_fds=True)
    with open(pidfile(a.port), "w") as f:
        f.write(str(p.pid))
    for _ in range(50):
        if alive(a.port):
            print("running on http://127.0.0.1:%d/ (pid %d, data %s)" % (a.port, p.pid, a.data))
            return 0
        time.sleep(0.2)
    print("did not come up; see %s" % log.name)
    return 1


def stop(a):
    pf = pidfile(a.port)
    try:
        pid = int(open(pf).read().strip())
    except (OSError, ValueError):
        print("no pid file; nothing to stop")
        return 0
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                   creationflags=0x08000000)
    try:
        os.remove(pf)
    except OSError:
        pass
    for _ in range(25):
        if not alive(a.port):
            print("stopped")
            return 0
        time.sleep(0.2)
    print("still answering after kill")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bzombie.viewer")
    ap.add_argument("cmd", choices=["start", "stop", "serve"])
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args(argv)
    a.data = os.path.abspath(a.data)
    if a.cmd == "serve":
        srv = serve(a.data, a.port)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    return start(a) if a.cmd == "start" else stop(a)


if __name__ == "__main__":
    sys.exit(main())
