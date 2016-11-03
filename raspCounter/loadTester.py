import time
import RPIO as GPIO

counter = 0
try:
    TRIG = 20
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG,GPIO.OUT,pull_up_down=GPIO.PUD_DOWN)
    while(True):
        GPIO.output(TRIG, True)
        counter = counter + 1
        print str(counter)
        time.sleep(0.5)




except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
GPIO.cleanup()