from machine import Pin
import time

# -----------------------------
# User settings
# -----------------------------
TRIGGER_INPUT_PIN = 4

# Driver 1
STEP1_PIN = 18
DIR1_PIN = 19

# Driver 2
STEP2_PIN = 25
DIR2_PIN = 26

# -----------------------------
# Logic settings for driver input stage
# Change these if your driver logic is reversed
# -----------------------------
INVERT_STEP = True
INVERT_DIR = True

# -----------------------------
# Timing settings
# -----------------------------
TRIGGER_TO_MOVE_DELAY = 1.0   # seconds after trigger before movement
DIR_SETUP_TIME = 0.02         # seconds after setting direction before stepping
STEP_PULSE_TIME = 0.001       # seconds HIGH and seconds LOW

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
    pin.value(1 if physical_level else 0)


def setup_gpio():
    global trigger_pin
    global step1_pin, dir1_pin
    global step2_pin, dir2_pin

    trigger_pin = Pin(TRIGGER_INPUT_PIN, Pin.IN, Pin.PULL_DOWN)

    step1_pin = Pin(STEP1_PIN, Pin.OUT)
    dir1_pin = Pin(DIR1_PIN, Pin.OUT)

    step2_pin = Pin(STEP2_PIN, Pin.OUT)
    dir2_pin = Pin(DIR2_PIN, Pin.OUT)

    # Idle states
    out(step1_pin, False, INVERT_STEP)
    out(step2_pin, False, INVERT_STEP)

    out(dir1_pin, DIRECTION, INVERT_DIR)
    out(dir2_pin, DIRECTION, INVERT_DIR)


def step_once_both():
    # STEP HIGH
    out(step1_pin, True, INVERT_STEP)
    out(step2_pin, True, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)

    # STEP LOW
    out(step1_pin, False, INVERT_STEP)
    out(step2_pin, False, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)


def move_steps_both(direction, steps):
    out(dir1_pin, direction, INVERT_DIR)
    out(dir2_pin, direction, INVERT_DIR)
    time.sleep(DIR_SETUP_TIME)

    for _ in range(steps):
        step_once_both()


def wait_for_rising_edge(pin):
    previous = pin.value()

    while True:
        current = pin.value()

        if previous == 0 and current == 1:
            time.sleep_ms(50)   # debounce
            return

        previous = current
        time.sleep_ms(1)


def main():
    setup_gpio()
    print("Waiting for trigger input...")

    moved_distance = 0.0

    try:
        while moved_distance < TOTAL_DISTANCE_MM:
            wait_for_rising_edge(trigger_pin)
            print("Trigger received")

            time.sleep(TRIGGER_TO_MOVE_DELAY)

            move_steps_both(DIRECTION, CHUNK_STEPS)
            moved_distance += CHUNK_MM

            print("Movement completed: {} mm".format(CHUNK_MM))
            print("Total moved distance: {} mm".format(moved_distance))

        print("Target total distance reached. Program stopped.")

    except KeyboardInterrupt:
        print("Program stopped by user")

    finally:
        # Put outputs back to idle
        out(step1_pin, False, INVERT_STEP)
        out(step2_pin, False, INVERT_STEP)


if __name__ == "__main__":
    main()
