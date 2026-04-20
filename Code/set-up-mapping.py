from machine import Pin
import time

# =========================================================
# USER SETTINGS
# =========================================================

TRIGGER_INPUT_PIN = 4

# ---------------------------------------------------------
# Axis assignment
# Driver 1 = X-axis
# Driver 2 = Y-axis
# ---------------------------------------------------------
X_STEP_PIN = 18
X_DIR_PIN  = 19

Y_STEP_PIN = 25
Y_DIR_PIN  = 26

# ---------------------------------------------------------
# Driver logic inversion
# Keep these values if your current hardware already works
# ---------------------------------------------------------
INVERT_STEP = True
INVERT_DIR = True

# ---------------------------------------------------------
# Trigger / timing
# ---------------------------------------------------------
WAIT_FOR_TRIGGER_EACH_MOVE = True     # True = trigger before every move
TRIGGER_TO_MOVE_DELAY_MS = 10000      # 10 s delay after trigger
TRIGGER_DEBOUNCE_MS = 20

DIR_SETUP_TIME_MS = 20
STEP_HIGH_US = 1000
STEP_LOW_US = 1000

# ---------------------------------------------------------
# Calibration
# ---------------------------------------------------------
STEPS_PER_10MM = 2000
STEPS_PER_MM = STEPS_PER_10MM / 10.0

MOVE_MM = 10.0
MOVE_STEPS = round(MOVE_MM * STEPS_PER_MM)

# ---------------------------------------------------------
# Mapping area
# X = 40 mm
# Y = 350 mm
# ---------------------------------------------------------
X_LENGTH_MM = 40.0
Y_LENGTH_MM = 350.0

# Number of 10 mm moves needed
X_MOVES_MAX = int(X_LENGTH_MM / MOVE_MM)   # 4 moves: 0->10->20->30->40
Y_MOVES_MAX = int(Y_LENGTH_MM / MOVE_MM)   # 35 moves: 0->10->...->350

# ---------------------------------------------------------
# Axis directions
# Change these if an axis moves in the wrong direction
# ---------------------------------------------------------
X_FORWARD_DIR = False     # direction for increasing X
Y_FORWARD_DIR = False     # direction for increasing Y


# =========================================================
# LOW-LEVEL OUTPUT HELPERS
# =========================================================

def out(pin, logical_level, invert=False):
    physical_level = not logical_level if invert else logical_level
    pin.value(1 if physical_level else 0)


def set_x_step(level):
    out(x_step_pin, level, INVERT_STEP)


def set_y_step(level):
    out(y_step_pin, level, INVERT_STEP)


def set_x_dir(direction):
    out(x_dir_pin, direction, INVERT_DIR)


def set_y_dir(direction):
    out(y_dir_pin, direction, INVERT_DIR)


# =========================================================
# GPIO SETUP
# =========================================================

def setup_gpio():
    global trigger_pin
    global x_step_pin, x_dir_pin
    global y_step_pin, y_dir_pin

    trigger_pin = Pin(TRIGGER_INPUT_PIN, Pin.IN, Pin.PULL_DOWN)

    x_step_pin = Pin(X_STEP_PIN, Pin.OUT)
    x_dir_pin = Pin(X_DIR_PIN, Pin.OUT)

    y_step_pin = Pin(Y_STEP_PIN, Pin.OUT)
    y_dir_pin = Pin(Y_DIR_PIN, Pin.OUT)

    # Safe idle
    set_x_step(False)
    set_y_step(False)

    set_x_dir(X_FORWARD_DIR)
    set_y_dir(Y_FORWARD_DIR)


# =========================================================
# TIMING HELPERS
# =========================================================

def wait_ms_precise(delay_ms):
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
        time.sleep_ms(1)


def wait_for_clean_rising_edge(pin, debounce_ms=20):
    """
    Wait for a proper LOW -> HIGH trigger.
    """
    # Arm only when line is LOW
    while pin.value() == 1:
        time.sleep_ms(1)

    while True:
        if pin.value() == 1:
            t0 = time.ticks_ms()
            stable = True

            while time.ticks_diff(time.ticks_ms(), t0) < debounce_ms:
                if pin.value() == 0:
                    stable = False
                    break
                time.sleep_ms(1)

            if stable:
                return

        time.sleep_ms(1)


# =========================================================
# STEP GENERATION
# =========================================================

def pulse_x_step():
    set_x_step(True)
    time.sleep_us(STEP_HIGH_US)
    set_x_step(False)
    time.sleep_us(STEP_LOW_US)


def pulse_y_step():
    set_y_step(True)
    time.sleep_us(STEP_HIGH_US)
    set_y_step(False)
    time.sleep_us(STEP_LOW_US)


def move_x_steps(direction, steps):
    set_x_dir(direction)
    time.sleep_ms(DIR_SETUP_TIME_MS)

    for _ in range(steps):
        pulse_x_step()


def move_y_steps(direction, steps):
    set_y_dir(direction)
    time.sleep_ms(DIR_SETUP_TIME_MS)

    for _ in range(steps):
        pulse_y_step()


def move_x_10mm_forward():
    move_x_steps(X_FORWARD_DIR, MOVE_STEPS)


def move_x_10mm_backward():
    move_x_steps(not X_FORWARD_DIR, MOVE_STEPS)


def move_y_10mm_forward():
    move_y_steps(Y_FORWARD_DIR, MOVE_STEPS)


# =========================================================
# SCAN STATE
# =========================================================
#
# x_index = current X position in 10 mm units
#           0,1,2,3,4  => 0,10,20,30,40 mm
#
# y_index = current Y position in 10 mm units
#           0..35 => 0..350 mm
#
# moving_right:
#   True  => next X moves go toward 40 mm
#   False => next X moves go back toward 0 mm
# =========================================================

x_index = 0
y_index = 0
moving_right = True


def mapping_finished():
    """
    Mapping is finished when:
    - Y has reached the final row (35)
    - and X has completed the final row end position
    """
    global x_index, y_index, moving_right

    if y_index != Y_MOVES_MAX:
        return False

    if moving_right and x_index == X_MOVES_MAX:
        return True

    if (not moving_right) and x_index == 0:
        return True

    return False


def perform_next_scan_move():
    """
    Perform exactly ONE motion action:
    - either X +10 mm
    - or X -10 mm
    - or Y +10 mm at row end

    Returns:
        True  -> a move was executed
        False -> mapping is already finished
    """
    global x_index, y_index, moving_right

    # If already finished, no more motion
    if mapping_finished():
        return False

    # ---------------------------------
    # Case 1: moving left -> right
    # ---------------------------------
    if moving_right:
        # Still room to move in X
        if x_index < X_MOVES_MAX:
            move_x_10mm_forward()
            x_index += 1
            return True

        # X row finished, so move Y one step if possible
        if y_index < Y_MOVES_MAX:
            move_y_10mm_forward()
            y_index += 1
            moving_right = False
            return True

        return False

    # ---------------------------------
    # Case 2: moving right -> left
    # ---------------------------------
    else:
        # Still room to move back in X
        if x_index > 0:
            move_x_10mm_backward()
            x_index -= 1
            return True

        # X row finished, so move Y one step if possible
        if y_index < Y_MOVES_MAX:
            move_y_10mm_forward()
            y_index += 1
            moving_right = True
            return True

        return False


def current_position_mm():
    return x_index * MOVE_MM, y_index * MOVE_MM


# =========================================================
# MAIN PROGRAM
# =========================================================

def main():
    global x_index, y_index, moving_right

    setup_gpio()

    total_points = (X_MOVES_MAX + 1) * (Y_MOVES_MAX + 1)   # 5 * 36 = 180 points
    total_moves = X_MOVES_MAX * (Y_MOVES_MAX + 1) + Y_MOVES_MAX   # 4*36 + 35 = 179 moves

    print("System armed.")
    print("Scan type: serpentine raster")
    print("X positions:", X_MOVES_MAX + 1, "points")
    print("Y positions:", Y_MOVES_MAX + 1, "points")
    print("Total mapping points:", total_points)
    print("Total motion cycles:", total_moves)

    cycle = 0
    started = False

    try:
        while True:
            # Stop once mapping is complete
            if mapping_finished():
                print("----------------------------------")
                print("Mapping finished.")
                print("Final position: X = {:.1f} mm, Y = {:.1f} mm".format(*current_position_mm()))
                break

            # -------------------------------------------------
            # Trigger policy
            # -------------------------------------------------
            if WAIT_FOR_TRIGGER_EACH_MOVE:
                print("----------------------------------")
                print("Waiting for trigger for next move...")
                wait_for_clean_rising_edge(trigger_pin, TRIGGER_DEBOUNCE_MS)
                trigger_time = time.ticks_ms()
                print("Trigger received")

            else:
                # Wait only once at the beginning
                if not started:
                    print("----------------------------------")
                    print("Waiting for initial trigger to start full mapping...")
                    wait_for_clean_rising_edge(trigger_pin, TRIGGER_DEBOUNCE_MS)
                    trigger_time = time.ticks_ms()
                    started = True
                    print("Initial trigger received")
                else:
                    # no external wait after the first trigger
                    trigger_time = time.ticks_ms()

            # Delay after trigger
            wait_ms_precise(TRIGGER_TO_MOVE_DELAY_MS)
            actual_delay = time.ticks_diff(time.ticks_ms(), trigger_time)

            # Perform one motion action
            moved = perform_next_scan_move()

            if not moved:
                print("No more moves required. Mapping finished.")
                break

            cycle += 1
            x_mm, y_mm = current_position_mm()

            print("Delay before move: {} ms".format(actual_delay))
            print("Cycle:", cycle)
            print("Current position -> X = {:.1f} mm, Y = {:.1f} mm".format(x_mm, y_mm))
            print("Direction mode:", "X forward" if moving_right else "X backward")

    except KeyboardInterrupt:
        print("Program stopped by user")

    finally:
        set_x_step(False)
        set_y_step(False)


if __name__ == "__main__":
    main()
