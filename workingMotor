import RPi.GPIO as GPIO
import time

# =========================
# PIN MAPPING (BCM)
# =========================
M1_STEP, M1_DIR, M1_ENA = 18, 23, 24   # X
M2_STEP, M2_DIR, M2_ENA = 5, 6, 13     # Y

# =========================
# ULN2803A (PUL-/DIR-/ENA- sinking) => INVERTS
# Keep these True since your system moved with them
# =========================
INVERT_STEP = True
INVERT_DIR  = True
INVERT_ENA  = True

# =========================
# MOTION SETTINGS
# =========================
STEP_FREQ_HZ  = 300     # 200..800 for testing with time.sleep
STEP_PULSE_US = 1000    # 500..2000us (reliable)

# Move distance:
X_STEPS = 30000         # increase for farther
Y_STEPS = 30000

# If you prefer time-based instead of steps:
USE_SECONDS = False
X_SECONDS = 10
Y_SECONDS = 10

def inv(level, do_inv):
    if not do_inv:
        return level
    return GPIO.LOW if level == GPIO.HIGH else GPIO.HIGH

def ena_level(enable: bool, enable_active_low: bool) -> int:
    # physical ENA level at driver input (before ULN inversion)
    if enable_active_low:
        physical = GPIO.LOW if enable else GPIO.HIGH
    else:
        physical = GPIO.HIGH if enable else GPIO.LOW
    return inv(physical, INVERT_ENA)

def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in [M1_STEP, M1_DIR, M1_ENA, M2_STEP, M2_DIR, M2_ENA]:
        GPIO.setup(p, GPIO.OUT)
        GPIO.output(p, GPIO.LOW)

def set_enable(enable: bool, enable_active_low: bool):
    GPIO.output(M1_ENA, ena_level(enable, enable_active_low))
    GPIO.output(M2_ENA, ena_level(enable, enable_active_low))
    time.sleep(0.2)

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
        low_t = period * 0.5
    else:
        low_t = period - high_t

    for _ in range(steps):
        GPIO.output(step_pin, hi)
        time.sleep(high_t)
        GPIO.output(step_pin, lo)
        time.sleep(low_t)

def move_motor(step_pin: int, dir_pin: int, steps: int, direction: int, freq_hz: int):
    set_dir(dir_pin, direction)
    pulse_steps(step_pin, steps, freq_hz)

def move_for_seconds(step_pin: int, dir_pin: int, seconds: float, direction: int, freq_hz: int):
    steps = int(max(0.0, seconds) * freq_hz)
    move_motor(step_pin, dir_pin, steps, direction, freq_hz)

def long_move_test(enable_active_low: bool):
    print(f"\n=== Trying ENABLE_ACTIVE_LOW = {enable_active_low} ===")
    print("Enabling...")
    set_enable(True, enable_active_low)
    print("Touch shafts now: they should feel LOCKED/stiff if enabled correctly.")

    # X axis long
    print("X forward long...")
    if USE_SECONDS:
        move_for_seconds(M1_STEP, M1_DIR, X_SECONDS, 1, STEP_FREQ_HZ)
    else:
        move_motor(M1_STEP, M1_DIR, X_STEPS, 1, STEP_FREQ_HZ)
    time.sleep(0.2)

    print("X backward long...")
    if USE_SECONDS:
        move_for_seconds(M1_STEP, M1_DIR, X_SECONDS, 0, STEP_FREQ_HZ)
    else:
        move_motor(M1_STEP, M1_DIR, X_STEPS, 0, STEP_FREQ_HZ)
    time.sleep(0.4)

    # Y axis long
    print("Y forward long...")
    if USE_SECONDS:
        move_for_seconds(M2_STEP, M2_DIR, Y_SECONDS, 1, STEP_FREQ_HZ)
    else:
        move_motor(M2_STEP, M2_DIR, Y_STEPS, 1, STEP_FREQ_HZ)
    time.sleep(0.2)

    print("Y backward long...")
    if USE_SECONDS:
        move_for_seconds(M2_STEP, M2_DIR, Y_SECONDS, 0, STEP_FREQ_HZ)
    else:
        move_motor(M2_STEP, M2_DIR, Y_STEPS, 0, STEP_FREQ_HZ)
    time.sleep(0.4)

    print("Disabling...")
    set_enable(False, enable_active_low)

def main():
    gpio_setup()
    try:
        # Try BOTH polarities (this is the key fix)
        long_move_test(True)
        long_move_test(False)

        print("\nDone.")
        print("Whichever polarity made the motors LOCK + MOVE is your correct ENABLE_ACTIVE_LOW setting.")
    except KeyboardInterrupt:
        print("\nCTRL+C. Disabling.")
        # best-effort disable both ways
        GPIO.output(M1_ENA, GPIO.LOW)
        GPIO.output(M2_ENA, GPIO.LOW)
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
