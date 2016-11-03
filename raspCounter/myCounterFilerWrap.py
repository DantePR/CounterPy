#!/usr/bin/env python2.7
import time
import datetime
import RPIO
import urllib
import urllib2
import os
import json
import sys
import logging
import threading
import shlex
from subprocess import call

#GPIO.setmode(GPIO.BCM)

class counterObj: 
    def __init__(self, gpioPin,counterType,machineID,totalcount,offline):
        self.counterType = counterType  
        self.gpioPin = gpioPin
        self.machineID = machineID
        self.totalcount = totalcount
        self.publish = False
        self.offline = False
        self.lock = threading.Lock()
        
        
    def add_tick(self, tick):
        self.lock.acquire()
        try:
            self.totalcount = self.totalcount + 1
            self.publish = True
           
        finally:
            self.lock.release()
    def setPublish(self,publish):
        self.lock.acquire()
        try:
            self.publish = publish
        finally:
            self.lock.release()
    def Publish(self,in_path):
        self.lock.acquire()
        try:
            if self.publish == True:
                self.publish = False
                msg = '{"msgType":"COUNTER_UPDATE","machineID":"'+ str(self.machineID)\
                + '","gpio_id":"' + str(self.gpioPin)+\
                '","totalcount":"'+str(self.totalcount)+\
                '","counter_type":"'+str(self.counterType)+'"}'
                f = open(in_path + ".counter", 'w')
            
                f.write(msg)
                f.flush()
                f.close()
                
                
        finally:
            self.lock.release()
        
        
        
Machines = {}
Counters = {}
ConfigVals = {}
onlineMode = True
CommandString = './pulse'
logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.WARNING)
#time.sleep(int(120))
#print "Hi, Starting .... if your reading this call 480-249-1942"
#print "Parameters in File: "
#print " "

with open('/media/USBHDD/projects/gpioCounter/config/endpoint.config') as c:
    for line in c:
        line = line.rstrip()
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
        logging.warning(mySetupList)
    
    
    

HEART_BEAT_URL = ConfigVals["HEART_BEAT_URL"]
BOXMODE = 'OFFLINE'
BOXDEBUG = ConfigVals["BOXDEBUG"]
BOXID = ConfigVals["BOXID"]
COUNTERVAL_URL = ConfigVals["COUNTERVAL_URL"]
COUNTERPOST_URL= ConfigVals["COUNTERPOST_URL"]
SLEEP_SECONDS= ConfigVals["SLEEP_SECONDS"]
WEB_USER=ConfigVals["WEB_USER"]
WEB_PASS=ConfigVals["WEB_PASS"]
GETALL_URL=ConfigVals["GETALL_URL"]
relevant_path = "/var/tmp/"
Counters={}
lasCounterList={}




def my_logprint(message):
    if BOXDEBUG == 'True':
        logging.info(message)
        


def httpGetReq(values,inboundURL):
    global onlineMode
    my_logprint(values)
    params = urllib.urlencode(values)
    my_logprint("httpGetRequest " + inboundURL)
    
    try:
        response = urllib2.urlopen(inboundURL + '?' + params)
        
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        logging.error(e.read())
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
        onlineMode = True
        
    return data 
    
def pullCounterValFromCloud(in_counterType,machineID):
    values = dict(machine_id=machineID,email=WEB_USER,password=WEB_PASS)
    my_logprint(values)
    myData = httpGetReq(values,COUNTERVAL_URL)
    return myData

      
def on_auth_response(args):
    global CommandString
    my_logprint("Handshake resp")
    my_logprint(args)
    pinCounterValueWeb_in = 0
    pinCounterValueWeb_out = 0
    myParameters ={}
    if args['isvalid'] == 'true':
        my_logprint('valid')
        Machines = args['machines']
        #need to get total count for each pin from web
        for m in Machines:
            
            if m['gpio_active'] == True:
                myData = pullCounterValFromCloud('IN',m['machine_id'])
                if (myData):
                    myDataObj = json.loads(myData)
                    for i in myDataObj:
                        pinCounterValueWeb_in = int(i['max_in_count'])
                        pinCounterValueWeb_out = int(i['max_out_count'])
            
                my_logprint('pinCounterValueWeb_in:' + str(pinCounterValueWeb_in))
                my_logprint('pinCounterValueWeb_out:' + str(pinCounterValueWeb_out))
                my_logprint('gpio_id_in:' + str(m['gpio_id_in']))
                my_logprint('gpio_id_out:' + str(m['gpio_id_out']))
                
                CommandString = CommandString + ' ' + str(m['gpio_id_in']).zfill(2) + str(pinCounterValueWeb_in) + " " + str(m['gpio_id_out']).zfill(2) + str(pinCounterValueWeb_out) ;
                my_logprint('CommandString:' + CommandString)
                #tempCounter_in = counterObj(str(m['gpio_id_in']),'IN',m['machine_id'],pinCounterValueWeb_in,0)
                #tempCounter_out = counterObj(str(m['gpio_id_out']),'OUT',m['machine_id'],pinCounterValueWeb_out,0)
                #Counters[str(m['gpio_id_in'])] = tempCounter_in
                #Counters[str(m['gpio_id_out'])] = tempCounter_out
                #lasCounterList[str(m['gpio_id_in'])] = pinCounterValueWeb_in
                #lasCounterList[str(m['gpio_id_out'])] = pinCounterValueWeb_out
                
                #RPIO.add_interrupt_callback(int(m['gpio_id_in']), my_callback,edge='falling',pull_up_down=RPIO.PUD_UP,\
                #                 threaded_callback=True,debounce_timeout_ms=int(m['gpio_dt_ms_in']))
                #RPIO.add_interrupt_callback(int(m['gpio_id_out']), my_callback,edge='falling',pull_up_down=RPIO.PUD_UP,\
                #                 threaded_callback=True,debounce_timeout_ms=int(m['gpio_dt_ms_out']))
        
        call(shlex.split(CommandString))
                
    

    
def my_callback(gpio_id, val):
    myCallBackCount = Counters[str(gpio_id)]
    myCallBackCount.add_tick(1)
    my_logprint( "Total Amt : " + str(myCallBackCount.totalcount))
    
def httpPostReq(values,inboundURL):
    global onlineMode
    my_logprint(values)
    params = urllib.urlencode(values)
    my_logprint("httpPostRequest " + inboundURL)
    req = urllib2.Request(inboundURL, params)
    try:
        response = urllib2.urlopen(req)
        
    except urllib2.HTTPError as e:
        my_logprint(str(e.code) + " " + e.read())
        logging.error(e.read())
        onlineMode = False
        data ={} 
    except urllib2.URLError as e:
        my_logprint("URLError")
        logging.error(e.read())
        onlineMode = False
        data ={} 
    else:
        data = response.read()
        response.close()
        onlineMode = True
        my_logprint(data)
           
    return data    

def myHttpPost(channel):
    myChannelCounter = Counters[channel]
    values = dict(machineID=myChannelCounter.machineID,\
                   counterType=myChannelCounter.counterType,\
                   email=WEB_USER,password=WEB_PASS,\
                    totalCount=str(myChannelCounter.totalcount))
    data = httpPostReq(values,COUNTERPOST_URL)
    my_logprint(data)   
        

def check_updates():
    
    included_extenstions = ['web'];
    file_names = [fn for fn in os.listdir(relevant_path) if any([fn.endswith(ext) for ext in included_extenstions])];
    for f in file_names:
        myIndex=f.index('.web')
        machine_id=f[0:myIndex]
        myCounter=Counters[str(machine_id)]
        
        with open(relevant_path + f) as fc:
            tempLine = fc.read()
            myCounter.totalcount = int(tempLine)
            myCounter.publish = True
        os.remove(relevant_path+f)
            
        
    
    
def publish_counters():
    localMode = onlineMode
    global Counters
    for k in Counters.keys():
        check_updates()
        myCounter = Counters[str(k)]
        thisCounterValueWeb_in = 0
        thisCounterValueWeb_out = 0
        if localMode == False:
            my_logprint("localMode if False")
            myData = pullCounterValFromCloud('IN',myCounter.machineID)
            if (myData):
                myDataObj = json.loads(myData)
                for i in myDataObj:
                    thisCounterValueWeb_in = int(i['max_in_count'])
                    thisCounterValueWeb_out = int(i['max_out_count'])
            
                
            if myCounter.counterType == "IN":
                myCounter.totalcount = myCounter.totalcount + thisCounterValueWeb_in
                if (myData):
                    myCounter.Publish(relevant_path +str(k))
            if myCounter.counterType == "OUT":
                myCounter.totalcount = myCounter.totalcount + thisCounterValueWeb_out
                if (myData):
                    myCounter.Publish(relevant_path +str(k))    
                
        
        else:
            myCounter.Publish(relevant_path +str(k))
                     
            

    
#*********  START UP END ********************************     


try:
    values = dict(boxid=BOXID,email=WEB_USER,password=WEB_PASS)
    myLoadValues=httpGetReq(values,GETALL_URL)
    myDataObj={}
    if (myLoadValues):
        logging.info('my values ' + myLoadValues)
        f = open("/media/USBHDD/projects/gpioCounter/config/counters.config", 'w')
        f.write(str(myLoadValues))
        f.flush()
        f.close()
        myDataObj = json.loads(myLoadValues)
        
    else:
        with open("/media/USBHDD/projects/gpioCounter/config/counters.config") as fc:
            myDataObj = json.loads(fc.read())
            
        
    on_auth_response(myDataObj)
    
    #RPIO.wait_for_interrupts(threaded=True)
    
    
    my_logprint("Listenin ... " ) 
    
    while(1):
        try:
            time.sleep(int(SLEEP_SECONDS))
            #publish_counters()
        except Exception as inst:
            logging.error(inst.read())
       
          
    

except KeyboardInterrupt:
    RPIO.cleanup()       # clean up GPIO on CTRL+C exit
RPIO.cleanup()           # clean up GPIO on normal exit
