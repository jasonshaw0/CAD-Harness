"""Owned subprocesses with live output and cancellable process trees."""

import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time


class Cancelled(RuntimeError):
    pass


def terminate_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_process(args, *, cwd: Path, cancel: threading.Event, timeout=120,
                env=None, stdin=None, on_line=None):
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", **flags)
    messages = queue.Queue()
    def read(stream, name):
        for line in iter(stream.readline, ""):
            messages.put((name, line))
        stream.close()
    readers = [threading.Thread(target=read, args=(stream, name), daemon=True)
               for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr"))]
    for reader in readers:
        reader.start()
    def send_input():
        try:
            if stdin:
                process.stdin.write(stdin)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    threading.Thread(target=send_input, daemon=True).start()
    output = {"stdout": [], "stderr": []}
    started = time.monotonic()
    try:
        while process.poll() is None or any(reader.is_alive() for reader in readers) or not messages.empty():
            if cancel.is_set():
                raise Cancelled("Cancelled by user")
            if time.monotonic() - started > timeout:
                raise subprocess.TimeoutExpired(args[0], timeout)
            try:
                name, line = messages.get(timeout=0.05)
                output[name].append(line)
                if on_line:
                    on_line(name, line)
            except queue.Empty:
                pass
    finally:
        if process.poll() is None:
            terminate_tree(process)
        process.wait()
        for reader in readers:
            reader.join(timeout=1)
    return subprocess.CompletedProcess(args, process.returncode, "".join(output["stdout"]), "".join(output["stderr"]))
