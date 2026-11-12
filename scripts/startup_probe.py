"""
Launch the server the way Claude Desktop does and time its start-up.

Sends initialize, notifications/initialized and tools/list over stdio and
prints the time from spawn to each response, with the server's stderr lines
timestamped from spawn. Standard library only, so any Python can run it.

    python scripts/startup_probe.py                  # Desktop's uv command
    python scripts/startup_probe.py --cwd C:\\        # launched from elsewhere
    python scripts/startup_probe.py --call           # also time a first tool call
    python scripts/startup_probe.py --hold 20        # keep it open, watching stderr
    python scripts/startup_probe.py -- .venv\\Scripts\\python.exe -m kerykeion_mcp.server
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP_COMMAND = ["uv", "run", "--directory", REPO, "python", "-m", "kerykeion_mcp.server"]
FIRST_CALL = {"name": "get_current_positions", "arguments": {"lat": 51.5, "lng": 0.0, "tz_str": "UTC"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", help="working directory to launch from (default: the current one)")
    parser.add_argument("--call", action="store_true", help="send one tools/call right after tools/list")
    parser.add_argument("--timeout", type=float, default=120, help="seconds to wait for each response")
    parser.add_argument("--hold", type=float, default=0, help="seconds to keep the server open after the last reply")
    parser.add_argument("--quiet", action="store_true", help="don't echo the server's stderr")
    parser.add_argument("command", nargs="*", help="server command (default: Claude Desktop's uv command)")
    args = parser.parse_args()
    command = args.command or DESKTOP_COMMAND

    start = time.perf_counter()
    elapsed = lambda: time.perf_counter() - start
    proc = subprocess.Popen(command, cwd=args.cwd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    replies, stray, arrived, eof = {}, [], threading.Condition(), threading.Event()

    def read_stdout():
        for line in proc.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                stray.append(line)  # anything but JSON-RPC on stdout breaks the protocol
                continue
            with arrived:
                replies[message.get("id")] = (elapsed(), message)
                arrived.notify_all()
        with arrived:  # EOF: the server closed stdout (exited), so stop waiting
            eof.set()
            arrived.notify_all()

    def read_stderr():
        for line in proc.stderr:
            if not args.quiet:
                print(f"  [{elapsed():6.2f}s stderr] {line.decode(errors='replace').rstrip()}")

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=read_stderr, daemon=True).start()

    def send(message):
        proc.stdin.write((json.dumps(message) + "\n").encode())
        proc.stdin.flush()

    def wait(request_id):
        with arrived:
            arrived.wait_for(lambda: request_id in replies or eof.is_set(), timeout=args.timeout)
        return replies.get(request_id)

    def report(label, reply):
        if reply is None:
            try:
                code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                code = None
            print(f"{label}: no reply" + (f" (server exited with code {code})" if code is not None else ""))
            return False
        at, message = reply
        print(f"{label}: {at:.2f}s" + (f"  ERROR {message['error']}" if "error" in message else ""))
        return True

    print(f"command: {' '.join(command)}" + (f"  (cwd {args.cwd})" if args.cwd else ""))
    send({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "startup-probe", "version": "1"}}})
    ok = report("spawn -> initialize reply", wait(0))
    if ok:
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        ok = report("spawn -> tools/list reply", wait(1))
        if ok:
            print(f"tools listed: {len(replies[1][1].get('result', {}).get('tools', []))}")
    if ok and args.call:
        sent = elapsed()
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": FIRST_CALL})
        reply = wait(2)
        if report("spawn -> first tools/call reply", reply):
            print(f"first tools/call took {reply[0] - sent:.2f}s")
    if stray:
        print(f"WARNING: {len(stray)} non-JSON line(s) on stdout, e.g. {stray[0][:120]!r}")

    time.sleep(args.hold)
    proc.stdin.close()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    time.sleep(0.2)  # let the stderr thread print the last lines
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
