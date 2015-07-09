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
Counters={}




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
    
def httpGetReq(values,inboundURL):
    my_logprint(values)
    params = urllib.urlencode(values)
    my_logprint("httpGetRequest " + inboundURL)
    
    try:
        response = urllib2.urlopen(inboundURL + '?' + params)
        #onlineMode = True
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        #onlineMode = False
        data ={}
    except urllib2.URLError as e:
        my_logprint("URLError")
        #onlineMode = False
        data ={}
    else:
        data = response.read()
        response.close()
        my_logprint(data)
        
    return data 
    
def pullCounterValFromCloud(in_counterType,machineID):
    values = dict(machine_id=machineID)
    my_logprint(values)
    myData = httpGetReq(values,COUNTERVAL_URL)
    return myData
    

def on_auth_response(args):
    my_logprint("Handshake resp")
    my_logprint(args)
    pinCounterValueWeb_in = 0
    pinCounterValueWeb_out = 0
    if args['isvalid']:
        my_logprint('valid')
        Machines = args['machines']
        #need to get total count for each pin from web
        for m in Machines:
            myData = pullCounterValFromCloud('IN',m['machine_id'])
            myDataObj = json.loads(myData)
            for i in myDataObj:
                pinCounterValueWeb_in = int(i['max_in_count'])
                pinCounterValueWeb_out = int(i['max_out_count'])
            
            my_logprint('pinCounterValueWeb_in:' + str(pinCounterValueWeb_in))
            my_logprint('pinCounterValueWeb_out:' + str(pinCounterValueWeb_out))
            my_logprint('gpio_id_in:' + str(m['gpio_id_in']))
            my_logprint('gpio_id_out:' + str(m['gpio_id_out']))
            tempCounter_in = counterObj(str(m['gpio_id_in']),'IN',m['machine_id'],pinCounterValueWeb_in,0)
            tempCounter_out = counterObj(str(m['gpio_id_out']),'OUT',m['machine_id'],pinCounterValueWeb_out,0)
            Counters[str(m['gpio_id_in'])] = tempCounter_in
            Counters[str(m['gpio_id_out'])] = tempCounter_out
            RPIO.add_interrupt_callback(int(m['gpio_id_in']), my_callback,edge='falling',pull_up_down=RPIO.PUD_UP,\
                                 threaded_callback=True,debounce_timeout_ms=100)
            RPIO.add_interrupt_callback(int(m['gpio_id_out']), my_callback,edge='falling',pull_up_down=RPIO.PUD_UP,\
                                 threaded_callback=True,debounce_timeout_ms=100)

    else:
        socketIO.emit('auth_nogo')
        #TODO: EXIT  


    
def my_callback(gpio_id, val):
    my_logprint("Edge detected on " + str(gpio_id))
    my_logprint(Counters)
    myCallBackCount = Counters[str(gpio_id)]
    myCallBackCount.add_tick(1)
    my_logprint( "Total Amt : " + str(myCallBackCount.totalcount))
    
   
        
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
        time.sleep(int(SLEEP_SECONDS))
        publish_counters()
        socketIO.wait(seconds=1)
       
          
    

except KeyboardInterrupt:
    RPIO.cleanup()       # clean up GPIO on CTRL+C exit
RPIO.cleanup()           # clean up GPIO on normal exit
