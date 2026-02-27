import RPi.GPIO as GPIO
import time

M1_STEP, M1_DIR, M1_ENA = 18, 23, 24

ENABLE_ACTIVE_LOW = True   # flip to False if nothing happens
STEP_FREQ_HZ = 800        
PULSE_US = 20

def ena_level(enable: bool) -> int:
    if ENABLE_ACTIVE_LOW:
        return GPIO.LOW if enable else GPIO.HIGH
    return GPIO.HIGH if enable else GPIO.LOW

def pulse_steps(step_pin, steps, freq_hz):
    period = 1.0 / freq_hz
    high_t = PULSE_US * 1e-6
    low_t = max(0.0, period - high_t)
    for _ in range(steps):
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(high_t)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(low_t)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup([M1_STEP, M1_DIR, M1_ENA], GPIO.OUT)
GPIO.output([M1_STEP, M1_DIR], GPIO.LOW)

try:
    print("ENABLE")
    GPIO.output(M1_ENA, ena_level(True))
    time.sleep(0.2)

    print("DIR forward, 10000 steps")
    GPIO.output(M1_DIR, GPIO.HIGH)
    time.sleep(0.01)
    pulse_steps(M1_STEP, 10000, STEP_FREQ_HZ)

    time.sleep(0.5)

    print("DIR backward, 10000 steps")
    GPIO.output(M1_DIR, GPIO.LOW)
    time.sleep(0.01)
    pulse_steps(M1_STEP, 10000, STEP_FREQ_HZ)

finally:
    print("DISABLE")
    GPIO.output(M1_ENA, ena_level(False))
    GPIO.cleanup()
