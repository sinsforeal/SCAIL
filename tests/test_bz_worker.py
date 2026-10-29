"""Bench worker helper (watch mode, tombstones, show/list of a gone request) and the harness side that writes tombstones.
Scratch only under H:\\SCAIL\\temp (or the system temp); the live claude_queue is never touched.
python -m unittest tests.test_bz_worker -v"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_scratch = r"H:\SCAIL\temp" if os.path.isdir(r"H:\SCAIL\temp") else None
os.environ.setdefault("BZ_VAR", tempfile.mkdtemp(prefix="bzw_", dir=_scratch))

from bzombie import llm  # noqa: E402
from bzombie.common import VAR, read_json, write_json  # noqa: E402
from tests.bz_safety import refuse_live_var  # noqa: E402

refuse_live_var(VAR)

_spec = importlib.util.spec_from_file_location("worker_io_t", ROOT / "bzombie" / "worker" / "worker_io.py")
wio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wio)


def _req(q, rid, task="sim_him"):
    write_json(q / f"{rid}.req.json", {"req_id": rid, "task": task, "model": "sonnet", "system": "SYS",
                                       "prompt": "PROMPT", "run_id": "r1", "created_wall": time.time()})


class WorkerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bzwq_", dir=_scratch))
        self.q = self.tmp / "claude_queue"
        self.q.mkdir()
        refuse_live_var(self.tmp)
        p = mock.patch.object(wio, "Q", self.q)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_main(self, *argv):
        out = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out):
            try:
                wio.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()


class WatchTests(WorkerBase):
    def start_watch(self, **kw):
        lines, res, stop = [], [], threading.Event()
        t = threading.Thread(target=lambda: res.append(
            wio.watch("t", beat_s=0.1, poll_s=0.02, out=lines.append, stop=stop, **kw)), daemon=True)
        t.start()
        return t, lines, res, stop

    def seen(self):
        return read_json(self.q / "worker.json")["last_seen_wall"]

    def test_heartbeat_advances_while_idle_and_no_exit(self):
        t, lines, res, stop = self.start_watch()
        time.sleep(0.4)
        a = self.seen()
        time.sleep(0.4)
        b = self.seen()
        self.assertGreater(b, a)  # beating by itself
        self.assertTrue(t.is_alive())  # idle: does not exit on its own
        self.assertEqual(lines, [])
        stop.set()
        t.join(2)
        self.assertEqual((lines, res), (["STOP"], [[]]))

    def test_exits_with_req_on_new_request(self):
        t, lines, res, stop = self.start_watch()
        time.sleep(0.25)
        _req(self.q, "aaa111")
        t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(lines, ["REQ aaa111"])
        self.assertEqual(res, [["aaa111"]])

    def test_pending_at_start_exits_but_answered_and_skipped_do_not(self):
        _req(self.q, "done1")
        write_json(self.q / "done1.ans.json", {"req_id": "done1"})  # answered: not pending
        _req(self.q, "skip1")
        code, _ = self.run_main("skip", "skip1")
        self.assertEqual(code, 0)
        t, lines, res, stop = self.start_watch()
        time.sleep(0.3)
        self.assertTrue(t.is_alive())  # nothing to wake for
        _req(self.q, "new1")
        t.join(3)
        self.assertEqual(lines, ["REQ new1"])

    def test_stop_file_exits_cleanly_and_is_removed(self):
        t, lines, res, stop = self.start_watch()
        time.sleep(0.2)
        self.run_main("stop")
        t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(lines, ["STOP"])
        self.assertFalse((self.q / "worker.stop").exists())

    def test_watch_command_wires_args_and_starts_no_child(self):
        _req(self.q, "cmd1")
        with mock.patch("subprocess.Popen") as popen:
            code, out = self.run_main("watch", "--label", "x", "--beat-s", "0.1", "--poll-s", "0.02")
        self.assertEqual((code, out), (0, "REQ cmd1\n"))
        popen.assert_not_called()
        self.assertEqual(read_json(self.q / "worker.json")["session_label"], "x")


class TombstoneReadTests(WorkerBase):
    def test_show_and_model_of_gone_request_report_tombstone(self):
        llm.gone(self.q, "dead01", "timeout", "harness pid 1 run r9", time.time() - 901, "no answer in 900 s",
                 task="judge", run_id="r9")
        for cmd in ("show", "model"):
            code, out = self.run_main(cmd, "dead01")
            self.assertEqual(code, 2)
            self.assertIn("GONE dead01 timeout by harness pid 1 run r9 after 901", out)
            self.assertIn("no answer in 900 s", out)

    def test_show_without_tombstone_says_so(self):
        code, out = self.run_main("show", "nope")
        self.assertEqual(code, 2)
        self.assertIn("GONE nope no request file and no tombstone", out)
        (self.q / "done").mkdir()
        (self.q / "done" / "mv01.req.json.timeout").write_text("{}")
        self.assertIn("moved to done/: mv01.req.json.timeout", self.run_main("show", "mv01")[1])

    def test_show_live_request_unchanged(self):
        _req(self.q, "live01")
        code, out = self.run_main("show", "live01")
        self.assertEqual(code, 0)
        self.assertEqual(out, f"SYS\n\nPROMPT\n\n{wio.TAIL}\n")

    def test_prompt_file_writes_show_output_and_prints_only_path(self):
        write_json(self.q / "pf01.req.json", {"req_id": "pf01", "task": "judge", "model": "sonnet",
                                              "system": "Sé日", "prompt": "line1\nline2", "created_wall": time.time()})
        code, out = self.run_main("prompt-file", "pf01")
        self.assertEqual(code, 0)
        f = self.q / "pf01.prompt.txt"
        self.assertEqual(out.strip(), str(f.resolve()))
        self.assertEqual(len(out.splitlines()), 1)
        self.assertEqual(f.read_bytes().decode("utf-8"), self.run_main("show", "pf01")[1])
        self.assertFalse((self.q / "pf01.prompt.tmp").exists())

    def test_prompt_file_of_gone_request_exits_2_and_drops_stale_file(self):
        (self.q / "gone01.prompt.txt").write_text("stale", encoding="utf-8")
        code, out = self.run_main("prompt-file", "gone01")
        self.assertEqual(code, 2)
        self.assertIn("GONE gone01 no request file and no tombstone", out)
        self.assertFalse((self.q / "gone01.prompt.txt").exists())

    def test_prompt_file_removed_by_answer_skip_and_list_orphan_sweep(self):
        for rid in ("a1", "s1"):
            _req(self.q, rid)
            self.run_main("prompt-file", rid)
            self.assertTrue((self.q / f"{rid}.prompt.txt").exists())
        (self.q / "a1.ans.txt").write_text("reply", encoding="utf-8")
        self.run_main("answer", "a1")
        self.assertFalse((self.q / "a1.prompt.txt").exists())
        self.run_main("skip", "s1")
        self.assertFalse((self.q / "s1.prompt.txt").exists())
        _req(self.q, "live1")
        self.run_main("prompt-file", "live1")
        (self.q / "orph1.prompt.txt").write_text("x", encoding="utf-8")
        self.run_main("list")
        self.assertFalse((self.q / "orph1.prompt.txt").exists())
        self.assertTrue((self.q / "live1.prompt.txt").exists())

    def test_list_reports_recent_gone_not_answered_or_old(self):
        _req(self.q, "p1")
        llm.gone(self.q, "t1", "timeout", "harness pid 1 run r", time.time() - 5, "x", task="him", run_id="r")
        llm.gone(self.q, "a1", "answered", "harness pid 1 run r", time.time() - 5, "x")
        write_json(self.q / "_gone" / "old1.json", {"req_id": "old1", "reason": "timeout", "who": "w",
                                                    "gone_wall": time.time() - 3600, "age_s": 900})
        code, out = self.run_main("list")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("p1 sim_him sonnet"))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("GONE t1 timeout"))
        self.assertTrue((self.q / "worker.json").exists())


class HarnessTombstoneTests(unittest.TestCase):
    """llm._queue writes a tombstone before the request leaves the queue."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bzwh_", dir=_scratch))
        self.q = self.tmp / "claude_queue"
        refuse_live_var(self.tmp)
        for p in (mock.patch.object(llm, "queue_dir", lambda: self.q), mock.patch.object(llm, "POLL_S", 0.02)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        write_json(self.q / "worker.json", {"session_label": "x", "last_seen_wall": time.time()})
        llm.session = None

    def gone_files(self):
        return sorted((self.q / "_gone").glob("*.json"))

    def test_timeout_leaves_tombstone_before_request_moves(self):
        seen = {}
        real_replace = os.replace

        def spy(src, dst):
            if str(src).endswith(".req.json"):
                seen["tombstone_first"] = [p.name for p in (self.q / "_gone").glob("*.json")]
            return real_replace(src, dst)

        with mock.patch.object(llm.os, "replace", spy):
            with self.assertRaises(llm.QueueUnavailable) as cm:
                llm._queue(llm.Session(None, None, 1, "queue", 0.3), "him", "s", "p")
        self.assertEqual(cm.exception.reason, "worker_timeout")
        (f,) = self.gone_files()
        t = read_json(f)
        self.assertEqual((t["reason"], t["task"], t["req_id"]), ("timeout", "sim_him", f.stem))
        self.assertGreaterEqual(t["age_s"], 0.3)
        self.assertIn("pid", t["who"])
        self.assertEqual(seen["tombstone_first"], [f.name])  # written before the req moved to done/
        self.assertTrue((self.q / "done" / f"{f.stem}.req.json.timeout").exists())

    def test_caller_exit_withdraws_with_tombstone(self):
        def boom(_):
            raise KeyboardInterrupt

        with mock.patch.object(llm.time, "sleep", boom):
            with self.assertRaises(KeyboardInterrupt):
                llm._queue(llm.Session(None, None, 1, "queue", 30), "judge", "s", "p")
        (f,) = self.gone_files()
        t = read_json(f)
        self.assertEqual((t["reason"], t["detail"], t["task"]), ("caller_exit", "KeyboardInterrupt", "judge"))
        self.assertEqual(list(self.q.glob("*.req.json")), [])
        self.assertTrue((self.q / "done" / f"{f.stem}.req.json.withdrawn").exists())

    def test_answered_request_gets_answered_tombstone(self):
        stop = threading.Event()

        def worker():
            while not stop.is_set():
                for p in self.q.glob("*.req.json"):
                    rid = p.name[:-len(".req.json")]
                    write_json(self.q / f"{rid}.ans.json", {"req_id": rid, "text": "ok", "is_error": False})
                time.sleep(0.02)

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        try:
            out = llm._queue(llm.Session(None, None, 1, "queue", 10), "him", "s", "p")
        finally:
            stop.set()
            th.join(2)
        self.assertEqual(out, "ok")
        (f,) = self.gone_files()
        self.assertEqual(read_json(f)["reason"], "answered")

    def test_gone_prunes_old_and_never_raises(self):
        d = self.q / "_gone"
        write_json(d / "old.json", {"req_id": "old"})
        old = time.time() - llm.GONE_KEEP_S - 10
        os.utime(d / "old.json", (old, old))
        llm.gone(self.q, "new1", "timeout", "w", time.time())
        self.assertEqual([p.name for p in self.gone_files()], ["new1.json"])
        llm.gone(Path("Z:/no/such/drive/q"), "x", "timeout", "w", time.time())  # OSError swallowed


class SafetyGuardTests(unittest.TestCase):
    def test_refuses_live_var(self):
        for v in (r"H:\SCAIL\bzombie\var", "h:/scail/bzombie/var/"):
            with self.assertRaises(RuntimeError):
                refuse_live_var(v)
        refuse_live_var(r"F:\temp\bzt_x")


if __name__ == "__main__":
    unittest.main()
