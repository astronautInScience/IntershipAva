import RPi.GPIO as GPIO
import time

# =========================
# PIN SETUP (BCM numbering)
# =========================
STEP_PIN = 18   # GPIO -> ULN IN1 -> ULN OUT1 -> PUL-
DIR_PIN  = 23   # GPIO -> ULN IN2 -> ULN OUT2 -> DIR-
ENA_PIN  = 24   # GPIO -> ULN IN3 -> ULN OUT3 -> ENA-   (optional)

# =========================
# LOGIC SETTINGS
# =========================
# Because ULN2803A pulls the driver input LOW when Pi output is HIGH,
# the logic is inverted.
INVERT_STEP = True
INVERT_DIR  = True
INVERT_ENA  = True

USE_ENABLE = True   # set False if ENA is not connected

# =========================
# MOTION CALIBRATION
# =========================
STEPS_PER_10MM = 2000
STEPS_PER_MM = STEPS_PER_10MM / 10.0   # 200 steps/mm
MOVE_MM = 40
MOVE_STEPS = int(MOVE_MM * STEPS_PER_MM)   # 8000 steps

# =========================
# TIMING
# =========================
STEP_DELAY = 0.001   # seconds
DIR_DELAY  = 0.01    # delay after changing direction

# =========================
# HELPER
# =========================
def out(pin, logical_level, invert=False):
    physical = GPIO.LOW if (logical_level and invert) else GPIO.HIGH if (not logical_level and invert) else GPIO.HIGH if logical_level else GPIO.LOW
    GPIO.output(pin, physical)

def step_once():
    # One pulse
    out(STEP_PIN, True, INVERT_STEP)
    time.sleep(STEP_DELAY)
    out(STEP_PIN, False, INVERT_STEP)
    time.sleep(STEP_DELAY)

def move_steps(steps, forward=True):
    # Set direction first
    out(DIR_PIN, forward, INVERT_DIR)
    time.sleep(DIR_DELAY)

    for _ in range(steps):
        step_once()

# =========================
# MAIN
# =========================
GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)

if USE_ENABLE:
    GPIO.setup(ENA_PIN, GPIO.OUT, initial=GPIO.LOW)

try:
    # Enable driver
    if USE_ENABLE:
        out(ENA_PIN, True, INVERT_ENA)

    print(f"Moving forward {MOVE_MM} mm ({MOVE_STEPS} steps)")
    move_steps(MOVE_STEPS, forward=True)

    time.sleep(1)

    print(f"Moving backward {MOVE_MM} mm ({MOVE_STEPS} steps)")
    move_steps(MOVE_STEPS, forward=False)

    print("Done")

finally:
    # Disable driver if used
    if USE_ENABLE:
        out(ENA_PIN, False, INVERT_ENA)

    GPIO.cleanup()
