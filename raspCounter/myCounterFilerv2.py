#!/usr/bin/env python2.7
import time
import datetime
import RPi.GPIO as GPIO
import urllib
import urllib2
import os
import json
import sys
import logging
import threading
import sqlite3

GPIO.setmode(GPIO.BCM)

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
    def Publish(self,this_cur,this_conn):
        self.lock.acquire()
        try:
            if self.publish == True:
                my_logprint( "going to publish pin :  " + str(self.gpioPin) + ' totalcount : ' + str(self.totalcount) + 'counter type: ' + self.counterType) 
                if self.counterType == 'IN':
                    this_cur.execute("UPDATE gpio_config set last_gpio_in = ? where gpio_id_in = ?",(self.totalcount,self.gpioPin))
                    my_logprint( "saved") 
                if self.counterType == 'OUT':
                    this_cur.execute("UPDATE gpio_config set last_gpio_out = ? where gpio_id_out = ?",(self.totalcount,self.gpioPin))
                this_conn.commit()
                self.publish = False    

                
                
                
        finally:
            self.lock.release()
        
        
        
Machines = {}
Counters = {}
ConfigVals = {}
onlineMode = True
logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.WARNING)
#time.sleep(int(120))
#print "Hi, Starting .... if your reading this call 480-249-1942"
#print "Parameters in File: "
#print " "

with open('/media/data/projects/gpioCounter/config/endpoint.config') as c:
    for line in c:
        line = line.rstrip()
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
        logging.warning(mySetupList)
    
    
    

DBFILE = ConfigVals["DBFILE"]
BOXMODE = 'OFFLINE'
BOXDEBUG = ConfigVals["BOXDEBUG"]
BOXID = ConfigVals["BOXID"]
SLEEP_SECONDS= ConfigVals["SLEEP_SECONDS"]
WEB_USER=ConfigVals["WEB_USER"]
WEB_PASS=ConfigVals["WEB_PASS"]
GETALL_URL=ConfigVals["GETALL_URL"]
relevant_path = "/var/tmp/"
Counters={}
lasCounterList={}
conn = sqlite3.connect(DBFILE)
c = conn.cursor()

def get_data():
    c.execute('SELECT * FROM gpio_config')
    all_rows = c.fetchall()
    return all_rows

def my_logprint(message):
    if BOXDEBUG == 'True':
        logging.info(message)
        
def on_auth_response():
    my_logprint("Handshake resp")
    all_rows=get_data()
    my_logprint(all_rows)
    pinCounterValueWeb_in = 0
    pinCounterValueWeb_out = 0
    for m in all_rows:
        my_logprint("Active " + m[6])
        if m[6] == 'true':               
            pinCounterValueWeb_in = int(m[7])
            pinCounterValueWeb_out = int(m[8])
            my_logprint('pinCounterValueWeb_in:' + str(pinCounterValueWeb_in))
            my_logprint('pinCounterValueWeb_out:' + str(pinCounterValueWeb_out))
            tempCounter_in = counterObj(str(m[2]),'IN',m[1],pinCounterValueWeb_in,0)
            tempCounter_out = counterObj(str(m[3]),'OUT',m[1],pinCounterValueWeb_out,0)
            Counters[str(m[2])] = tempCounter_in
            Counters[str(m[3])] = tempCounter_out
            lasCounterList[str(m[2])] = pinCounterValueWeb_in
            lasCounterList[str(m[3])] = pinCounterValueWeb_out
            GPIO.setup(int(m[2]), GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(int(m[3]), GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(int(m[2]), GPIO.FALLING, callback=my_callback,bouncetime=int(m[4]))
            my_logprint("Callback set for pin :" + m[2])
            GPIO.add_event_detect(int(m[3]), GPIO.FALLING, callback=my_callback,bouncetime=int(m[5]))
            my_logprint("Callback set for pin :" + m[3])

    

    
def my_callback(gpio_id):
    myCallBackCount = Counters[str(gpio_id)]
    myCallBackCount.add_tick(1)
    my_logprint( "Total Amt : " + str(myCallBackCount.totalcount))   
         
def publish_counters():
    localMode = onlineMode
    global Counters
    for k in Counters.keys():
        my_logprint("checking publish ... " + str(k)) 
        myCounter = Counters[str(k)]
        myCounter.Publish(c,conn)
                     
            

    
#*********  START UP END ********************************     


try:
    values = dict(boxid=BOXID,email=WEB_USER,password=WEB_PASS)
    on_auth_response()
    
    #RPIO.wait_for_interrupts(threaded=True)
    
    
    my_logprint("Listenin ... " ) 
    
    while(1):
        try:
            time.sleep(int(SLEEP_SECONDS))
            publish_counters()

        except Exception as inst:
            logging.error(inst)
       
          
    

except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
    conn.close()
GPIO.cleanup()
conn.close()           # clean up GPIO on normal exit
