#!/usr/bin/env python2.7
import time
import datetime
import RPi.GPIO as GPIO
import urllib
import urllib2
import os.path
import json
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
onlineMode = True


print "Hi, Starting .... you reading this call 480-249-1942"
print "Parameters in File: "
print " "

with open('/home/pi/projects/gpioCounter/config/endpoint.config') as c:
    for line in c:
        line = line.rstrip()
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
        print mySetupList
    
    
    

HEART_BEAT_URL = ConfigVals["HEART_BEAT_URL"]
BOXMODE = ConfigVals["BOXMODE"]
BOXDEBUG = ConfigVals["BOXDEBUG"]
BOXID = ConfigVals["BOXID"]
COUNTERVAL_URL = ConfigVals["COUNTERVAL_URL"]
COUNTERPOST_URL= ConfigVals["COUNTERPOST_URL"]
SLEEP_SECONDS= ConfigVals["SLEEP_SECONDS"]

if BOXMODE == 'OFFLINE':
    onlineMode = False 

def my_logprint(message):
    if BOXDEBUG == 'True':
        print message    


with open('/home/pi/projects/gpioCounter/config/counters.config') as f:
    for line in f:
        line = line.rstrip()
        myList = line.split()
        my_logprint("gpio_pin:" + str(myList[0]))
        gpio_pin = str(myList[0])
        my_logprint("type:" + str(myList[1]))
        counterType = str(myList[1])
        my_logprint("machine:" + str(myList[2]))
        machineID = str(myList[2])
        tempCounter = counterObj(gpio_pin,counterType,machineID,0)
        Counters[gpio_pin] = tempCounter


def httpPostReq(values,inboundURL):
    my_logprint(values)
    params = urllib.urlencode(values)
    my_logprint("httpRequest " + inboundURL)
    req = urllib2.Request(inboundURL, params)
    try:
        response = urllib2.urlopen(req)
        onlineMode = True
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        onlineMode = False
        return    
    data = json.loads(response.read())
    response.close()
    my_logprint(data)
    return data
    

def pullCounterValFromCloud(in_counterType,machineID):
    values = dict(machineID=machineID, counterType=in_counterType)
    my_logprint(values)
    myData = httpPostReq(values,COUNTERVAL_URL)
    return myData




for k in Counters.keys():
    GPIO.setup(int(k), GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    pinCounterValueFile = 0
    pinCounterTSFile = datetime.datetime(1982,8,5,0,0,0)
    pinCounterValueWeb = 0
    pinCounterTSWeb = datetime.datetime(1982,8,5,0,0,0)
    fname = '/home/pi/projects/gpioCounter/data/' + str(k)+ ".dat"
    
    if onlineMode == True:
        myData = pullCounterValFromCloud(Counters[str(k)].counterType,\
                                         Counters[str(k)].machineName)
        
        if os.path.isfile(fname):
            my_logprint("File exists " +str(k) + ".dat")
            with open(fname) as fc:
                tempLine = fc.read()
                tempList = tempLine.split()
                pinCounterValueFile = int(tempList[0])
                tempCounterTS = tempList[1]
                tempCounterTSList = tempCounterTS.split(',')
                pinCounterTSFile = datetime.datetime(tempCounterTSList[0],\
                                   tempCounterTSList[1],\
                                   tempCounterTSList[2],\
                                   tempCounterTSList[3],\
                                   tempCounterTSList[4],\
                                   tempCounterTSList[5])
                my_logprint("pinCounterValueFile: " +str(pinCounterValueFile))
                my_logprint("pinCounterTSFile: " +str(tempCounterTS))
                
                
        if myData is None:
            my_logprint("No Data from web found")
            Counters[str(k)].totalcount = pinCounterValueFile
        else:
            if Counters[str(k)].counterType == 'IN':
                tempWebDate = myData.max_in_date.split(',')
                pinCounterValueWeb = int(myData.max_in_count)
            else:
                tempWebDate = myData.max_out_date.split(',')
                pinCounterValueWeb = int(myData.max_out_count)
            
            pinCounterTSWeb  = datetime.datetime(tempWebDate[0],\
                                           tempWebDate[1],\
                             tempWebDate[2],tempWebDate[3],\
                             tempWebDate[4],tempWebDate[5])
            
            if pinCounterTSWeb > pinCounterTSFile:
                Counters[str(k)].totalcount = pinCounterValueWeb  
            else:
                Counters[str(k)].totalcount = pinCounterTSFile 
        #end if data is None
    else:
        #OFFLINE
        if os.path.isfile(fname):
            with open(fname) as fc:
                tempLine = fc.read()
                tempList = tempLine.split()
                pinCounterValueFile = int(tempList[0])
                tempCounterTS = tempList[1]
                tempCounterTSList = tempCounterTS.split(',')
                pinCounterTSFile = datetime.datetime(tempCounterTSList[0],\
                                   tempCounterTSList[1],\
                                   tempCounterTSList[2],\
                                   tempCounterTSList[3],\
                                   tempCounterTSList[4],\
                                   tempCounterTSList[5])
        
    #end if online   
        
        
    
    
    
    
    
    
    
#*********  START UP END ********************************     

    
def writeCounterFile(filepath,counterAmt):
    d = datetime.datetime.now()
    f = open(filepath, 'w')
    f.write(counterAmt + " " + d.year + ","+ d.month + "," + d.day + "," + \
            d.hour + "," + d.minute+ "," + d.second )
    
    

def myHttpPost(channel):
    myChannelCounter = Counters[channel]
    values = dict(machineID=myChannelCounter.machineName,\
                   counterType=myChannelCounter.counterType,\
                    totalCount=str(myChannelCounter.totalcount))
    data = httpPostReq(values,COUNTERPOST_URL)
    my_logprint(data)
    
def my_callback(channel):
    myCallBackCount = Counters[str(channel)]
    myCallBackCount.add_tick(1)
    my_logprint("Edge detected on " + str(channel))
    fname = '/home/pi/projects/gpioCounter/data/' + str(channel) + ".dat"
    if BOXMODE == "ONLINE":
        myHttpPost(str(channel))
        if onlineMode == False:    
            writeCounterFile(fname,myCallBackCount.totalcount)
    else:
        writeCounterFile(fname,myCallBackCount.totalcount)


    
    

    
for k1 in Counters.keys():
    my_logprint("current key " + str(k1))
    GPIO.add_event_detect(int(k1), GPIO.FALLING, callback=my_callback,\
                           bouncetime=300)



try:
    
    
    
    while(1):
        time.sleep(int(SLEEP_SECONDS)) 
        if BOXMODE == 'ONLINE':
            hbValues = dict(boxId=BOXID)
            data = httpPostReq(hbValues,HEART_BEAT_URL)
            if myData is None:
                my_logprint("No Data from HeartBeat .. going offline")
                onlineMode = False
            else:
                my_logprint("HeartBeat Found .. going onLine")
                onlineMode = True
                
            
            
        
          
    

except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
GPIO.cleanup()           # clean up GPIO on normal exit
