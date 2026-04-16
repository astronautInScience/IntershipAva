from machine import Pin
import time

# -----------------------------
# User settings
# -----------------------------
TRIGGER_INPUT_PIN = 4
STEP_PIN = 18
DIR_PIN = 19

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
STEP_PULSE_TIME = 0.001       # seconds

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
    global trigger_pin, step_pin, dir_pin

    trigger_pin = Pin(TRIGGER_INPUT_PIN, Pin.IN, Pin.PULL_DOWN)
    step_pin = Pin(STEP_PIN, Pin.OUT)
    dir_pin = Pin(DIR_PIN, Pin.OUT)

    # idle states
    out(step_pin, False, INVERT_STEP)
    out(dir_pin, DIRECTION, INVERT_DIR)


def step_once():
    out(step_pin, True, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)
    out(step_pin, False, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)


def move_steps(direction, steps):
    out(dir_pin, direction, INVERT_DIR)
    time.sleep(DIR_SETUP_TIME)

    for _ in range(steps):
        step_once()


def wait_for_rising_edge(pin):
    previous = pin.value()
    while True:
        current = pin.value()
        if previous == 0 and current == 1:
            time.sleep_ms(50)  # debounce
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

            move_steps(DIRECTION, CHUNK_STEPS)
            moved_distance += CHUNK_MM

            print("Movement completed: {} mm".format(CHUNK_MM))
            print("Total moved distance: {} mm".format(moved_distance))

        print("Target total distance reached. Program stopped.")

    except KeyboardInterrupt:
        print("Program stopped by user")


if __name__ == "__main__":
    main()
