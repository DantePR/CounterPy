#!/usr/bin/env python2.7
import time
import datetime
import RPIO
import urllib
import urllib2
import os.path
import json

#GPIO.setmode(GPIO.BCM)

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

with open('/media/USBHDD/projects/gpioCounter/config/endpoint.config') as c:
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


with open('/media/USBHDD/projects/gpioCounter/config/counters.config') as f:
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
    my_logprint("httpPostRequest " + inboundURL)
    req = urllib2.Request(inboundURL, params)
    try:
        response = urllib2.urlopen(req)
        onlineMode = True
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        onlineMode = False
        data ={} 
    except urllib2.URLError as e:
        my_logprint("URLError")
        onlineMode = False
        data ={} 
    else:
        data = response.read()
        response.close()
        my_logprint(data)
           
    return data

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
    
    
    

def checkIfOnline(values,inboundURL):
    my_logprint(values)
    params = urllib.urlencode(values)
    req = urllib2.Request(inboundURL, params)
    try:
        response = urllib2.urlopen(req)
     
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        onlineMode = False
        return False
    except urllib2.URLError as e:
        my_logprint("URLError")
        onlineMode = False
        return False
    else:
        onlineMode = True
        return True
        
def myHttpPost(channel):
    myChannelCounter = Counters[channel]
    values = dict(machineID=myChannelCounter.machineName,\
                   counterType=myChannelCounter.counterType,\
                    totalCount=str(myChannelCounter.totalcount))
    data = httpPostReq(values,COUNTERPOST_URL)
    my_logprint(data)
        
      
    

def pullCounterValFromCloud(in_counterType,machineID):
    values = dict(machine_id=machineID)
    my_logprint(values)
    myData = httpGetReq(values,COUNTERVAL_URL)
    return myData

def writeCounterFile(filepath,counterAmt):
    d = datetime.datetime.now()
    f = open(filepath, 'w')
    f.write(str(counterAmt) + " " + str(d.year) + ","+ str(d.month) + "," + str(d.day) + "," + \
            str(d.hour) + "," + str(d.minute)+ "," + str(d.second) )
    
    

    
def my_callback(gpio_id, val):
    myCallBackCount = Counters[str(gpio_id)]
    myCallBackCount.add_tick(1)
    my_logprint("Edge detected on " + str(gpio_id))
    fname = '/media/USBHDD/projects/gpioCounter/data/' + str(gpio_id) + ".dat"
    if BOXMODE == "ONLINE":
        myHttpPost(str(gpio_id))
        if onlineMode == False:    
            writeCounterFile(fname,myCallBackCount.totalcount)
    else:
        writeCounterFile(fname,myCallBackCount.totalcount)
        
        
        


for k in Counters.keys():
    #GPIO.setup(int(k), GPIO.IN, pull_up_down=GPIO.PUD_UP)
    RPIO.add_interrupt_callback(int(k), my_callback, pull_up_down=RPIO.PUD_UP,\
                                 threaded_callback=True,debounce_timeout_ms=10)
    #RPIO.add_interrupt_callback(int(k), my_callback, pull_up_down=RPIO.PUD_UP,\
    #                             threaded_callback=True)
    #RPIO.add_interrupt_callback(int(k), my_callback, pull_up_down=RPIO.PUD_OFF,\
    #                             threaded_callback=True,debounce_timeout_ms=50)
    
    pinCounterValueFile = 0
    pinCounterTSFile = datetime.datetime(1982,8,5,0,0,0)
    pinCounterValueWeb = 0
    pinCounterTSWeb = datetime.datetime(1982,8,5,0,0,0)
    fname = '/media/USBHDD/projects/gpioCounter/data/' + str(k)+ ".dat"
    
    if onlineMode == True:
        myData = pullCounterValFromCloud(Counters[str(k)].counterType,\
                                         Counters[str(k)].machineName)
        my_logprint("MyData Fetched:"+ str(len(myData)))
        if os.path.isfile(fname):
            my_logprint("File exists " +str(k) + ".dat")
            with open(fname) as fc:
                tempLine = fc.read()
                tempList = tempLine.split()
                pinCounterValueFile = int(tempList[0])
                tempCounterTS = tempList[1]
                tempCounterTSList = tempCounterTS.split(',')
                pinCounterTSFile = datetime.datetime(int(tempCounterTSList[0]),\
                                   int(tempCounterTSList[1]),\
                                   int(tempCounterTSList[2]),\
                                   int(tempCounterTSList[3]),\
                                   int(tempCounterTSList[4]),\
                                   int(tempCounterTSList[5]))
                my_logprint("pinCounterValueFile: " +str(pinCounterValueFile))
                my_logprint("pinCounterTSFile: " +str(tempCounterTS))
                
                
        if len(myData) == 0:
            my_logprint("No Data from web found")
            Counters[str(k)].totalcount = pinCounterValueFile
            my_logprint("GPIO " + str(k) + " Started with : " + str(pinCounterValueFile))
        else:
            myDataObj = json.loads(myData)
            if Counters[str(k)].counterType == 'IN':
                for i in myDataObj:
                    tempWebDate = i['max_in_date']
                    pinCounterValueWeb = int(i['max_in_count'])
                my_logprint("max_in_date:" + str(tempWebDate))
                my_logprint("max_in_count:" + str(pinCounterValueWeb))     
            else:
                for i in myDataObj:
                    tempWebDate = i['max_out_date']
                    pinCounterValueWeb = int(i['max_out_count'])
                my_logprint("max_out_date:" + str(tempWebDate))
                my_logprint("max_out_count:" + str(pinCounterValueWeb))     
            tempWebDatelist =  tempWebDate.split('T')
            tempDatePartlist = tempWebDatelist[0].split('-')
            tempTimePartlist = tempWebDatelist[1].split(':')
                
            for s in tempDatePartlist:
                my_logprint(s)
            for s in tempTimePartlist:
                my_logprint(s)
           
            pinCounterTSWeb  = datetime.datetime(int(tempDatePartlist[0]),\
                                           int(tempDatePartlist[1]),\
                             int(tempDatePartlist[2]),int(tempTimePartlist[0]),\
                             int(tempTimePartlist[1]),int(tempTimePartlist[2][:2]))
            
            if pinCounterTSWeb > pinCounterTSFile:
                Counters[str(k)].totalcount = pinCounterValueWeb
                my_logprint("GPIO " + str(k) + " type(" + \
                            Counters[str(k)].counterType + \
                            ") Started with web value : " + \
                            str(pinCounterValueWeb))  
            else:
                Counters[str(k)].totalcount = pinCounterValueFile
                myHttpPost(str(k)) 
                my_logprint("GPIO " + str(k) + " type(" + \
                            Counters[str(k)].counterType + \
                            ") Started with file value : " + \
                            str(pinCounterValueFile))
        #end if data is None
    else:
        #OFFLINE
        
        if os.path.isfile(fname):
            with open(fname) as fc:
                tempLine = fc.read()
                tempList = tempLine.split()
                pinCounterValueFile = int(tempList[0])
 
        Counters[str(k)].totalcount = pinCounterValueFile
        my_logprint("GPIO " + str(k) + " type(" + Counters[str(k)].counterType + ") Started with file value : " + str(pinCounterValueFile))
    #end if online   
        
        
    
    
    
    
    
    
    
#*********  START UP END ********************************     

    



    
    

    
for k1 in Counters.keys():
    my_logprint("current key " + str(k1))
    #GPIO.add_event_detect(int(k1), GPIO.FALLING, callback=my_callback,\
    #                       bouncetime=100)



try:
    RPIO.wait_for_interrupts(threaded=True)
    
    
    
    while(1):
        time.sleep(int(SLEEP_SECONDS)) 
        if BOXMODE == 'ONLINE':
            hbValues = dict(boxId=BOXID)
            onli = checkIfOnline(hbValues,HEART_BEAT_URL)
            if onli == False:
                my_logprint("No Data from HeartBeat .. going offline")
                onlineMode = False
            elif onli == True:
                my_logprint("HeartBeat Found .. going onLine")
                onlineMode = True
                
            
            
        
          
    

except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
GPIO.cleanup()           # clean up GPIO on normal exit
