import RPi.GPIO as GPIO
import time

TRIGGER_INPUT_PIN = 17

def edge_callback(channel):
    level = GPIO.input(channel)
    print(f"Edge detected on GPIO {channel}, level now = {level}")

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Try this first
GPIO.setup(TRIGGER_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print("Monitoring GPIO17...")
print("Press Ctrl+C to stop")
print("Initial level:", GPIO.input(TRIGGER_INPUT_PIN))

GPIO.add_event_detect(TRIGGER_INPUT_PIN, GPIO.BOTH, callback=edge_callback, bouncetime=20)

try:
    while True:
        print("Current level:", GPIO.input(TRIGGER_INPUT_PIN))
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
