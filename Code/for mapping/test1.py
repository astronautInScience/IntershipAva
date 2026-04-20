from machine import Pin
import time

# =========================================================
# USER SETTINGS
# =========================================================

TRIGGER_INPUT_PIN = 4

# Axis assignment
# Driver 1 = X-axis
# Driver 2 = Y-axis
X_STEP_PIN = 18
X_DIR_PIN  = 19

Y_STEP_PIN = 25
Y_DIR_PIN  = 26

# Driver logic inversion
INVERT_STEP = True
INVERT_DIR = True

# Mapping phases
PHASE_X_FORWARD  = 0
PHASE_Y_FORWARD  = 1
PHASE_X_BACKWARD = 2
PHASE_Y_BACKWARD = 3
PHASE_DONE       = 4

# Trigger / timing
WAIT_FOR_TRIGGER_EACH_MOVE = False
TRIGGER_TO_MOVE_DELAY_MS = 1000   # 1000 ms = 1 second
TRIGGER_DEBOUNCE_MS = 2

DIR_SETUP_TIME_MS = 20
STEP_HIGH_US = 1000
STEP_LOW_US = 1000

# Calibration
STEPS_PER_10MM = 2000
STEPS_PER_MM = STEPS_PER_10MM / 10.0

MOVE_MM = 10.0
MOVE_STEPS = round(MOVE_MM * STEPS_PER_MM)

# Mapping area
X_LENGTH_MM = 40.0
Y_LENGTH_MM = 350.0

X_MOVES_MAX = int(X_LENGTH_MM / MOVE_MM)   # 4
Y_MOVES_MAX = int(Y_LENGTH_MM / MOVE_MM)   # 35

# Axis directions
X_FORWARD_DIR = True
Y_FORWARD_DIR = True

# Scan state
x_index = 0
y_index = 0
phase = PHASE_X_FORWARD


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


# =========================================================
# MAPPING STATE
# =========================================================

def mapping_finished():
    return phase == PHASE_DONE


def current_position_mm():
    return x_index * MOVE_MM, y_index * MOVE_MM


def perform_next_scan_move():
    global x_index, y_index, phase

    while True:
        if phase == PHASE_X_FORWARD:
            if x_index < X_MOVES_MAX:
                move_x_steps(X_FORWARD_DIR, MOVE_STEPS)
                x_index += 1
                return True, "X forward"
            else:
                phase = PHASE_Y_FORWARD

        elif phase == PHASE_Y_FORWARD:
            if y_index < Y_MOVES_MAX:
                move_y_steps(Y_FORWARD_DIR, MOVE_STEPS)
                y_index += 1
                return True, "Y forward"
            else:
                phase = PHASE_X_BACKWARD

        elif phase == PHASE_X_BACKWARD:
            if x_index > 0:
                move_x_steps(not X_FORWARD_DIR, MOVE_STEPS)
                x_index -= 1
                return True, "X backward"
            else:
                phase = PHASE_Y_BACKWARD

        elif phase == PHASE_Y_BACKWARD:
            if y_index > 0:
                move_y_steps(not Y_FORWARD_DIR, MOVE_STEPS)
                y_index -= 1
                return True, "Y backward"
            else:
                phase = PHASE_DONE

        elif phase == PHASE_DONE:
            return False, "done"


# =========================================================
# MAIN PROGRAM
# =========================================================

def main():
    setup_gpio()

    total_moves = 2 * X_MOVES_MAX + 2 * Y_MOVES_MAX   # 4 + 35 + 4 + 35 = 78

    print("System armed.")
    print("Scan type: X forward -> Y forward -> X backward -> Y backward")
    print("Total motion cycles:", total_moves)

    cycle = 0
    started = True   # start immediately for testing

    try:
        while True:
            if mapping_finished():
                print("----------------------------------")
                print("Mapping finished.")
                print("Final position: X = {:.1f} mm, Y = {:.1f} mm".format(*current_position_mm()))
                break

            if WAIT_FOR_TRIGGER_EACH_MOVE:
                print("----------------------------------")
                print("Waiting for trigger for next move...")
                wait_for_clean_rising_edge(trigger_pin, TRIGGER_DEBOUNCE_MS)
                trigger_time = time.ticks_ms()
                print("Trigger received")
            else:
                if not started:
                    print("----------------------------------")
                    print("Waiting for initial trigger...")
                    wait_for_clean_rising_edge(trigger_pin, TRIGGER_DEBOUNCE_MS)
                    trigger_time = time.ticks_ms()
                    started = True
                    print("Initial trigger received")
                else:
                    trigger_time = time.ticks_ms()

            wait_ms_precise(TRIGGER_TO_MOVE_DELAY_MS)
            actual_delay = time.ticks_diff(time.ticks_ms(), trigger_time)

            moved, move_name = perform_next_scan_move()

            if not moved:
                print("No more moves required. Mapping finished.")
                break

            cycle += 1
            x_mm, y_mm = current_position_mm()

            print("Delay before move: {} ms".format(actual_delay))
            print("Cycle:", cycle)
            print("Executed move:", move_name)
            print("Current position -> X = {:.1f} mm, Y = {:.1f} mm".format(x_mm, y_mm))

    except KeyboardInterrupt:
        print("Program stopped by user")

    finally:
        set_x_step(False)
        set_y_step(False)


if __name__ == "__main__":
    main()
