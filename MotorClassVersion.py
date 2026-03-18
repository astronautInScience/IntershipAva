import time
from dataclasses import dataclass
import pigpio

# =========================
# PIN MAPPING (BCM)
# =========================
M1_STEP, M1_DIR = 18, 23  # X axis
M2_STEP, M2_DIR = 5, 6    # Y axis

# =========================
# TRANSISTOR SINKING LOGIC
# True means logical HIGH/LOW are inverted on the physical GPIO pin.
# =========================
INVERT_STEP = True
INVERT_DIR = True

# =========================
# MOTION SETTINGS
# =========================
STEP_FREQ_HZ = 500
STEP_PULSE_US = 1000
DIR_SETUP_S = 0.002
EDGE_DWELL_S = 0.2
RECTANGLE_LOOPS = 1  # 1 = run once, 0 = run forever

# =========================
# CALIBRATION (EDIT THESE)
# steps/cm = (motor_steps_per_rev * microstep * 10) / mm_per_rev
# =========================
MOTOR_FULL_STEPS_PER_REV = 200
MICROSTEP = 16
X_MM_PER_REV = 8.0
Y_MM_PER_REV = 8.0

X_STEPS_PER_CM = (MOTOR_FULL_STEPS_PER_REV * MICROSTEP * 10.0) / X_MM_PER_REV
Y_STEPS_PER_CM = (MOTOR_FULL_STEPS_PER_REV * MICROSTEP * 10.0) / Y_MM_PER_REV

# If one axis moves opposite of expected, flip 1 <-> 0.
X_POSITIVE_DIR = 0  # +X means stage moves right
Y_POSITIVE_DIR = 1  # +Y means stage moves up

# Requested rectangle:
# 1) +5 cm in X (right)
# 2) +35 cm in Y (up)
# 3) -5 cm in X (left)
# 4) -35 cm in Y (down)
RECTANGLE_PATH_CM = [
    ("X +5 cm (right)", "x", +5.0),
    ("Y +35 cm (up)", "y", +35.0),
    #("X -5 cm (left)", "x", -5.0),
    #("Y -35 cm (down)", "y", -35.0),
]


def inv(level: int, do_inv: bool) -> int:
    return (1 - level) if do_inv else level


@dataclass
class AxisConfig:
    name: str
    step_pin: int
    dir_pin: int
    steps_per_cm: float
    positive_dir: int


class StepperAxis:
    def __init__(self, pi: pigpio.pi, cfg: AxisConfig):
        self.pi = pi
        self.cfg = cfg

        self.pi.set_mode(cfg.step_pin, pigpio.OUTPUT)
        self.pi.set_mode(cfg.dir_pin, pigpio.OUTPUT)

        # Idle logical LOW on both lines.
        self._write_logic(cfg.step_pin, 0, INVERT_STEP)
        self._write_logic(cfg.dir_pin, 0, INVERT_DIR)

    def _write_logic(self, pin: int, logic_level: int, invert: bool) -> None:
        self.pi.write(pin, inv(logic_level, invert))

    def _set_direction(self, positive: bool) -> None:
        logic_dir = self.cfg.positive_dir if positive else (1 - self.cfg.positive_dir)
        self._write_logic(self.cfg.dir_pin, logic_dir, INVERT_DIR)
        time.sleep(DIR_SETUP_S)

    def move_cm(self, distance_cm: float, freq_hz: int, pulse_us: int) -> None:
        steps = int(round(abs(distance_cm) * self.cfg.steps_per_cm))
        positive = distance_cm >= 0.0
        self.move_steps(steps, positive, freq_hz, pulse_us)

    def move_steps(self, steps: int, positive: bool, freq_hz: int, pulse_us: int) -> None:
        if steps <= 0:
            return
        if freq_hz <= 0:
            raise ValueError("freq_hz must be > 0")

        self._set_direction(positive)
        self._pulse_with_wave(steps, freq_hz, pulse_us)

    def _pulse_with_wave(self, steps: int, freq_hz: int, pulse_us: int) -> None:
        period_us = max(2, int(round(1_000_000.0 / float(freq_hz))))
        high_us = max(1, min(int(pulse_us), period_us - 1))
        low_us = period_us - high_us

        step_mask = 1 << self.cfg.step_pin

        high_phys = inv(1, INVERT_STEP)
        low_phys = inv(0, INVERT_STEP)

        pulse_high = pigpio.pulse(step_mask, 0, high_us) if high_phys else pigpio.pulse(0, step_mask, high_us)
        pulse_low = pigpio.pulse(step_mask, 0, low_us) if low_phys else pigpio.pulse(0, step_mask, low_us)

        self.pi.wave_clear()
        self.pi.wave_add_generic([pulse_high, pulse_low])
        wid = self.pi.wave_create()
        if wid < 0:
            raise RuntimeError(f"wave_create failed on axis {self.cfg.name} with code {wid}")

        try:
            remaining = steps
            while remaining > 0:
                chunk = min(remaining, 65535)
                self.pi.wave_chain([255, 0, wid, 255, 1, chunk & 0xFF, (chunk >> 8) & 0xFF])
                while self.pi.wave_tx_busy():
                    time.sleep(0.001)
                remaining -= chunk
        finally:
            self.pi.wave_delete(wid)
            self._write_logic(self.cfg.step_pin, 0, INVERT_STEP)


def run_rectangle(x_axis: StepperAxis, y_axis: StepperAxis) -> None:
    axes = {"x": x_axis, "y": y_axis}
    loop_count = 0

    while RECTANGLE_LOOPS == 0 or loop_count < RECTANGLE_LOOPS:
        loop_count += 1
        print(f"\nRectangle loop {loop_count}")

        for label, axis_key, distance_cm in RECTANGLE_PATH_CM:
            axis = axes[axis_key]
            est_steps = int(round(abs(distance_cm) * axis.cfg.steps_per_cm))
            print(f"{label}: {est_steps} steps @ {STEP_FREQ_HZ} Hz")
            axis.move_cm(distance_cm, STEP_FREQ_HZ, STEP_PULSE_US)
            time.sleep(EDGE_DWELL_S)


def main() -> None:
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError(
            "Cannot connect to pigpio daemon.\n"
            "Install/start it on Raspberry Pi:\n"
            "  sudo apt install pigpio python3-pigpio\n"
            "  sudo systemctl enable --now pigpiod"
        )

    """x_axis = StepperAxis(
        pi,
        AxisConfig(
            name="X",
            step_pin=M1_STEP,
            dir_pin=M1_DIR,
            steps_per_cm=X_STEPS_PER_CM,
            positive_dir=X_POSITIVE_DIR,
        ),
    )
    """
    y_axis = StepperAxis(
        pi,
        AxisConfig(
            name="Y",
            step_pin=M2_STEP,
            dir_pin=M2_DIR,
            steps_per_cm=Y_STEPS_PER_CM,
            positive_dir=Y_POSITIVE_DIR,
        ),
    )

    try:
        print("Driver ENA must be enabled by wiring/switches.")
        print("Running rectangle path: +X 5 cm, +Y 35 cm, -X 5 cm, -Y 35 cm.")
        run_rectangle(x_axis, y_axis)
    except KeyboardInterrupt:
        print("\nCTRL+C detected.")
    finally:
        pi.wave_tx_stop()
        pi.wave_clear()
        pi.stop()


if __name__ == "__main__":
    main()
