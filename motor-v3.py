import RPi.GPIO as GPIO
import time

# =========================================================
# PIN MAPPING (BCM)
# =========================================================
M1_STEP, M1_DIR = 18, 23   # X axis
M2_STEP, M2_DIR = 5, 6     # Y axis

OPTIC_TRIG_IN = 24         # TRIG from optical board -> Pi input
SPEC_TRIG_OUT = 16         # Pi output -> spectrometer trigger input

# =========================================================
# DRIVER LOGIC
# ULN2803A (sinking PUL-/DIR-) => INVERTS
# =========================================================
INVERT_STEP = True
INVERT_DIR  = True

# =========================================================
# TRIGGER SETTINGS
# =========================================================
OPTIC_TRIGGER_EDGE = GPIO.RISING
TRIGGER_DEBOUNCE_MS = 20

SPEC_ACTIVE_HIGH = True
SPEC_PULSE_US = 5000            # 5 ms pulse to spectrometer
MEASUREMENT_TIME_S = 0.050      # adjust to your real spectrometer timing
POST_MOVE_GUARD_S = 0.010

# =========================================================
# MOTION SETTINGS
# =========================================================
STEP_FREQ_HZ  = 500
STEP_PULSE_US = 1000

# Example path:
# one motion command is executed after each accepted optical trigger
# Format: (axis, steps, direction)
# direction: 1 = forward, 0 = backward
MOVE_LIST = [
    ("X", 3000, 1),
    ("X", 3000, 1),
    ("X", 3000, 1),
    ("Y", 3000, 1),
    ("X", 3000, 0),
    ("X", 3000, 0),
    ("X", 3000, 0),
    ("Y", 3000, 1),
]

# =========================================================
# HELPERS
# =========================================================
def inv(level, do_inv):
    if not do_inv:
        return level
    return GPIO.LOW if level == GPIO.HIGH else GPIO.HIGH

def spec_level(active: bool):
    if SPEC_ACTIVE_HIGH:
        return GPIO.HIGH if active else GPIO.LOW
    return GPIO.LOW if active else GPIO.HIGH

def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # motor outputs
    for p in [M1_STEP, M1_DIR, M2_STEP, M2_DIR]:
        GPIO.setup(p, GPIO.OUT)
        GPIO.output(p, GPIO.LOW)

    # optical trigger input
    GPIO.setup(OPTIC_TRIG_IN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # spectrometer trigger output
    GPIO.setup(SPEC_TRIG_OUT, GPIO.OUT)
    GPIO.output(SPEC_TRIG_OUT, spec_level(False))

def set_dir(dir_pin: int, direction: int):
    d = GPIO.HIGH if direction else GPIO.LOW
    GPIO.output(dir_pin, inv(d, INVERT_DIR))
    time.sleep(0.002)

def pulse_steps(step_pin: int, steps: int, freq_hz: int):
    if steps <= 0:
        return

    hi = inv(GPIO.HIGH, INVERT_STEP)
    lo = inv(GPIO.LOW,  INVERT_STEP)

    high_t = STEP_PULSE_US * 1e-6
    period = 1.0 / float(freq_hz)

    if period <= high_t:
        high_t = period * 0.5
        low_t  = period * 0.5
    else:
        low_t = period - high_t

    for _ in range(steps):
        GPIO.output(step_pin, hi)
        time.sleep(high_t)
        GPIO.output(step_pin, lo)
        time.sleep(low_t)

def move_motor_steps(step_pin: int, dir_pin: int, steps: int, direction: int, freq_hz: int):
    set_dir(dir_pin, direction)
    pulse_steps(step_pin, steps, freq_hz)

def execute_move(axis: str, steps: int, direction: int):
    if axis == "X":
        print(f"Move X: steps={steps}, dir={direction}")
        move_motor_steps(M1_STEP, M1_DIR, steps, direction, STEP_FREQ_HZ)
    elif axis == "Y":
        print(f"Move Y: steps={steps}, dir={direction}")
        move_motor_steps(M2_STEP, M2_DIR, steps, direction, STEP_FREQ_HZ)
    else:
        raise ValueError(f"Unknown axis '{axis}'")

def send_spectrometer_trigger():
    GPIO.output(SPEC_TRIG_OUT, spec_level(True))
    time.sleep(SPEC_PULSE_US * 1e-6)
    GPIO.output(SPEC_TRIG_OUT, spec_level(False))

def wait_for_optic_trigger():
    """
    Wait for one clean optical trigger edge.
    Uses blocking edge detection + simple debounce/settling.
    """
    GPIO.wait_for_edge(
        OPTIC_TRIG_IN,
        OPTIC_TRIGGER_EDGE,
        bouncetime=TRIGGER_DEBOUNCE_MS
    )

    # tiny settle time so we don't react to noise
    time.sleep(0.002)

    # confirm line is still active for rising-edge systems
    if OPTIC_TRIGGER_EDGE == GPIO.RISING:
        return GPIO.input(OPTIC_TRIG_IN) == GPIO.HIGH
    else:
        return GPIO.input(OPTIC_TRIG_IN) == GPIO.LOW

# =========================================================
# MAIN
# =========================================================
def main():
    gpio_setup()

    cycle = 0
    total_cycles = len(MOVE_LIST)

    try:
        print("System 1 started")
        print("Optical board: only TRIG is read by code")
        print("Waiting for optical trigger from board...")

        while cycle < total_cycles:
            print(f"\nCycle {cycle + 1}/{total_cycles} - waiting for optical trigger")

            valid = wait_for_optic_trigger()
            if not valid:
                print("Ignored noisy trigger")
                continue

            print("Optical trigger detected")

            # 1) send trigger to spectrometer
            send_spectrometer_trigger()
            print("Spectrometer trigger sent")

            # 2) wait for measurement window
            time.sleep(MEASUREMENT_TIME_S)
            print("Measurement window done")

            # 3) move stage once
            axis, steps, direction = MOVE_LIST[cycle]
            execute_move(axis, steps, direction)

            cycle += 1

            # 4) short guard time before next cycle
            time.sleep(POST_MOVE_GUARD_S)

        print("\nAll cycles completed")

    except KeyboardInterrupt:
        print("\nStopped by user")

    finally:
        GPIO.output(SPEC_TRIG_OUT, spec_level(False))
        GPIO.cleanup()

if __name__ == "__main__":
    main()
