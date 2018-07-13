#!/usr/bin/env python2.7
import time
import datetime
import urllib
import urllib2
import os.path
import json
import sys
import paho.mqtt.client as mqtt
import subprocess

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

with open('/media/data/projects/gpioCounter/config/endpoint_mq.config') as c:
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
MQTT_HOST=ConfigVals["MQCONN"]
GETALL_URL=ConfigVals["GETALL_URL"]
WEB_USER=ConfigVals["WEB_USER"]
WEB_PASS=ConfigVals["WEB_PASS"]
MQTT_USER=ConfigVals["MQTT_USER"]
MQTT_PASS=ConfigVals["MQTT_PASS"]
MQTT_IS_SECURE=ConfigVals["MQTT_IS_SECURE"]
MQTT_PORT=ConfigVals["MQTT_PORT"]
relevant_path = "/var/tmp/"
Counters={}




def my_logprint(message):
    if BOXDEBUG == 'True':
        print message    
        sys.stdout.flush()
    
def on_connect(client, userdata, flags, rc):
    my_logprint("Connected with result code "+str(rc))
    client.subscribe(BOXID)
    
def on_hbt_message(data,client):
    client.publish('549fRAMR4bd_BOXES', '{"msgType":"HBT_RESP","boxid":"'+ BOXID+ '","status":"Active"}')
    
def on_update_message(data,client):#fix this methos save total to table
    my_logprint("got payload :")
    f = open(relevant_path + data['gpio_in'] + ".web", 'w')
    f.write(data['counter_in'])
    f.flush()
    f.close()
    s = open(relevant_path + data['gpio_out'] + ".web", 'w')
    s.write(data['counter_out'])
    s.flush()
    s.close()
    
    
# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    
    my_logprint("on message :" + msg.topic+" "+str(msg.payload))
    myDataObj = json.loads(str(msg.payload))
    if myDataObj['msgType'] == "UPDATE_COUNTER":
        on_update_message(myDataObj,client)
    
    if myDataObj['msgType'] == "HBT":    
        on_hbt_message(myDataObj,client)

   

def httpGetReq(values,inboundURL):
    global onlineMode
    my_logprint(values)
    params = urllib.urlencode(values)
    my_logprint("httpGetRequest " + inboundURL)
    
    try:
        response = urllib2.urlopen(inboundURL + '?' + params)
        
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
        onlineMode = True
        my_logprint(data)
        
    return data 
    
def pullCounterValFromCloud(in_counterType,machineID):
    values = dict(machine_id=machineID,email=WEB_USER,password=WEB_PASS)
    my_logprint(values)
    myData = httpGetReq(values,COUNTERVAL_URL)
    return myData

  
def on_auth_response(args):
    my_logprint("Handshake resp")
    my_logprint(args)
    pinCounterValueWeb_in = 0
    pinCounterValueWeb_out = 0
    if args['isvalid'] == 'true':
        my_logprint('valid')
        Machines = args['machines']
        #need to get total count for each pin from web
        for m in Machines:
            
            if m['gpio_active'] == True:
                my_logprint('pinCounterValueWeb_in:' + str(pinCounterValueWeb_in))
                my_logprint('pinCounterValueWeb_out:' + str(pinCounterValueWeb_out))
                my_logprint('gpio_id_in:' + str(m['gpio_id_in']))
                my_logprint('gpio_id_out:' + str(m['gpio_id_out']))
                tempCounter_in = counterObj(str(m['gpio_id_in']),'IN',m['machine_id'],pinCounterValueWeb_in,0)
                tempCounter_out = counterObj(str(m['gpio_id_out']),'OUT',m['machine_id'],pinCounterValueWeb_out,0)
                Counters[str(m['gpio_id_in'])] = tempCounter_in #check value in table update 
                Counters[str(m['gpio_id_out'])] = tempCounter_out



    
def my_callback(gpio_id, val):
    my_logprint("Edge detected on " + str(gpio_id))
    #my_logprint(Counters)
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

def myHttpPost(channel):
    myChannelCounter = Counters[channel]
    values = dict(machineID=myChannelCounter.machineID,\
                   counterType=myChannelCounter.counterType,\
                   email=WEB_USER,password=WEB_PASS,\
                    totalCount=str(myChannelCounter.totalcount))
    data = httpPostReq(values,COUNTERPOST_URL)
    my_logprint(data)   
        
def publish_counters(client):
    global Counters
    included_extenstions = ['counter'];
    file_names = [fn for fn in os.listdir(relevant_path) if any([fn.endswith(ext) for ext in included_extenstions])];
    for f in file_names:
        myIndex=f.index('.counter')
        output = subprocess.check_output("cat "+relevant_path+f, shell=True) #read from db  and create json output
        myOutObj = json.loads(output)
        gpio=myOutObj['gpio_id']
        numCount=int(myOutObj['totalcount'])
        myCounter = Counters[gpio]
        if myCounter.totalcount != numCount:
            #client.publish("publish_counter",output)
            client.publish('549fRAMR4bd_PUBLISH', output)
            myCounter.totalcount = numCount
            Counters[gpio] = myCounter
            my_logprint("Publish Success for Pin " + str(gpio))
            
    
#*********  START UP END ********************************     


try:
    values = dict(boxid=BOXID,email=WEB_USER,password=WEB_PASS)
    myLoadValues=httpGetReq(values,GETALL_URL)
    myDataObj={}
    if (myLoadValues):
        print 'my values ' + myLoadValues
        f = open("/media/data/projects/gpioCounter/config/countersMQ.config", 'w')
        f.write(str(myLoadValues))
        f.flush()
        f.close()
        myDataObj = json.loads(myLoadValues)
        
        
    else:
        with open("/media/data/projects/gpioCounter/config/countersMQ.config") as fc:
            myDataObj = json.loads(fc.read())
    
    on_auth_response(myDataObj)
    #
    client = mqtt.Client(client_id=str(BOXID))
    if MQTT_IS_SECURE == 'True':
        client.tls_set(ca_certs='/home/pi/cointrakPI/iot.cointrak.io.chained.crt',\
                   certfile='/home/pi/cointrakPI/iot.cointrak.io.chained.pem',\
                    keyfile='/home/pi/cointrakPI/iot.cointrak.io.key',ciphers=None)
    
    client.username_pw_set(MQTT_USER, password=MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    tryconnect = True
    while(tryconnect):
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            tryconnect = False
        except Exception as inst:
            my_logprint("Failed to Connect will try again .. ")
            time.sleep(int(SLEEP_SECONDS))
            
                

    client.loop_start()
    my_logprint("Listenin ... " ) 
    
    while(1):
        try:
            time.sleep(int(SLEEP_SECONDS))
            publish_counters(client)
        except Exception as inst:
            my_logprint("Exception in main loop ")

       
          
    

except KeyboardInterrupt:
    client.loop_stop()
    

