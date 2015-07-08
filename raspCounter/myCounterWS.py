#!/usr/bin/env python2.7
import time
import datetime
import RPIO
import urllib
import urllib2
import os.path
import json
import sys
from socketIO_client import SocketIO, LoggingNamespace

#GPIO.setmode(GPIO.BCM)

class counterObj: 
    def __init__(self, gpioPin,counterType,machineID,totalcount,offline):
        self.counterType = counterType  
        self.gpioPin = gpioPin
        self.machineID = machineID
        self.totalcount = totalcount
        self.publish = False
        self.offline = False
        
        
    def add_tick(self, tick):
        self.totalcount = self.totalcount + 1
        self.publish = True
        
        
Machines = {}
Counters = {}
ConfigVals = {}
onlineMode = True

#time.sleep(int(120))
print "Hi, Starting .... if your reading this call 480-249-1942"
print "Parameters in File: "
print " "

with open('/media/USBHDD/projects/gpioCounter/config/endpoint.config') as c:
    for line in c:
        line = line.rstrip()
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
        print mySetupList
    
    
    

HEART_BEAT_URL = ConfigVals["HEART_BEAT_URL"]
BOXMODE = 'OFFLINE'
BOXDEBUG = ConfigVals["BOXDEBUG"]
BOXID = ConfigVals["BOXID"]
COUNTERVAL_URL = ConfigVals["COUNTERVAL_URL"]
COUNTERPOST_URL= ConfigVals["COUNTERPOST_URL"]
SLEEP_SECONDS= ConfigVals["SLEEP_SECONDS"]





def my_logprint(message):
    if BOXDEBUG == 'True':
        print message    
        sys.stdout.flush()

def on_get_box_status(args):
    my_logprint("HeartBeaT for " + args['boxid']);
    socketIO.emit('on_get_box_status', {"boxid":args['boxid']})
    
def on_gpio_offline_response(args):
    my_logprint("GPIO  OFFLINE" + args['gpio_id']);
    myOfflineCount = Counters[str(args['gpio_id'])]
    myOfflineCount.offline = True
    
    
def on_gpio_online_response(args):
    my_logprint("GPIO  ONLINE" + args['gpio_id']);
    myOfflineCount = Counters[str(args['gpio_id'])]
    myOfflineCount.offline = False
    myOfflineCount.publish = False
    myOfflineCount.totalcount = args['totalcount'] 
    

    

def on_auth_response(args):
    my_logprint("Handshake resp")
    my_logprint(args)
    Counters={}
    if args['isvalid']:
        my_logprint('valid')
        Machines = args['machines']
        #need to get total count for each pin from web
        for m in Machines:
            tempCounter = counterObj(str(m['gpioPin']),m['counterType'],m['machineID'],0,0)
            Counters[str(m['gpioPin'])] = tempCounter
            RPIO.add_interrupt_callback(int(m['gpioPin']), my_callback,edge='falling',pull_up_down=RPIO.PUD_UP,\
                                 threaded_callback=True,debounce_timeout_ms=100)

    else:
        socketIO.emit('auth_nogo')
        #TODO: EXIT  


    
def my_callback(gpio_id, val):
    myCallBackCount = Counters[str(gpio_id)]
    myCallBackCount.add_tick(1)
    my_logprint("Edge detected on " + str(gpio_id) + " Total Amt : " + str(myCallBackCount.totalcount))
    
   
        
def publish_counters():
    for k in Counters.keys():
        myCounter = Counters[str(k)]
        if myCounter.publish == True and myCounter.offline == False:
            my_logprint("Found Publish for Pin " + k)
            socketIO.emit('publish_counter', {"machineID":myCounter.machineID,\
                        "gpio_id":myCounter.gpioPin,"totalcount":myCounter.totalcount,"counter_type":myCounter.counterType})
            myCounter.publish = False
            my_logprint("Publish Success for Pin " + k)
                       
            

    
#*********  START UP END ********************************     


try:
    socketIO = SocketIO(HEART_BEAT_URL,3000 ,LoggingNamespace, params={"boxid":BOXID,"type":"PI"}) 
    socketIO.on('on_auth', on_auth_response)
    socketIO.on('on_gpio_offline', on_gpio_offline_response)
    socketIO.on('on_gpio_online', on_gpio_online_response)
    socketIO.on('on_get_box_status', on_get_box_status)
    socketIO.wait(seconds=1) 
    
    
    RPIO.wait_for_interrupts(threaded=True)
    
    
    my_logprint("Listenin ... " ) 
    
    while(1):
        #time.sleep(int(SLEEP_SECONDS))
        publish_counters()
        socketIO.wait(seconds=1)
       
          
    

except KeyboardInterrupt:
    RPIO.cleanup()       # clean up GPIO on CTRL+C exit
RPIO.cleanup()           # clean up GPIO on normal exit
