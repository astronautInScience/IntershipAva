#!/usr/bin/env python3
"""Interactive two-axis stepper debug tool for Raspberry Pi GPIO."""

import time
from dataclasses import dataclass

import RPi.GPIO as GPIO

# =========================================================
# PIN MAPPING (BCM)
# =========================================================
M1_STEP, M1_DIR = 18, 23   # X axis
M2_STEP, M2_DIR = 5, 6     # Y axis

# =========================================================
# DRIVER LOGIC
# ULN2803A (sinking PUL-/DIR-) => INVERTS
# =========================================================
INVERT_STEP = True
INVERT_DIR = True

# =========================================================
# DEFAULT SETTINGS
# =========================================================
DEFAULT_FREQ_HZ = 500
DEFAULT_PULSE_US = 1000
DEFAULT_STEPS = 3000
DEFAULT_SECONDS = 3.0
DIR_SETUP_S = 0.002
EDGE_DWELL_S = 0.2

# Input limits
MIN_FREQ_HZ = 1
MAX_FREQ_HZ = 5000
MIN_PULSE_US = 1
MAX_PULSE_US = 100000
MIN_STEPS = 1
MIN_SECONDS = 0.001


# =========================================================
# DATA MODEL
# =========================================================
@dataclass
class MotionConfig:
    axis: str = "X"              # "X" or "Y"
    direction: int = 1           # 1=forward, 0=backward
    freq_hz: int = DEFAULT_FREQ_HZ
    pulse_us: int = DEFAULT_PULSE_US
    mode: str = "steps"          # "steps" or "seconds"
    steps: int = DEFAULT_STEPS
    seconds: float = DEFAULT_SECONDS


# =========================================================
# GPIO HELPERS
# =========================================================
def inv(level: int, do_inv: bool) -> int:
    if not do_inv:
        return level
    return GPIO.LOW if level == GPIO.HIGH else GPIO.HIGH


def gpio_setup() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Initialize pins to logical LOW (taking inversion into account).
    GPIO.setup(M1_STEP, GPIO.OUT, initial=inv(GPIO.LOW, INVERT_STEP))
    GPIO.setup(M2_STEP, GPIO.OUT, initial=inv(GPIO.LOW, INVERT_STEP))
    GPIO.setup(M1_DIR, GPIO.OUT, initial=inv(GPIO.LOW, INVERT_DIR))
    GPIO.setup(M2_DIR, GPIO.OUT, initial=inv(GPIO.LOW, INVERT_DIR))


def gpio_cleanup() -> None:
    GPIO.cleanup()


def get_axis_pins(axis: str) -> tuple[int, int]:
    axis = axis.upper()
    if axis == "X":
        return M1_STEP, M1_DIR
    if axis == "Y":
        return M2_STEP, M2_DIR
    raise ValueError("Axis must be 'X' or 'Y'")


# =========================================================
# MOTION FUNCTIONS
# =========================================================
def set_dir(dir_pin: int, direction: int) -> None:
    if direction not in (0, 1):
        raise ValueError("Direction must be 0 or 1")
    d = GPIO.HIGH if direction else GPIO.LOW
    GPIO.output(dir_pin, inv(d, INVERT_DIR))
    time.sleep(DIR_SETUP_S)


def _compute_timing(freq_hz: int, pulse_us: int) -> tuple[float, float, bool]:
    if freq_hz <= 0:
        raise ValueError("Frequency must be > 0")
    if pulse_us <= 0:
        raise ValueError("Pulse width must be > 0")

    period = 1.0 / float(freq_hz)
    requested_high = pulse_us * 1e-6
    clipped = False

    if requested_high >= period:
        clipped = True
        high_t = period * 0.5
    else:
        high_t = requested_high

    low_t = period - high_t
    if low_t <= 0.0:
        clipped = True
        high_t = period * 0.5
        low_t = period * 0.5

    return high_t, low_t, clipped


def _sleep_until(target_t: float) -> None:
    delay = target_t - time.perf_counter()
    if delay > 0:
        time.sleep(delay)


def pulse_steps(step_pin: int, steps: int, freq_hz: int, pulse_us: int) -> None:
    if steps <= 0:
        return

    high_t, low_t, clipped = _compute_timing(freq_hz, pulse_us)
    if clipped:
        period_us = int(round((1.0 / float(freq_hz)) * 1_000_000.0))
        print(f"Warning: pulse width {pulse_us} us is too large for {freq_hz} Hz (period {period_us} us). Using 50/50 duty.")

    hi = inv(GPIO.HIGH, INVERT_STEP)
    lo = inv(GPIO.LOW, INVERT_STEP)

    GPIO.output(step_pin, lo)
    edge_t = time.perf_counter()
    try:
        for _ in range(steps):
            GPIO.output(step_pin, hi)
            edge_t += high_t
            _sleep_until(edge_t)

            GPIO.output(step_pin, lo)
            edge_t += low_t
            _sleep_until(edge_t)
    finally:
        GPIO.output(step_pin, lo)


def move_motor_steps(step_pin: int, dir_pin: int, steps: int, direction: int, freq_hz: int, pulse_us: int) -> None:
    set_dir(dir_pin, direction)
    pulse_steps(step_pin, steps, freq_hz, pulse_us)


def move_motor_seconds(step_pin: int, dir_pin: int, seconds: float, direction: int, freq_hz: int, pulse_us: int) -> None:
    if seconds < 0:
        raise ValueError("Seconds must be >= 0")
    steps = int(round(seconds * freq_hz))
    move_motor_steps(step_pin, dir_pin, steps, direction, freq_hz, pulse_us)


def jog_motor(step_pin: int, dir_pin: int, direction: int, freq_hz: int, pulse_us: int) -> None:
    """Continuous jog until Ctrl+C."""
    set_dir(dir_pin, direction)

    high_t, low_t, clipped = _compute_timing(freq_hz, pulse_us)
    if clipped:
        period_us = int(round((1.0 / float(freq_hz)) * 1_000_000.0))
        print(f"Warning: pulse width {pulse_us} us is too large for {freq_hz} Hz (period {period_us} us). Using 50/50 duty.")

    hi = inv(GPIO.HIGH, INVERT_STEP)
    lo = inv(GPIO.LOW, INVERT_STEP)

    print("Jogging... Press Ctrl+C to stop.")
    GPIO.output(step_pin, lo)
    edge_t = time.perf_counter()

    try:
        while True:
            GPIO.output(step_pin, hi)
            edge_t += high_t
            _sleep_until(edge_t)

            GPIO.output(step_pin, lo)
            edge_t += low_t
            _sleep_until(edge_t)
    except KeyboardInterrupt:
        print("\nJog stopped.")
    finally:
        GPIO.output(step_pin, lo)
        time.sleep(EDGE_DWELL_S)


# =========================================================
# USER INTERFACE
# =========================================================
def dir_name(direction: int) -> str:
    return "forward" if direction == 1 else "backward"


def estimate_duration_s(cfg: MotionConfig) -> float:
    if cfg.mode == "steps":
        return float(cfg.steps) / float(cfg.freq_hz)
    return max(0.0, cfg.seconds)


def print_status(cfg: MotionConfig) -> None:
    print("\n" + "=" * 60)
    print("CURRENT TEST SETTINGS")
    print("=" * 60)
    print(f"Axis        : {cfg.axis}")
    print(f"Direction   : {dir_name(cfg.direction)}")
    print(f"Speed       : {cfg.freq_hz} steps/s")
    print(f"Pulse width : {cfg.pulse_us} us")
    print(f"Mode        : {cfg.mode}")
    print(f"Steps       : {cfg.steps}")
    print(f"Seconds     : {cfg.seconds}")
    print(f"Est. move   : {estimate_duration_s(cfg):.3f} s")
    print("=" * 60)


def print_menu() -> None:
    print("\nSelect an option:")
    print("  1  - Select axis (X/Y)")
    print("  2  - Select direction (forward/backward)")
    print("  3  - Set speed (steps/s)")
    print("  4  - Set pulse width (us)")
    print("  5  - Set move mode (steps/seconds)")
    print("  6  - Set number of steps")
    print("  7  - Set move duration (seconds)")
    print("  8  - Run one move")
    print("  9  - Jog continuously")
    print(" 10  - Quick reverse direction")
    print(" 11  - Quick switch axis")
    print(" 12  - Reset defaults")
    print("  q  - Quit")


def ask_axis(current: str) -> str:
    while True:
        val = input(f"Axis [X/Y] (current: {current}, Enter=keep): ").strip().upper()
        if val == "":
            return current
        if val in ("X", "Y"):
            return val
        print("Invalid axis. Enter X or Y.")


def ask_direction(current: int) -> int:
    while True:
        val = input(f"Direction [f/b] (current: {dir_name(current)}, Enter=keep): ").strip().lower()
        if val == "":
            return current
        if val in ("f", "forward", "1"):
            return 1
        if val in ("b", "backward", "0"):
            return 0
        print("Invalid direction. Enter f or b.")


def ask_int(prompt: str, current: int, min_val: int = 1, max_val: int | None = None) -> int:
    while True:
        val = input(f"{prompt} (current: {current}, Enter=keep): ").strip()
        if val == "":
            return current
        try:
            num = int(val)
            if num < min_val:
                print(f"Value must be >= {min_val}")
                continue
            if max_val is not None and num > max_val:
                print(f"Value must be <= {max_val}")
                continue
            return num
        except ValueError:
            print("Please enter a valid integer.")


def ask_float(prompt: str, current: float, min_val: float = 0.001) -> float:
    while True:
        val = input(f"{prompt} (current: {current}, Enter=keep): ").strip()
        if val == "":
            return current
        try:
            num = float(val)
            if num < min_val:
                print(f"Value must be >= {min_val}")
                continue
            return num
        except ValueError:
            print("Please enter a valid number.")


def ask_mode(current: str) -> str:
    while True:
        val = input(f"Mode [steps/seconds] (current: {current}, Enter=keep): ").strip().lower()
        if val == "":
            return current
        if val in ("steps", "step", "s"):
            return "steps"
        if val in ("seconds", "second", "sec", "t"):
            return "seconds"
        print("Invalid mode. Enter steps or seconds.")


def validate_config(cfg: MotionConfig) -> None:
    get_axis_pins(cfg.axis)

    if cfg.direction not in (0, 1):
        raise ValueError("Direction must be 0 or 1.")
    if cfg.freq_hz < MIN_FREQ_HZ or cfg.freq_hz > MAX_FREQ_HZ:
        raise ValueError(f"Speed must be in range {MIN_FREQ_HZ}..{MAX_FREQ_HZ} steps/s.")
    if cfg.pulse_us < MIN_PULSE_US or cfg.pulse_us > MAX_PULSE_US:
        raise ValueError(f"Pulse width must be in range {MIN_PULSE_US}..{MAX_PULSE_US} us.")
    if cfg.mode not in ("steps", "seconds"):
        raise ValueError("Mode must be 'steps' or 'seconds'.")
    if cfg.steps < MIN_STEPS:
        raise ValueError(f"Steps must be >= {MIN_STEPS}.")
    if cfg.seconds < MIN_SECONDS:
        raise ValueError(f"Seconds must be >= {MIN_SECONDS}.")


def run_move(cfg: MotionConfig) -> None:
    validate_config(cfg)
    step_pin, dir_pin = get_axis_pins(cfg.axis)

    print("\nRunning move with:")
    print(f"  Axis      : {cfg.axis}")
    print(f"  Direction : {dir_name(cfg.direction)}")
    print(f"  Speed     : {cfg.freq_hz} steps/s")
    print(f"  Pulse     : {cfg.pulse_us} us")
    print(f"  Mode      : {cfg.mode}")

    try:
        if cfg.mode == "steps":
            print(f"  Steps     : {cfg.steps}")
            move_motor_steps(step_pin, dir_pin, cfg.steps, cfg.direction, cfg.freq_hz, cfg.pulse_us)
        else:
            print(f"  Seconds   : {cfg.seconds}")
            move_motor_seconds(step_pin, dir_pin, cfg.seconds, cfg.direction, cfg.freq_hz, cfg.pulse_us)
        print("Move complete.")
    except KeyboardInterrupt:
        print("\nMove interrupted by user.")
    finally:
        time.sleep(EDGE_DWELL_S)


def reset_defaults(cfg: MotionConfig) -> None:
    cfg.axis = "X"
    cfg.direction = 1
    cfg.freq_hz = DEFAULT_FREQ_HZ
    cfg.pulse_us = DEFAULT_PULSE_US
    cfg.mode = "steps"
    cfg.steps = DEFAULT_STEPS
    cfg.seconds = DEFAULT_SECONDS


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    cfg = MotionConfig()
    gpio_setup()

    try:
        print("=" * 60)
        print("STEPPER / ACTUATOR DEBUG TEST TOOL")
        print("=" * 60)
        print("Use this to test one axis at a time.")
        print("If forward/backward is reversed physically, just use the other direction.")
        print("Recommended first test:")
        print("  - Axis: X")
        print("  - Direction: forward")
        print("  - Speed: 200")
        print("  - Pulse width: 1000 us")
        print("  - Steps: 500")
        print("=" * 60)

        while True:
            print_status(cfg)
            print_menu()
            choice = input("\nEnter choice: ").strip().lower()

            try:
                if choice == "1":
                    cfg.axis = ask_axis(cfg.axis)

                elif choice == "2":
                    cfg.direction = ask_direction(cfg.direction)

                elif choice == "3":
                    cfg.freq_hz = ask_int(
                        prompt="Enter speed in steps/s",
                        current=cfg.freq_hz,
                        min_val=MIN_FREQ_HZ,
                        max_val=MAX_FREQ_HZ,
                    )

                elif choice == "4":
                    cfg.pulse_us = ask_int(
                        prompt="Enter pulse width in microseconds",
                        current=cfg.pulse_us,
                        min_val=MIN_PULSE_US,
                        max_val=MAX_PULSE_US,
                    )

                elif choice == "5":
                    cfg.mode = ask_mode(cfg.mode)

                elif choice == "6":
                    cfg.steps = ask_int(
                        prompt="Enter step count",
                        current=cfg.steps,
                        min_val=MIN_STEPS,
                    )

                elif choice == "7":
                    cfg.seconds = ask_float(
                        prompt="Enter duration in seconds",
                        current=cfg.seconds,
                        min_val=MIN_SECONDS,
                    )

                elif choice == "8":
                    run_move(cfg)

                elif choice == "9":
                    validate_config(cfg)
                    step_pin, dir_pin = get_axis_pins(cfg.axis)
                    print(
                        f"\nJog start: axis={cfg.axis}, dir={dir_name(cfg.direction)}, "
                        f"speed={cfg.freq_hz}, pulse={cfg.pulse_us} us"
                    )
                    jog_motor(step_pin, dir_pin, cfg.direction, cfg.freq_hz, cfg.pulse_us)

                elif choice == "10":
                    cfg.direction = 0 if cfg.direction == 1 else 1
                    print(f"Direction changed to {dir_name(cfg.direction)}")

                elif choice == "11":
                    cfg.axis = "Y" if cfg.axis == "X" else "X"
                    print(f"Axis changed to {cfg.axis}")

                elif choice == "12":
                    reset_defaults(cfg)
                    print("Defaults restored.")

                elif choice == "q":
                    print("Exiting.")
                    break

                else:
                    print("Unknown option.")
            except ValueError as exc:
                print(f"Input/config error: {exc}")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        gpio_cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()
