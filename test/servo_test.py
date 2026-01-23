from gpiozero import Servo
from time import sleep

servo = Servo(
    18,
    min_pulse_width=0.5/1000,
    max_pulse_width=2.5/1000
)

while True:
    print("0°")
    servo.min()
    sleep(1)

    print("90°")
    servo.mid()
    sleep(1)

    print("180°")
    servo.max()
    sleep(1)
