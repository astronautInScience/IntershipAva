import time
import RPi.GPIO as GPIO

# -----------------------------
# User settings
# -----------------------------
TRIGGER_INPUT_PIN = 17
STEP_PIN = 18
DIR_PIN = 23

# -----------------------------
# Logic settings for ULN2803A
# -----------------------------
INVERT_STEP = True
INVERT_DIR = True

# -----------------------------
# Timing settings
# -----------------------------
TRIGGER_TO_MOVE_DELAY = 1.0   # seconds after trigger before movement
DIR_SETUP_TIME = 0.02         # seconds after setting direction before stepping
STEP_PULSE_TIME = 0.001       # start with same value as working code

# -----------------------------
# Calibration / movement settings
# -----------------------------
STEPS_PER_10MM = 2000
STEPS_PER_MM = STEPS_PER_10MM / 10.0   # 200 steps/mm

CHUNK_MM = 10.0
TOTAL_DISTANCE_MM = 40.0
CHUNK_STEPS = int(CHUNK_MM * STEPS_PER_MM)

# Direction:
# True = one direction
# False = opposite direction
DIRECTION = False


def out(pin, logical_level, invert=False):
    physical_level = not logical_level if invert else logical_level
    GPIO.output(pin, GPIO.HIGH if physical_level else GPIO.LOW)


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(TRIGGER_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(STEP_PIN, GPIO.OUT)
    GPIO.setup(DIR_PIN, GPIO.OUT)

    # idle states
    out(STEP_PIN, False, INVERT_STEP)
    out(DIR_PIN, DIRECTION, INVERT_DIR)


def step_once():
    out(STEP_PIN, True, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)
    out(STEP_PIN, False, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)


def move_steps(direction, steps):
    out(DIR_PIN, direction, INVERT_DIR)
    time.sleep(DIR_SETUP_TIME)

    for _ in range(steps):
        step_once()


def main():
    setup_gpio()
    print("Waiting for trigger input...")

    moved_distance = 0.0

    try:
        while moved_distance < TOTAL_DISTANCE_MM:
            GPIO.wait_for_edge(TRIGGER_INPUT_PIN, GPIO.RISING, bouncetime=50)
            print("Trigger received")

            time.sleep(TRIGGER_TO_MOVE_DELAY)

            move_steps(DIRECTION, CHUNK_STEPS)
            moved_distance += CHUNK_MM

            print(f"Movement completed: {CHUNK_MM} mm")
            print(f"Total moved distance: {moved_distance} mm")

        print("Target total distance reached. Program stopped.")

    except KeyboardInterrupt:
        print("Program stopped by user")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
