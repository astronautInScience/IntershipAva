import RPi.GPIO as GPIO
import time

# -------------------------
# PIN SETUP
# -------------------------
STEP_PIN = 18   # GPIO18 -> CLK+
DIR_PIN  = 23   # GPIO23 -> CW+

# -------------------------
# SETTINGS
# -------------------------
STEPS = 400              # number of pulses
PULSE_DELAY = 0.002      # seconds, 0.002 = slow and safe
PAUSE_BETWEEN = 1.0      # seconds

GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT)
GPIO.setup(DIR_PIN, GPIO.OUT)

def step_motor(steps, direction, delay):
    GPIO.output(DIR_PIN, direction)
    time.sleep(0.01)  # small delay so direction settles

    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(delay)

try:
    print("Moving forward...")
    step_motor(STEPS, GPIO.HIGH, PULSE_DELAY)

    time.sleep(PAUSE_BETWEEN)

    print("Moving backward...")
    step_motor(STEPS, GPIO.LOW, PULSE_DELAY)

    time.sleep(PAUSE_BETWEEN)

finally:
    GPIO.output(STEP_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Done.")
