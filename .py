import time
from dataclasses import dataclass
import pigpio

# =========================
# PIN MAPPING (BCM) - Y axis only
# =========================
Y_STEP, Y_DIR = 5, 6

# =========================
# ULN2803A sinking logic
# If your ULN wiring requires inversion, keep True.
# If direction is reversed, flip Y_POSITIVE_DIR (below) first.
# =========================
INVERT_STEP = True
INVERT_DIR  = True

# =========================
# MOTION SETTINGS
# =========================
STEP_FREQ_HZ   = 500
STEP_PULSE_US  = 1000
DIR_SETUP_S    = 0.01
EDGE_DWELL_S   = 0.5
LOOPS          = 1    # 1 = run once, 0 = run forever

# =========================
# CALIBRATION (EDIT THESE)
# steps/cm = (motor_steps_per_rev * microstep * 10) / mm_per_rev
# =========================
MOTOR_FULL_STEPS_PER_REV = 200
MICROSTEP = 16
Y_MM_PER_REV = 8.0

Y_STEPS_PER_CM = (MOTOR_FULL_STEPS_PER_REV * MICROSTEP * 10.0) / Y_MM_PER_REV

# If Y moves opposite, flip this: 1 -> 0 or 0 -> 1
Y_POSITIVE_DIR = 1  # +Y means stage moves "up"

# Y-only path: up 35cm, down 35cm
Y_PATH_CM = [
    ("Y +35 cm (up)",   +35.0),
    ("Y -35 cm (down)", -35.0),
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

        # idle low (logical) on both lines
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

        # physical levels after inversion
        high_phys = inv(1, INVERT_STEP)  # what pigpio should output during "STEP active"
        low_phys  = inv(0, INVERT_STEP)

        pulse_high = pigpio.pulse(step_mask, 0, high_us) if high_phys else pigpio.pulse(0, step_mask, high_us)
        pulse_low  = pigpio.pulse(step_mask, 0, low_us)  if low_phys  else pigpio.pulse(0, step_mask, low_us)

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
            # return STEP to idle logical low
            self._write_logic(self.cfg.step_pin, 0, INVERT_STEP)

def main() -> None:
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError(
            "Cannot connect to pigpio daemon.\n"
            "Start it first (depending on your install):\n"
            "  sudo pigpiod\n"
        )

    y_axis = StepperAxis(
        pi,
        AxisConfig(
            name="Y",
            step_pin=Y_STEP,
            dir_pin=Y_DIR,
            steps_per_cm=Y_STEPS_PER_CM,
            positive_dir=Y_POSITIVE_DIR,
        ),
    )

    try:
        print("Y-axis only test. Driver ENA must be enabled by wiring/switches.")
        loop = 0
        while LOOPS == 0 or loop < LOOPS:
            loop += 1
            print(f"\nLoop {loop}")
            for label, dist_cm in Y_PATH_CM:
                est_steps = int(round(abs(dist_cm) * y_axis.cfg.steps_per_cm))
                print(f"{label}: {est_steps} steps @ {STEP_FREQ_HZ} Hz")
                y_axis.move_cm(dist_cm, STEP_FREQ_HZ, STEP_PULSE_US)
                time.sleep(EDGE_DWELL_S)

    except KeyboardInterrupt:
        print("\nCTRL+C detected.")
    finally:
        pi.wave_tx_stop()
        pi.wave_clear()
        pi.stop()

if __name__ == "__main__":
    main()
