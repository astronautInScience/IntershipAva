import RPi.GPIO as GPIO
import time

# -----------------------------
# User settings
# -----------------------------
LED_SIG_PIN = 17          # MOSFET SIG connected to GPIO17
ACTIVE_HIGH = True        # True if GPIO HIGH turns LED on
PULSE_ON_MS = 1000          # LED ON time
PULSE_OFF_MS = 1000       # LED OFF time between flashes

# -----------------------------
# Setup
# -----------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED_SIG_PIN, GPIO.OUT)

def set_led(state):
    if ACTIVE_HIGH:
        GPIO.output(LED_SIG_PIN, GPIO.HIGH if state else GPIO.LOW)
    else:
        GPIO.output(LED_SIG_PIN, GPIO.LOW if state else GPIO.HIGH)

try:
    set_led(False)
    time.sleep(1)

    while True:
        # Flash ON
        set_led(True)
        time.sleep(PULSE_ON_MS / 1000.0)

        # OFF
        set_led(False)
        time.sleep(PULSE_OFF_MS / 1000.0)

except KeyboardInterrupt:
    pass

finally:
    set_led(False)
    GPIO.cleanup()
