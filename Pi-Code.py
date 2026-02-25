"""
XY Stage Scanner for Spectrometer Measurements
Controls 2-axis stepper motor stages via microstep drivers (STEP/DIR/ENA).

"""

import os
import sys
from gpiozero import DigitalOutputDevice, DigitalInputDevice
from time import sleep, time
from typing import Optional, Dict
from dataclasses import dataclass


# =========================================================
# 1) HARDWARE CONFIGURATION
# =========================================================

@dataclass
class PinConfig:
    # Motor 1 (X axis)
    m1_step: int = 18
    m1_dir: int = 23
    m1_ena: int = 24
    
    # Motor 2 (Y axis)
    m2_step: int = 5
    m2_dir: int = 6
    m2_ena: int = 13
    
    # TTL inputs (external trigger signals)
    start_ttl_in: int = 25  # Start scan trigger pin 4 in wire
    #stop_ttl_in: int = 20   # Abort scan trigger
    
    # Optional TTL output (spectrometer trigger)
    #trig_out: Optional[int] = 24
    
    # Enable polarity: True if ULN2803A driver pulls low to enable
    ena_active_low: bool = True


# =========================================================
# 2) SCAN PARAMETERS
# =========================================================

@dataclass
class ScanConfig:
    """Scan geometry and motion parameters."""
    # Scan area
    width_mm: float = 20.0       # X axis scan range
    height_mm: float = 10.0      # Y axis scan range
    grid_spacing_mm: float = 1.0 # Distance between measurement points
    
    # Motor calibration
    steps_per_mm_x: int = 800    # Steps/mm for X motor (adjust per your mechanics)
    steps_per_mm_y: int = 800    # Steps/mm for Y motor
    
    # Motion speed
    speed_steps_per_sec: int = 500  # Pulse frequency (Hz)
    
    # Spectrometer timing
    integration_time_s: float = 0.20  # Acquisition time per point
    
    # Output
    csv_filename: str = "scan_results.csv"


# =========================================================
# 3) LOW-LEVEL STEPPER DRIVER
# =========================================================

class StepperDriver:
    """
    Controls a single stepper motor via STEP/DIR/ENA signals.
    
    Interface:
    - STEP: pulse to advance 1 microstep
    - DIR:  logic level sets direction (typically high=+, low=-)
    - ENA:  enable/disable (polarity depends on driver chip)
    
    WHY: Microstep drivers only understand these three signals.
    The driver chip (e.g., DRV8825) internally counts pulses.
    """
    
    def __init__(self, 
                 step_gpio: int, 
                 dir_gpio: int, 
                 ena_gpio: Optional[int] = None,
                 ena_active_low: bool = True,
                 step_pulse_width_us: float = 10.0):
        """
        Args:
            step_gpio: GPIO pin for STEP signal
            dir_gpio: GPIO pin for DIRECTION signal
            ena_gpio: GPIO pin for ENABLE (optional)
            ena_active_low: True if driver activates on low signal
            step_pulse_width_us: Pulse width in microseconds (keep >driver minimum)
        """
        self.step = DigitalOutputDevice(step_gpio, initial_value=False)
        self.dir = DigitalOutputDevice(dir_gpio, initial_value=False)
        self.ena_active_low = ena_active_low
        
        self.ena: Optional[DigitalOutputDevice] = None
        if ena_gpio is not None:
            self.ena = DigitalOutputDevice(ena_gpio, initial_value=False)
            self.enable()  # Enable on startup
        
        self.step_pulse_width_us = step_pulse_width_us

    def enable(self) -> None:
        """Activate motor (allows current flow to coils)."""
        if self.ena is None:
            return
        # Logic depends on driver: ULN2803A/DRV8825 vs others differ
        if self.ena_active_low:
            self.ena.off()  # Pull low to enable
        else:
            self.ena.on()   # Pull high to enable

    def disable(self) -> None:
        """Deactivate motor (no current, free to move if not holding)."""
        if self.ena is None:
            return
        if self.ena_active_low:
            self.ena.on()   # Pull high to disable
        else:
            self.ena.off()  # Pull low to disable

    def set_direction(self, positive: bool) -> None:
        """
        Set motor direction before stepping.
        
        Args:
            positive: True for + direction, False for - direction
        
        WHY: DIR must settle before STEP pulses (setup time).
        """
        self.dir.on() if positive else self.dir.off()
        sleep(0.001)  # DIR setup time (1 ms margin for safety)

    def step_pulses(self, count: int, steps_per_sec: int) -> None:
        """
        Generate STEP pulses at specified frequency.
        
        Each pulse advances motor by 1 microstep (16x, 32x, etc. depends on driver).
        Timing: pulse_high_time + pulse_low_time = 1 / steps_per_sec
        
        Args:
            count: Number of STEP pulses to generate
            steps_per_sec: Frequency in Hz
        
        WHY: Python's sleep() has ~1ms granularity, so high-freq stepping
        (e.g., >1 kHz) will be imprecise. Consider external PWM for high speed.
        """
        if count <= 0:
            return

        period_s = 1.0 / float(steps_per_sec)
        on_time_s = self.step_pulse_width_us * 1e-6
        off_time_s = max(0.0, period_s - on_time_s)

        for _ in range(count):
            self.step.on()
            sleep(on_time_s)
            self.step.off()
            sleep(off_time_s)


# =========================================================
# 4) MID-LEVEL XY STAGE CONTROLLER
# =========================================================

class XYStage:
    """
    Combines two stepper drivers into a coordinated XY scanner.
    Converts millimeter moves into step commands.
    """
    
    def __init__(self, motor_x: StepperDriver, motor_y: StepperDriver):
        self.mx = motor_x
        self.my = motor_y

    def move_x_mm(self, 
                  mm: float, 
                  steps_per_mm: int, 
                  speed_sps: int) -> None:
        """Move X axis by delta (mm)."""
        positive = mm >= 0
        steps = int(abs(mm) * steps_per_mm)
        self.mx.set_direction(positive)
        self.mx.step_pulses(steps, speed_sps)

    def move_y_mm(self, 
                  mm: float, 
                  steps_per_mm: int, 
                  speed_sps: int) -> None:
        """Move Y axis by delta (mm)."""
        positive = mm >= 0
        steps = int(abs(mm) * steps_per_mm)
        self.my.set_direction(positive)
        self.my.step_pulses(steps, speed_sps)

    def move_xy_mm(self, 
                   x_mm: float, 
                   y_mm: float, 
                   steps_per_mm_x: int,
                   steps_per_mm_y: int,
                   speed_sps: int) -> None:
        """Move both axes sequentially. For parallel motion, use threading."""
        self.move_x_mm(x_mm, steps_per_mm_x, speed_sps)
        self.move_y_mm(y_mm, steps_per_mm_y, speed_sps)


# =========================================================
# 5) SPECTROMETER MEASUREMENT & DATA LOGGING
# =========================================================

def measure_spectrum(x_mm: float, 
                    y_mm: float,
                    trig_out: Optional[DigitalOutputDevice] = None) -> Dict:
    """
    Acquire one measurement point.
    
    TODO: Replace sleep() with actual spectrometer communication
    (USB, SPI, I2C, serial, etc.)
    
    Args:
        x_mm, y_mm: Position labels for logging
        trig_out: Optional GPIO output to pulse external device
    
    Returns:
        Dict with timestamp, position, and measurement value(s)
    """
    if trig_out is not None:
        # Pulse external spectrometer or camera trigger
        trig_out.on()
        sleep(0.005)  # 5 ms pulse
        trig_out.off()
    
    # SIMULATE integration time
    sleep(0.20)  # Replace with real spectrometer.read()
    
    # PLACEHOLDER: replace with actual spectrum data
    # Real version might return: {"wavelength": [...], "intensity": [...]}
    fake_value = 123.456
    
    return {
        "t": time(),
        "x_mm": x_mm,
        "y_mm": y_mm,
        "value": fake_value
    }


def append_csv(row: Dict, filename: str = "scan_results.csv") -> None:
    """
    Append measurement to CSV file (create header if new).
    
    WHY: Write-after-each-point prevents data loss on crash.
    """
    is_new_file = not os.path.exists(filename)
    
    try:
        with open(filename, "a", encoding="utf-8") as f:
            if is_new_file:
                f.write("t,x_mm,y_mm,value\n")
            f.write(f"{row['t']:.3f},{row['x_mm']:.2f},{row['y_mm']:.2f},{row['value']:.6f}\n")
    except IOError as e:
        print(f"ERROR: Failed to write CSV: {e}", file=sys.stderr)


# =========================================================
# 6) RASTER SCAN LOGIC
# =========================================================

def raster_scan(stage: XYStage,
               start_in: DigitalInputDevice,
               stop_in: DigitalInputDevice,
               scan_cfg: ScanConfig,
               trig_out: Optional[DigitalOutputDevice] = None) -> bool:
    """
    Execute 2D raster scan in serpentine pattern.
    
    Pattern benefits:
    - Minimizes Y movement (slow axis)
    - Reduces travel time between rows
    - Natural for push-broom spectroscopy
    
    Args:
        stage: XY stage controller
        start_in, stop_in: TTL input devices
        scan_cfg: Scan parameters
        trig_out: Optional TTL output trigger
    
    Returns:
        True if scan completed normally, False if aborted
    """
    
    # Wait for external start trigger (e.g., from optics)
    print("Waiting for START signal (TTL)...")
    start_in.wait_for_active()
    print("START detected. Beginning scan.\n")
    
    # Calculate grid dimensions
    x_points = int(scan_cfg.width_mm / scan_cfg.grid_spacing_mm) + 1
    y_points = int(scan_cfg.height_mm / scan_cfg.grid_spacing_mm) + 1
    
    print(f"Scan grid: {x_points} × {y_points} points")
    print(f"Spacing: {scan_cfg.grid_spacing_mm} mm")
    print(f"Total area: {scan_cfg.width_mm} × {scan_cfg.height_mm} mm\n")
    
    # ASSUMPTION: Stage is homed at (0, 0) before scan starts
    # TODO: Add explicit homing sequence if needed
    
    measurement_count = 0
    
    try:
        for y_idx in range(y_points):
            # Check STOP signal between rows (safer than per-point)
            if stop_in.is_active:
                print("\n⚠ STOP signal detected. Aborting scan.")
                return False
            
            # Serpentine pattern: alternate X direction each row
            x_direction = range(x_points) if (y_idx % 2 == 0) else range(x_points - 1, -1, -1)
            
            for x_idx in x_direction:
                # Check STOP before expensive measurement
                if stop_in.is_active:
                    print("\n⚠ STOP signal detected. Aborting scan.")
                    return False
                
                # Current position in mm
                x_mm = x_idx * scan_cfg.grid_spacing_mm
                y_mm = y_idx * scan_cfg.grid_spacing_mm
                
                # 1) ACQUIRE data
                result = measure_spectrum(x_mm, y_mm, trig_out)
                append_csv(result, scan_cfg.csv_filename)
                measurement_count += 1
                
                print(f"[{measurement_count:3d}] ({x_mm:5.1f}, {y_mm:5.1f}) mm → {result['value']:.3f}")
                
                # 2) MOVE X to next point (unless end of row)
                is_last_x = (x_idx == x_points - 1) if (y_idx % 2 == 0) else (x_idx == 0)
                if not is_last_x:
                    step_dir = 1.0 if (y_idx % 2 == 0) else -1.0
                    delta_mm = step_dir * scan_cfg.grid_spacing_mm
                    stage.move_x_mm(delta_mm, 
                                   scan_cfg.steps_per_mm_x, 
                                   scan_cfg.speed_steps_per_sec)
            
            # 3) MOVE Y to next row (unless last row)
            if y_idx != y_points - 1:
                stage.move_y_mm(scan_cfg.grid_spacing_mm,
                               scan_cfg.steps_per_mm_y,
                               scan_cfg.speed_steps_per_sec)
        
        print(f"\n✓ Scan completed successfully. {measurement_count} points logged.")
        return True
    
    except KeyboardInterrupt:
        print("\n⚠ Keyboard interrupt. Stopping scan.")
        return False


# =========================================================
# 7) MAIN PROGRAM
# =========================================================

def main():
    """Initialize hardware and execute scan sequence."""
    
    # Load configuration
    pins = PinConfig()
    scan = ScanConfig()
    
    print("=" * 60)
    print("XY Stage Spectrometer Scanner")
    print("=" * 60)
    print(f"Pins:   X=[{pins.m1_step},{pins.m1_dir},{pins.m1_ena}] "
          f"Y=[{pins.m2_step},{pins.m2_dir},{pins.m2_ena}]")
    print(f"Motors: {scan.steps_per_mm_x} steps/mm X, {scan.steps_per_mm_y} steps/mm Y")
    print(f"Speed:  {scan.speed_steps_per_sec} steps/sec\n")
    
    # Initialize GPIO devices
    start_in = DigitalInputDevice(pins.start_ttl_in, pull_down=True)
    stop_in = DigitalInputDevice(pins.stop_ttl_in, pull_down=True)
    trig_out = (DigitalOutputDevice(pins.trig_out, initial_value=False) 
                if pins.trig_out is not None else None)
    
    # Initialize stepper drivers
    mx = StepperDriver(pins.m1_step, pins.m1_dir, pins.m1_ena, 
                       ena_active_low=pins.ena_active_low)
    my = StepperDriver(pins.m2_step, pins.m2_dir, pins.m2_ena,
                       ena_active_low=pins.ena_active_low)
    
    stage = XYStage(mx, my)
    
    try:
        # Execute scan
        success = raster_scan(stage, start_in, stop_in, scan, trig_out)
        
        # Return status
        exit_code = 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        exit_code = 2
    
    finally:
        # CRITICAL: Always disable motors safely
        print("\nShutting down...")
        mx.disable()
        my.disable()
        if trig_out is not None:
            trig_out.off()
        print("✓ Motors disabled. Program end.\n")
        
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
