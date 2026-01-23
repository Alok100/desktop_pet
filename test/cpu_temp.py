import subprocess
import time

def get_cpu_temp():
    output = subprocess.check_output(
        ["vcgencmd", "measure_temp"]
    ).decode()
    return output.strip()

while True:
    print(get_cpu_temp())
    time.sleep(2)

