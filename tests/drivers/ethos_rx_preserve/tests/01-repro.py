#!/usr/bin/env python3
"""
Local red-test harness for RIOT #22606.

Usage:
    python3 tests/01-repro.py /path/to/tests_ethos_rx_preserve.elf

Expected on current buggy master:
    FAIL: queued DATA was lost after TEXT header

Expected after the fix:
    PASS: queued DATA survived TEXT header
"""
import os
import pty
import re
import sys
import time

try:
    import pexpect
except ImportError:
    print("error: python3-pexpect is required", file=sys.stderr)
    sys.exit(2)


DATA_FRAME = bytes([
    0x7E,             # frame start
    0xAA, 0xBB, 0xCC, 0xDD,
    0x7E,             # frame end (stored in inbuf)
])

TEXT_HEADER = bytes([
    0x7E,             # frame start
    0x7D,             # ESC
    0x21,             # ETHOS_FRAME_TYPE_TEXT (0x01) ^ 0x20
])

STATUS_RE = re.compile(
    r"ETHOS_TEST pending=(\d+) held=(\d+) state=(\d+) type=(\d+)"
)


def status(child):
    child.sendline("ethos_status")
    child.expect(STATUS_RE)
    return tuple(int(child.match.group(i)) for i in range(1, 5))


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <native-elf>", file=sys.stderr)
        return 2

    elf = os.path.abspath(sys.argv[1])
    if not os.path.isfile(elf):
        print(f"error: ELF not found: {elf}", file=sys.stderr)
        return 2

    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)

    print(f"[host] UART PTY: {slave_name}")
    child = pexpect.spawn(
        elf,
        ["-c", slave_name],
        encoding="utf-8",
        timeout=10,
    )
    child.logfile_read = sys.stdout

    try:
        child.expect_exact("Initialization successful - starting the shell now")

        child.sendline("ethos_hold 1")
        child.expect_exact("ETHOS_TEST hold=1")

        # Queue one complete DATA frame. The test callback intentionally does
        # not call recv(), so those bytes must remain in ethos.inbuf.
        os.write(master_fd, DATA_FRAME)
        child.expect(r"ETHOS_TEST RX_HELD 1")

        before = status(child)
        before_pending, before_held, before_state, before_type = before

        print(
            f"[host] before TEXT: pending={before_pending}, "
            f"held={before_held}, state={before_state}, type={before_type}"
        )

        # Start a TEXT frame but do not finish it. Once its type marker has
        # been parsed, state==IN_FRAME and type==TEXT. This gives us a
        # deterministic observation point without timing the network thread.
        os.write(master_fd, TEXT_HEADER)

        after = None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            cur = status(child)
            # line_state_t: WAIT_FRAMESTART=0, IN_FRAME=1, IN_ESCAPE=2
            # ETHOS_FRAME_TYPE_TEXT=1
            if cur[2] == 1 and cur[3] == 1:
                after = cur
                break
            time.sleep(0.01)

        if after is None:
            print("FAIL: TEXT header was not observed by the ETHOS parser")
            return 1

        after_pending, after_held, after_state, after_type = after
        print(
            f"[host] after TEXT: pending={after_pending}, "
            f"held={after_held}, state={after_state}, type={after_type}"
        )

        if before_pending <= 0:
            print("FAIL: DATA frame was not queued before TEXT injection")
            return 1

        if after_pending != before_pending:
            print(
                "FAIL: queued DATA was lost after TEXT header "
                f"({before_pending} -> {after_pending})"
            )
            return 1

        print("PASS: queued DATA survived TEXT header")
        return 0

    finally:
        child.close(force=True)
        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    sys.exit(main())
