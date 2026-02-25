from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep, time


# 1) DEFINE PI PINS  

# Motor 1 (X axis) 
M1_STEP = 18
M1_DIR  = 23
M1_ENA  = 24

# Motor 2 (Y axis) -> microstep driver inputs
M2_STEP = 5
M2_DIR  = 6
M2_ENA  = 13

# TTL inputs
voltage_TTL = 5   # idk if pin 1, 3.3V work safe!
#gnd_TTL  = 20    # physical pin 20
trig_TTL = 25

# =========================================================
# 2) SCAN INPUTS 
# =========================================================
WIDTH_MM  = 20   # X scan size
HEIGHT_MM = 10   # Y scan size
GRID_MM   = 1    # 1mm grid

# Spectrometer measurement time (placeholder)
INTEGRATION_TIME_S = 0.20

# Motion speed (start conservative)
SPEED_STEPS_PER_SEC = 500

# =========================================================
# 3) CALIBRATION (critical)
# "How many STEP pulses move 1 mm"
# You MUST set these for your mechanics (leadscrew/belt + microstep setting).
# =========================================================
STEPS_PER_MM_X = 800  # example
STEPS_PER_MM_Y = 800  # example

# =========================================================
# 4) ENABLE polarity (because of ULN2803A / wiring)
# If motors never move, try flipping this True <-> False
# =========================================================
ENA_ACTIVE_LOW = True


# ---------------------------------------------------------
# Low-level driver: sends STEP pulses, sets DIR, ENA
# WHY: microstep drivers only understand pulses + direction.
# ---------------------------------------------------------
class StepperDriver:
    def __init__(self, step_gpio, dir_gpio, ena_gpio=None, ena_active_low=True):
        self.step = DigitalOutputDevice(step_gpio, initial_value=False)
        self.dir  = DigitalOutputDevice(dir_gpio,  initial_value=False)

        self.ena = None
        self.ena_active_low = ena_active_low
        if ena_gpio is not None:
            self.ena = DigitalOutputDevice(ena_gpio, initial_value=False)
            self.enable()

    def enable(self):
        if not self.ena:
            return
        # WHY: depending on wiring, "enabled" might mean ENA is NOT being pulled low.
        if self.ena_active_low:
            self.ena.off()
        else:
            self.ena.on()

    def disable(self):
        if not self.ena:
            return
        if self.ena_active_low:
            self.ena.on()
        else:
            self.ena.off()

    def set_direction(self, direction: int):
        # direction >= 0 => one way, direction < 0 => opposite
        if direction >= 0:
            self.dir.on()
        else:
            self.dir.off()

        # WHY: give driver time to latch DIR before STEP pulses start (safe margin)
        sleep(0.001)

    def step_pulses(self, count: int, steps_per_sec: int):
        """
        Generates 'count' STEP pulses.
        WHY: each pulse moves the motor 1 (micro)step according to driver settings.
        """
        if count <= 0:
            return

        # period = time per step
        period = 1.0 / float(steps_per_sec)

        # STEP pulse width: keep comfortably above driver minimum
        on_time = 10e-6  # 10 microseconds
        off_time = max(0.0, period - on_time)

        for _ in range(count):
            self.step.on()
            sleep(on_time)
            self.step.off()
            sleep(off_time)


# ---------------------------------------------------------
# Mid-level XY stage: move in millimeters
# WHY: your task is in mm grid, not in raw steps.
# ---------------------------------------------------------
class XYStage:
    def __init__(self, motor_x: StepperDriver, motor_y: StepperDriver):
        self.mx = motor_x
        self.my = motor_y

    def move_x_mm(self, mm: float, steps_per_mm: int, speed_sps: int):
        direction = 1 if mm >= 0 else -1
        steps = int(abs(mm) * steps_per_mm)
        self.mx.set_direction(direction)
        self.mx.step_pulses(steps, speed_sps)

    def move_y_mm(self, mm: float, steps_per_mm: int, speed_sps: int):
        direction = 1 if mm >= 0 else -1
        steps = int(abs(mm) * steps_per_mm)
        self.my.set_direction(direction)
        self.my.step_pulses(steps, speed_sps)


# ---------------------------------------------------------
# Spectrometer measurement placeholder
# WHY: you said "measurement of spectrometer (taking time)"
# Replace the sleep() with real spectrometer code later.
# ---------------------------------------------------------
def measure_spectrum(x_mm: int, y_mm: int, trig_out: DigitalOutputDevice | None):
    """
    Optionally pulse TRIG_OUT, wait integration time, return a measurement result.
    """
    if trig_out is not None:
        # short pulse to trigger external device
        trig_out.on()
        sleep(0.005)
        trig_out.off()

    # simulate integration / acquisition time
    sleep(INTEGRATION_TIME_S)

    # TODO: replace with real spectrum value(s)
    fake_value = 123.456
    return {"x_mm": x_mm, "y_mm": y_mm, "value": fake_value, "t": time()}


def append_csv(row: dict, filename="scan_results.csv"):
    import os
    new = not os.path.exists(filename)
    with open(filename, "a", encoding="utf-8") as f:
        if new:
            f.write("t,x_mm,y_mm,value\n")
        f.write(f"{row['t']},{row['x_mm']},{row['y_mm']},{row['value']}\n")


# ---------------------------------------------------------
# Raster scan logic
# WHY: divides area into 1mm grid and moves until done.
# Uses "serpentine" pattern to reduce wasted travel.
# ---------------------------------------------------------
def raster_scan(stage: XYStage, start_in: DigitalInputDevice, stop_in: DigitalInputDevice,
               trig_out: DigitalOutputDevice | None):
    # Wait for optic trigger (START)
    print("Waiting for START TTL (optic trigger)...")
    start_in.wait_for_active()
    print("START detected. Beginning scan.")

    # Compute number of points (include both ends)
    x_points = int(WIDTH_MM / GRID_MM) + 1
    y_points = int(HEIGHT_MM / GRID_MM) + 1
    print(f"Grid: {x_points} x {y_points} points, step={GRID_MM}mm")

    # IMPORTANT assumption:
    # You already positioned the stage at the scan origin (0,0) physically or via homing.

    for y in range(y_points):
        if stop_in.is_active:
            print("STOP detected -> aborting scan.")
            return

        # Serpentine direction per row:
        # even row: left->right, odd row: right->left
        x_range = range(x_points) if (y % 2 == 0) else range(x_points - 1, -1, -1)

        for x in x_range:
            if stop_in.is_active:
                print("STOP detected -> aborting scan.")
                return

            # 1) Spectrometer measurement at current point
            x_mm = x * GRID_MM
            y_mm = y * GRID_MM
            result = measure_spectrum(x_mm, y_mm, trig_out)
            append_csv(result)
            print(f"Measured at ({x_mm},{y_mm}) -> {result['value']}")

            # 2) Move X to next grid point (unless end of row)
            is_end_of_row = (x == x_points - 1) if (y % 2 == 0) else (x == 0)
            if not is_end_of_row:
                step_dir = +1 if (y % 2 == 0) else -1
                stage.move_x_mm(step_dir * GRID_MM, STEPS_PER_MM_X, SPEED_STEPS_PER_SEC)

        # 3) After finishing the row, move Y up one grid step (unless last row)
        if y != y_points - 1:
            stage.move_y_mm(GRID_MM, STEPS_PER_MM_Y, SPEED_STEPS_PER_SEC)

    print("Scan completed successfully.")


def main():
    # TTL inputs
    start_in = DigitalInputDevice(START_TTL_IN, pull_down=True)
    stop_in  = DigitalInputDevice(STOP_TTL_IN,  pull_down=True)

    # Optional TTL output
    trig_out = DigitalOutputDevice(TRIG_OUT, initial_value=False) if TRIG_OUT is not None else None

    # Drivers
    mx = StepperDriver(M1_STEP, M1_DIR, M1_ENA, ena_active_low=ENA_ACTIVE_LOW)
    my = StepperDriver(M2_STEP, M2_DIR, M2_ENA, ena_active_low=ENA_ACTIVE_LOW)

    stage = XYStage(mx, my)

    try:
        raster_scan(stage, start_in, stop_in, trig_out)
    finally:
        # WHY: always leave drivers in a safe state even if aborted
        mx.disable()
        my.disable()
        if trig_out is not None:
            trig_out.off()
        print("Motors disabled. Program end.")


if __name__ == "__main__":
    main()
