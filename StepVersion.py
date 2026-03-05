import RPi.GPIO as GPIO
import time


# PIN MAPPING (BCM)

M1_STEP, M1_DIR = 18, 23   # X
M2_STEP, M2_DIR = 5, 6     # Y

# =========================
# ULN2803A (sinking PUL-/DIR-) => INVERTS
# =========================
INVERT_STEP = True
INVERT_DIR  = True

# =========================
# MOTION SETTINGS
# =========================
STEP_FREQ_HZ  = 500   # 200..800 for testing with time.sleep
STEP_PULSE_US = 1000    # 500..2000us (reliable)

# Choose distance mode:
MODE = "steps"          # "steps" or "seconds"

# Long moves:
X_STEPS   = 3000       # increase for farther
Y_STEPS   = 3000

X_SECONDS = 5          # increase for longer
Y_SECONDS = 5

def inv(level, do_inv):
    if not do_inv:
        return level
    return GPIO.LOW if level == GPIO.HIGH else GPIO.HIGH

def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in [M1_STEP, M1_DIR, M2_STEP, M2_DIR]:
        GPIO.setup(p, GPIO.OUT)
        GPIO.output(p, GPIO.LOW)

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

    # keep valid timing
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

def move_motor_seconds(step_pin: int, dir_pin: int, seconds: float, direction: int, freq_hz: int):
    steps = int(max(0.0, seconds) * freq_hz)
    move_motor_steps(step_pin, dir_pin, steps, direction, freq_hz)

def main():
    gpio_setup()
    try:
        print("ENA is disconnected -> driver must be enabled by wiring/switches.")
        print("Looping both directions. CTRL+C to stop.")

        while True:
            # X forward
            print("\nX -> forward")
            move_motor_steps(M1_STEP, M1_DIR, X_STEPS, 1, STEP_FREQ_HZ)
            time.sleep(0.2)

            # X backward
            print("X -> backward")
            move_motor_steps(M1_STEP, M1_DIR, X_STEPS, 0, STEP_FREQ_HZ)
            time.sleep(0.4)

            # Y forward
            print("\nY -> forward")
            move_motor_steps(M2_STEP, M2_DIR, Y_STEPS, 1, STEP_FREQ_HZ)
            time.sleep(0.2)

            # Y backward
            print("Y -> backward")
            move_motor_steps(M2_STEP, M2_DIR, Y_STEPS, 0, STEP_FREQ_HZ)
            time.sleep(0.6)

    except KeyboardInterrupt:
        print("\nCTRL+C detected.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
