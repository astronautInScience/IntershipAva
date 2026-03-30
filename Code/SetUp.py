import time
import RPi.GPIO as GPIO

# -----------------------------
# User settings
# -----------------------------
TRIGGER_INPUT_PIN = 17
STEP_PIN = 18
DIR_PIN = 23


# -----------------------------
# Timing settings
# -----------------------------
TRIGGER_TO_MOVE_DELAY = 1.0   # seconds after trigger before movement
DIR_SETUP_TIME = 0.02         # seconds after setting direction before stepping
STEP_PULSE_TIME = 0.01        # seconds

# -----------------------------
# Calibration / movement settings
# -----------------------------
STEPS_PER_10MM = 2000
STEPS_PER_MM = STEPS_PER_10MM / 10.0   # 200 steps/mm
CHUNK_MM = 10.0               # how much to move each trigger (10 mm)
TOTAL_DISTANCE_MM = 40.0      # total distance before stopping
CHUNK_STEPS = int(CHUNK_MM * STEPS_PER_MM)

# Direction:
# 1 = right
# 0 = left
DIRECTION = 1


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(TRIGGER_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(STEP_PIN, GPIO.OUT)
    GPIO.setup(DIR_PIN, GPIO.OUT)
    GPIO.output(STEP_PIN, GPIO.LOW)
    GPIO.output(DIR_PIN, GPIO.LOW)


def move_steps(direction, steps):
    GPIO.output(DIR_PIN, direction)
    time.sleep(DIR_SETUP_TIME)
    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(STEP_PULSE_TIME)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(STEP_PULSE_TIME)


def main():
    setup_gpio()
    print("Waiting for trigger input...")

    moved_distance = 0.0

    # After each trigger the stage moves 10 mm to the right, then stops and
    # waits for the next trigger. This loop continues until 40 mm total is reached.
    try:
        while moved_distance < TOTAL_DISTANCE_MM:
            GPIO.wait_for_edge(TRIGGER_INPUT_PIN, GPIO.RISING)
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
