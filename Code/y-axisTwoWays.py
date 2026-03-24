import RPi.GPIO as GPIO
import time

# =====================================
# PIN SETUP
# =====================================
STEP_PIN = 18   # TB6560 CLK+
DIR_PIN  = 23   # TB6560 CW+

# =====================================
# CALIBRATION
# =====================================
STEPS_PER_MM = 200.0
TRAVEL_MM = 300.0
TOTAL_STEPS = int(STEPS_PER_MM * TRAVEL_MM)   # 11000 steps

# =====================================
# MOTION SETTINGS
# =====================================
DIR_SETUP_TIME = 0.03     # seconds after direction change

START_DELAY = 0.004       # slow start
CRUISE_DELAY = 0.0025     # moderate speed
END_DELAY = 0.004         # slow stop

ACCEL_STEPS = 800         # ramp up/down steps
PAUSE_BETWEEN = 2.0

GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)

def one_pulse(delay):
    GPIO.output(STEP_PIN, GPIO.HIGH)
    time.sleep(delay)
    GPIO.output(STEP_PIN, GPIO.LOW)
    time.sleep(delay)

def move_steps(total_steps, direction=True):
    GPIO.output(DIR_PIN, GPIO.HIGH if direction else GPIO.LOW)
    time.sleep(DIR_SETUP_TIME)

    accel_steps = min(ACCEL_STEPS, total_steps // 2)
    cruise_steps = total_steps - 2 * accel_steps

    # Accelerate
    for i in range(accel_steps):
        frac = i / max(1, accel_steps)
        delay = START_DELAY - (START_DELAY - CRUISE_DELAY) * frac
        one_pulse(delay)

    # Cruise
    for _ in range(max(0, cruise_steps)):
        one_pulse(CRUISE_DELAY)

    # Decelerate
    for i in range(accel_steps):
        frac = i / max(1, accel_steps)
        delay = CRUISE_DELAY + (END_DELAY - CRUISE_DELAY) * frac
        one_pulse(delay)

try:
    print(f"Moving forward {TRAVEL_MM} mm ({TOTAL_STEPS} steps)...")
    move_steps(TOTAL_STEPS, direction=True)

    time.sleep(PAUSE_BETWEEN)

    print(f"Moving backward {TRAVEL_MM} mm ({TOTAL_STEPS} steps)...")
    move_steps(TOTAL_STEPS, direction=False)

finally:
    GPIO.output(STEP_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Finished.")
