#!/usr/bin/env python2.7
import time
import RPi.GPIO as GPIO
import urllib
import urllib2
GPIO.setmode(GPIO.BCM)

class counterObj: 
    def __init__(self, gpioPin,counterType,machineName,totalcount):
        self.counterType = counterType  
        self.gpioPin = gpioPin
        self.machineName = machineName
        self.totalcount = totalcount
        self.publish = False
        
        
    def add_tick(self, tick):
        self.totalcount = self.totalcount + 1
        print "total count = " + str(self.totalcount)
        self.publish = True
        
Counters = {}
ConfigVals = {}

with open('/home/pi/projects/gpioCounter/config/endpoint.config') as c:
    for line in c:
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
    
    
    
print ConfigVals,

with open('/home/pi/projects/gpioCounter/config/counters.config') as f:
    for line in f:
        myList = line.split()
        print "gpio_pin:" + str(myList[0])
        gpio_pin = str(myList[0])
        print "type:" + str(myList[1])
        counterType = str(myList[1])
        print "machine:" + str(myList[2])
        machineID = str(myList[2])
        tempCounter = counterObj(gpio_pin,counterType,machineID,0)
        
        Counters[gpio_pin] = tempCounter

print "Config file loaded ..."


for k in Counters.keys():
    #print "current key:" + str(k)
    GPIO.setup(int(k), GPIO.IN, pull_up_down=GPIO.PUD_UP)
     


def my_callback(channel):
    myCallBackCount = Counters[str(channel)]
    myCallBackCount.add_tick(1)
    print "rising edge detected on " + str(channel)



def myHttpPost(channel):
    myChannelCounter = Counters[channel]
    values = dict(machineID=myChannelCounter.machineName, counterType=myChannelCounter.counterType, totalCount=str(myChannelCounter.totalcount))
    print values
    params = urllib.urlencode(values)
    url = endpointAddress 
    print "posting to " + url
    req = urllib2.Request(url, params)
    response = urllib2.urlopen(req)
    data = response.read()
    print data,
    
    
    

    
for k1 in Counters.keys():
    print "current key " + str(k1)
    GPIO.add_event_detect(int(k1), GPIO.RISING, callback=my_callback, bouncetime=300)



try:
    
    
    print "Monitoring GPIO ..."
    while(1):
        for c1 in Counters.keys():
            myCurrentCounter = Counters[str(c1)]
            if myCurrentCounter.publish == True:
                print "counter change found for " + str(myCurrentCounter.gpioPin)
                myHttpPost(myCurrentCounter.gpioPin)
                myCurrentCounter.publish = False
        time.sleep( 5 ) 
        
        
          
    

except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
GPIO.cleanup()           # clean up GPIO on normal exit
