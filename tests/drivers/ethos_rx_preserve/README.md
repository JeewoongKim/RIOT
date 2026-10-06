# RIOT #22606 regression draft

This is a **local red-test draft**, not yet the final upstream test shape.

## Why this test shape

The existing `tests/drivers/ethos` application uses
`test_utils_netdev_eth_minimal`, whose RX_COMPLETE callback immediately calls
`recv()`. That makes it difficult to preserve the exact #22606 state:

1. a complete DATA frame is queued,
2. RX_COMPLETE has happened,
3. the network consumer has deliberately not called `recv()` yet,
4. a TEXT frame header arrives.

This draft wraps the same test utility callback and holds only
`NETDEV_EVENT_RX_COMPLETE`. `NETDEV_EVENT_ISR` is still delegated to RIOT's
existing event-thread path.

The native UART is attached to a host PTY, so bytes are injected into the real
`ethos_isr()` callback instead of a test-only parser API.

## Proposed location

Copy this directory to:

    RIOT/tests/drivers/ethos_rx_preserve/

This is intentionally a separate native-first regression application while we
prove the reproducer. After the red test works, decide with the maintainer
whether to keep it separate or fold the case into `tests/drivers/ethos`.

## Build

From the RIOT checkout:

    make -C tests/drivers/ethos_rx_preserve BOARD=native64 all

RIOT's native CPU exposes only one UART by default, so the draft explicitly
uses `UART_DEV(0)` rather than ETHOS's normal default `UART_DEV(1)`.

## Run the red test

Install pexpect if needed:

    sudo apt install python3-pexpect

Then:

    python3 tests/drivers/ethos_rx_preserve/tests/01-repro.py \
      tests/drivers/ethos_rx_preserve/bin/native64/tests_ethos_rx_preserve.elf

The Python harness creates a PTY and starts the native RIOT binary as:

    <elf> -c /dev/pts/N

The `-c` / `--uart-tty` option binds the first native UART to that PTY.

## Expected behavior

### Current buggy master

The test should fail after the TEXT type marker because the current code resets
`dev->inbuf.reads` and `dev->inbuf.writes`:

    before TEXT: pending=5
    after TEXT:  pending=0
    FAIL: queued DATA was lost after TEXT header

### After the intended fix

The DATA bytes should remain queued:

    before TEXT: pending=5
    after TEXT:  pending=5
    PASS: queued DATA survived TEXT header

## What this test deliberately does NOT test yet

- malformed DATA handling (`_fail_frame()`)
- escaped DATA bytes 0x7d / 0x7e
- HELLO / HELLO_REPLY
- actual simultaneous ISR/thread execution

The first goal is to prove the stronger deterministic invariant:
a completed, unconsumed DATA frame must not be destroyed merely because the
next frame is identified as TEXT.

After this red test is confirmed, add positive compatibility cases for escaped
DATA and HELLO/HELLO_REPLY before changing production code.
