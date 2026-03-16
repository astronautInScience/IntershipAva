#!/usr/bin/env python3
"""Run a staged move sequence from an optical trigger and spectrometer pulse."""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import RPi.GPIO as GPIO

# =========================================================
# PIN MAPPING (BCM)
# =========================================================
M1_STEP, M1_DIR = 18, 23   # X axis
M2_STEP, M2_DIR = 5, 6     # Y axis

OPTIC_TRIG_IN = 24         # Optical board trigger -> Pi input
SPEC_TRIG_OUT = 16         # Pi output -> spectrometer trigger

# =========================================================
# DRIVER LOGIC
# ULN2803A (sinking PUL-/DIR-) => INVERTS
# =========================================================
INVERT_STEP = True
INVERT_DIR = True

# =========================================================
# TRIGGER SETTINGS
# =========================================================
OPTIC_TRIGGER_EDGE = GPIO.RISING
TRIGGER_DEBOUNCE_MS = 20
TRIGGER_SETTLE_S = 0.002
TRIGGER_WAIT_TIMEOUT_S: Optional[float] = None

SPEC_ACTIVE_HIGH = True
SPEC_PULSE_US = 5000
MEASUREMENT_TIME_S = 0.050
POST_MOVE_GUARD_S = 0.010

# =========================================================
# MOTION SETTINGS
# =========================================================
STEP_FREQ_HZ = 500
STEP_PULSE_US = 1000
DIR_SETUP_S = 0.002


@dataclass(frozen=True)
class AxisPins:
    name: str
    step_pin: int
    dir_pin: int


@dataclass(frozen=True)
class MoveCommand:
    axis: str
    steps: int
    direction: int  # 1 = forward, 0 = backward


AXES: Dict[str, AxisPins] = {
    "X": AxisPins(name="X", step_pin=M1_STEP, dir_pin=M1_DIR),
    "Y": AxisPins(name="Y", step_pin=M2_STEP, dir_pin=M2_DIR),
}


# One move is executed after each accepted optical trigger.
MOVE_LIST: List[MoveCommand] = [
    MoveCommand("X", 3000, 1),
    MoveCommand("X", 3000, 1),
    MoveCommand("X", 3000, 1),
    MoveCommand("Y", 3000, 1),
    MoveCommand("X", 3000, 0),
    MoveCommand("X", 3000, 0),
    MoveCommand("X", 3000, 0),
    MoveCommand("Y", 3000, 1),
]


# =========================================================
# HELPERS
# =========================================================
def inv(level: int, do_inv: bool) -> int:
    if not do_inv:
        return level
    return GPIO.LOW if level == GPIO.HIGH else GPIO.HIGH


def step_level(active: bool) -> int:
    return inv(GPIO.HIGH if active else GPIO.LOW, INVERT_STEP)


def dir_level(direction: int) -> int:
    logical_level = GPIO.HIGH if direction else GPIO.LOW
    return inv(logical_level, INVERT_DIR)


def spec_level(active: bool) -> int:
    if SPEC_ACTIVE_HIGH:
        return GPIO.HIGH if active else GPIO.LOW
    return GPIO.LOW if active else GPIO.HIGH


def optic_pull_mode() -> int:
    if OPTIC_TRIGGER_EDGE == GPIO.RISING:
        return GPIO.PUD_DOWN
    if OPTIC_TRIGGER_EDGE == GPIO.FALLING:
        return GPIO.PUD_UP
    raise ValueError("OPTIC_TRIGGER_EDGE must be GPIO.RISING or GPIO.FALLING")


def expected_trigger_level() -> int:
    if OPTIC_TRIGGER_EDGE == GPIO.RISING:
        return GPIO.HIGH
    if OPTIC_TRIGGER_EDGE == GPIO.FALLING:
        return GPIO.LOW
    raise ValueError("OPTIC_TRIGGER_EDGE must be GPIO.RISING or GPIO.FALLING")


def get_axis(axis_name: str) -> AxisPins:
    axis_key = axis_name.upper()
    if axis_key not in AXES:
        raise ValueError(f"Unknown axis '{axis_name}'. Expected one of: {', '.join(sorted(AXES))}")
    return AXES[axis_key]


def validate_settings(moves: Sequence[MoveCommand]) -> None:
    if STEP_FREQ_HZ <= 0:
        raise ValueError("STEP_FREQ_HZ must be > 0")
    if STEP_PULSE_US <= 0:
        raise ValueError("STEP_PULSE_US must be > 0")
    if SPEC_PULSE_US <= 0:
        raise ValueError("SPEC_PULSE_US must be > 0")
    if TRIGGER_DEBOUNCE_MS < 0:
        raise ValueError("TRIGGER_DEBOUNCE_MS must be >= 0")
    if TRIGGER_SETTLE_S < 0:
        raise ValueError("TRIGGER_SETTLE_S must be >= 0")
    if MEASUREMENT_TIME_S < 0:
        raise ValueError("MEASUREMENT_TIME_S must be >= 0")
    if POST_MOVE_GUARD_S < 0:
        raise ValueError("POST_MOVE_GUARD_S must be >= 0")
    if TRIGGER_WAIT_TIMEOUT_S is not None and TRIGGER_WAIT_TIMEOUT_S <= 0:
        raise ValueError("TRIGGER_WAIT_TIMEOUT_S must be > 0 or None")
    if not moves:
        raise ValueError("MOVE_LIST must contain at least one move")

    for move in moves:
        get_axis(move.axis)
        if move.steps < 0:
            raise ValueError(f"Move steps must be >= 0 for axis {move.axis}")
        if move.direction not in (0, 1):
            raise ValueError(f"Move direction must be 0 or 1 for axis {move.axis}")


def gpio_setup() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for axis in AXES.values():
        GPIO.setup(axis.step_pin, GPIO.OUT, initial=step_level(False))
        GPIO.setup(axis.dir_pin, GPIO.OUT, initial=dir_level(0))

    GPIO.setup(OPTIC_TRIG_IN, GPIO.IN, pull_up_down=optic_pull_mode())
    GPIO.setup(SPEC_TRIG_OUT, GPIO.OUT, initial=spec_level(False))


def safe_output_idle() -> None:
    for axis in AXES.values():
        GPIO.output(axis.step_pin, step_level(False))
        GPIO.output(axis.dir_pin, dir_level(0))
    GPIO.output(SPEC_TRIG_OUT, spec_level(False))


def set_dir(axis: AxisPins, direction: int) -> None:
    if direction not in (0, 1):
        raise ValueError("Direction must be 0 or 1")
    GPIO.output(axis.dir_pin, dir_level(direction))
    time.sleep(DIR_SETUP_S)


def compute_step_timing(freq_hz: int, pulse_us: int) -> Tuple[float, float, bool]:
    if freq_hz <= 0:
        raise ValueError("Frequency must be > 0")
    if pulse_us <= 0:
        raise ValueError("Pulse width must be > 0")

    period_s = 1.0 / float(freq_hz)
    requested_high_s = pulse_us * 1e-6
    clipped = False

    if requested_high_s >= period_s:
        clipped = True
        high_s = period_s * 0.5
    else:
        high_s = requested_high_s

    low_s = period_s - high_s
    if low_s <= 0.0:
        clipped = True
        high_s = period_s * 0.5
        low_s = period_s * 0.5

    return high_s, low_s, clipped


def sleep_until(target_time: float) -> None:
    delay_s = target_time - time.perf_counter()
    if delay_s > 0:
        time.sleep(delay_s)


def pulse_steps(axis: AxisPins, steps: int, freq_hz: int, pulse_us: int) -> None:
    if steps <= 0:
        print(f"Skipping {axis.name}: requested 0 steps.")
        return

    high_s, low_s, clipped = compute_step_timing(freq_hz, pulse_us)
    if clipped:
        period_us = int(round((1.0 / float(freq_hz)) * 1_000_000.0))
        print(
            f"Warning: STEP_PULSE_US={pulse_us} us is too large for {freq_hz} Hz "
            f"(period {period_us} us). Using a 50/50 duty cycle."
        )

    step_hi = step_level(True)
    step_lo = step_level(False)

    GPIO.output(axis.step_pin, step_lo)
    edge_time = time.perf_counter()

    try:
        for _ in range(steps):
            GPIO.output(axis.step_pin, step_hi)
            edge_time += high_s
            sleep_until(edge_time)

            GPIO.output(axis.step_pin, step_lo)
            edge_time += low_s
            sleep_until(edge_time)
    finally:
        GPIO.output(axis.step_pin, step_lo)


def execute_move(move: MoveCommand) -> None:
    axis = get_axis(move.axis)
    print(f"Move {axis.name}: steps={move.steps}, dir={move.direction}")
    set_dir(axis, move.direction)
    pulse_steps(axis, move.steps, STEP_FREQ_HZ, STEP_PULSE_US)


def send_spectrometer_trigger() -> None:
    GPIO.output(SPEC_TRIG_OUT, spec_level(True))
    time.sleep(SPEC_PULSE_US * 1e-6)
    GPIO.output(SPEC_TRIG_OUT, spec_level(False))


def remaining_timeout_ms(deadline_s: Optional[float]) -> Optional[int]:
    if deadline_s is None:
        return None
    remaining_s = deadline_s - time.monotonic()
    if remaining_s <= 0:
        return 1
    return max(1, int(remaining_s * 1000.0))


def wait_for_edge(timeout_ms: Optional[int]) -> Optional[int]:
    if timeout_ms is None:
        return GPIO.wait_for_edge(
            OPTIC_TRIG_IN,
            OPTIC_TRIGGER_EDGE,
            bouncetime=TRIGGER_DEBOUNCE_MS,
        )

    return GPIO.wait_for_edge(
        OPTIC_TRIG_IN,
        OPTIC_TRIGGER_EDGE,
        timeout=timeout_ms,
        bouncetime=TRIGGER_DEBOUNCE_MS,
    )


def wait_for_optic_trigger(timeout_s: Optional[float]) -> bool:
    """
    Wait for one clean optical trigger edge.

    Returns True when a settled trigger is confirmed. Returns False only when
    a timeout expires.
    """
    deadline_s = None if timeout_s is None else time.monotonic() + timeout_s
    active_level = expected_trigger_level()

    while True:
        channel = wait_for_edge(remaining_timeout_ms(deadline_s))
        if channel is None:
            return False

        if TRIGGER_SETTLE_S > 0:
            time.sleep(TRIGGER_SETTLE_S)

        if GPIO.input(OPTIC_TRIG_IN) == active_level:
            return True

        print("Rejected noisy trigger pulse; waiting for the next edge.")


def run_sequence(moves: Sequence[MoveCommand]) -> None:
    total_cycles = len(moves)
    cycle = 0

    print("System started")
    print("Optical board: trigger input monitored by Raspberry Pi")
    print("Waiting for optical trigger from board...")

    while cycle < total_cycles:
        print(f"\nCycle {cycle + 1}/{total_cycles} - waiting for optical trigger")

        if not wait_for_optic_trigger(TRIGGER_WAIT_TIMEOUT_S):
            print("Timed out waiting for optical trigger")
            continue

        print("Optical trigger detected")

        send_spectrometer_trigger()
        print("Spectrometer trigger sent")

        time.sleep(MEASUREMENT_TIME_S)
        print("Measurement window done")

        execute_move(moves[cycle])
        cycle += 1

        time.sleep(POST_MOVE_GUARD_S)

    print("\nAll cycles completed")


def main() -> None:
    validate_settings(MOVE_LIST)
    gpio_setup()

    try:
        run_sequence(MOVE_LIST)
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        safe_output_idle()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
