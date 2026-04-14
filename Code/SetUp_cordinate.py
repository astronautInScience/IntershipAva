
import time
import RPi.GPIO as GPIO

# -----------------------------
# PIN SETUP
# -----------------------------
STEP_X = 18
DIR_X = 23

STEP_Y = 24
DIR_Y = 25

TRIGGER_INPUT_PIN = 17

# -----------------------------
# SETTINGS
# -----------------------------
INVERT_STEP = True
INVERT_DIR = True

STEP_PULSE_TIME = 0.001
DIR_SETUP_TIME = 0.002

STEPS_PER_MM = 200  # calibration

# Scan settings
X_POINTS = 10
Y_POINTS = 5
STEP_SIZE_MM = 2.0

# -----------------------------
# POSITION TRACKING
# -----------------------------
x_pos = 0.0
y_pos = 0.0


# -----------------------------
# GPIO FUNCTIONS
# -----------------------------
def out(pin, logical_level, invert=False):
    physical = not logical_level if invert else logical_level
    GPIO.output(pin, GPIO.HIGH if physical else GPIO.LOW)


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(STEP_X, GPIO.OUT)
    GPIO.setup(DIR_X, GPIO.OUT)
    GPIO.setup(STEP_Y, GPIO.OUT)
    GPIO.setup(DIR_Y, GPIO.OUT)

    GPIO.setup(TRIGGER_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)


# -----------------------------
# MOTOR CONTROL
# -----------------------------
def step(pin):
    out(pin, True, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)
    out(pin, False, INVERT_STEP)
    time.sleep(STEP_PULSE_TIME)


def move_axis(step_pin, dir_pin, steps, direction):
    out(dir_pin, direction, INVERT_DIR)
    time.sleep(DIR_SETUP_TIME)

    for _ in range(steps):
        step(step_pin)


# -----------------------------
# COORDINATE CONTROL
# -----------------------------
def move_to(target_x, target_y):
    global x_pos, y_pos

    dx = target_x - x_pos
    dy = target_y - y_pos

    steps_x = int(abs(dx) * STEPS_PER_MM)
    steps_y = int(abs(dy) * STEPS_PER_MM)

    dir_x = dx > 0
    dir_y = dy > 0

    # Move X first
    move_axis(STEP_X, DIR_X, steps_x, dir_x)

    # Then Y
    move_axis(STEP_Y, DIR_Y, steps_y, dir_y)

    x_pos = target_x
    y_pos = target_y

    print(f"Position -> X: {x_pos:.2f} mm, Y: {y_pos:.2f} mm")


# -----------------------------
# LIBS TRIGGER
# -----------------------------
def trigger_measurement():
    print("Waiting for LIBS trigger...")
    GPIO.wait_for_edge(TRIGGER_INPUT_PIN, GPIO.RISING)
    print("Measurement done")


# -----------------------------
# SCANNING ALGORITHM (RASTER)
# -----------------------------
def scan_grid():
    global x_pos, y_pos

    direction = 1  # 1 = right, -1 = left

    for j in range(Y_POINTS):

        for i in range(X_POINTS):

            target_x = i * STEP_SIZE_MM if direction == 1 else (X_POINTS - 1 - i) * STEP_SIZE_MM
            target_y = j * STEP_SIZE_MM

            move_to(target_x, target_y)

            time.sleep(0.2)  # settle time
            trigger_measurement()

        direction *= -1  # reverse X direction (zig-zag)


# -----------------------------
# MAIN
# -----------------------------
def main():
    setup_gpio()

    try:
        print("Starting LIBS scan...")
        scan_grid()

    except KeyboardInterrupt:
        print("Stopped")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
