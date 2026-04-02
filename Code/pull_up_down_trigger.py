import RPi.GPIO as GPIO
import time

TRIGGER_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

last = GPIO.input(TRIGGER_PIN)
print("Initial level:", last, "->", "HIGH" if last else "LOW")

try:
    while True:
        val = GPIO.input(TRIGGER_PIN)
        if val != last:
            print("Changed:", last, "->", val, "at", time.perf_counter())
            last = val
        time.sleep(0.001)   # 1 ms poll
except KeyboardInterrupt:
    print("Stopped")
finally:
    GPIO.cleanup()
