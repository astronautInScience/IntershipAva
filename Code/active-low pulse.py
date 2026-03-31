import RPi.GPIO as GPIO
import time

TRIGGER_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Since your line was reading constant 1, use pull-up
GPIO.setup(TRIGGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Watching trigger output on GPIO17...")
print("Press Ctrl+C to stop")
print("Initial level:", GPIO.input(TRIGGER_PIN))

try:
    while True:
        # Wait for line to go LOW
        if GPIO.wait_for_edge(TRIGGER_PIN, GPIO.FALLING, timeout=2000):
            t_fall = time.time()
            print(f"FALLING edge at {t_fall:.6f}, level={GPIO.input(TRIGGER_PIN)}")

            # Wait for line to return HIGH
            if GPIO.wait_for_edge(TRIGGER_PIN, GPIO.RISING, timeout=2000):
                t_rise = time.time()
                print(f"RISING edge  at {t_rise:.6f}, level={GPIO.input(TRIGGER_PIN)}")
                print(f"Pulse width: {(t_rise - t_fall)*1000:.3f} ms\n")
            else:
                print("Line went LOW but did not return HIGH within timeout\n")
        else:
            print("No falling edge detected in 2 seconds")

except KeyboardInterrupt:
    print("Stopped by user")

finally:
    GPIO.cleanup()
