#!/usr/bin/env python2.7
import time
import RPIO as GPIO
import paho.mqtt.client as mqtt
import sys
import logging
import json

# remember to change the GPIO values below to match your sensors
# GPIO output = the pin that's connected to "Trig" on the sensor
# GPIO input = the pin that's connected to "Echo" on the senso
ConfigVals = {}
#logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.WARNING)
with open('/media/USBHDD/projects/starRuby/config/endpoint_mq.config') as c:
    for line in c:
        line = line.rstrip()
        mySetupList = line.split('=');
        ConfigVals[mySetupList[0]] = mySetupList[1]
        logging.warning(mySetupList)
        

BOXDEBUG = ConfigVals["BOXDEBUG"]
BOXID = ConfigVals["BOXID"]
MQTT_HOST=ConfigVals["MQCONN"]
MQTT_USER=ConfigVals["MQTT_USER"]
MQTT_PASS=ConfigVals["MQTT_PASS"]
MQTT_IS_SECURE=ConfigVals["MQTT_IS_SECURE"]
MQTT_PORT=ConfigVals["MQTT_PORT"]
        
TRIG = 6
ECHO = 6
CLOSE_TRESHOLD = 30
MAX_CLOSE_TIME = 10
def reading(sensor):

    GPIO.setwarnings(False)

    GPIO.setmode(GPIO.BCM)
 
    if sensor == 0:
        
       
        #GPIO.setup(TRIG,GPIO.OUT)
        GPIO.setup(ECHO,GPIO.IN)
        #GPIO.output(TRIG, GPIO.LOW)
        #Might need more time
        time.sleep(0.3) 
        
        #GPIO.output(TRIG, True)
        
        time.sleep(0.00001)
        
        #GPIO.output(TRIG, False)

        #while GPIO.input(ECHO) == 0:
            #signaloff = time.time()
        

        #while GPIO.input(ECHO) == 1:
            #signalon = time.time()
        
 
        #timepassed = signalon - signaloff
        
 
        #distance = timepassed * 17000

        return GPIO.input(ECHO)
        

    else:
        print "Incorrect usonic() function varible."

def my_logprint(message):
    if BOXDEBUG == 'True':
        print message    
        sys.stdout.flush()
    
def on_connect(client, userdata, flags, rc):
    my_logprint("Connected with result code "+str(rc))
    my_logprint("Connected with userdata "+str(userdata))
    
    client.subscribe(BOXID)
    
def on_hbt_message(data,client):
    client.publish('549fRAMR4bd_BOXES', '{"msgType":"HBT_RESP","boxid":"'+ BOXID+ '","status":"Active"}')
    
    
# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    
    my_logprint("on message :" + msg.topic+" "+str(msg.payload))
    

try:
    
    
    # Connect to MQTT 
    client = mqtt.Client(client_id=str(BOXID))
    if MQTT_IS_SECURE == 'True':
        client.tls_set(ca_certs='/usr/local/lib/python2.7/dist-packages/requests/iot.cointrak.io.chained.crt',\
                   certfile='/usr/local/lib/python2.7/dist-packages/requests/iot.cointrak.io.pem',\
                    keyfile='/usr/local/lib/python2.7/dist-packages/requests/iot.cointrak.io.key',ciphers=None)
    
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
            time.sleep(5)
            
                

    client.loop_start()
    
    
    
    
    
    
    init_time = None
    end_time = None
    alert_sent = False
    while(1) :
        myReading = reading(0)
        my_logprint("myReading:" + str(myReading))
        if myReading < CLOSE_TRESHOLD:
            if init_time is None:
                my_logprint("Init is Null:")
                init_time = time.time()
                
            else:
                end_time =  time.time()
                timeelapsed =  end_time - init_time
                my_logprint("timeelapsed :"  + str(timeelapsed))
                if timeelapsed > MAX_CLOSE_TIME :
                    if alert_sent == False : 
                        my_logprint( "Alert too close for too long:" + str(myReading) + " Time : " + str(timeelapsed))
                        output = {}
                        output['boxid'] = BOXID
                        output['alert'] = "TB1"
                        output['timeelapsed'] = timeelapsed
                        client.publish('TB1_PUBLISH', json.dumps(output))
                        alert_sent = True
                        
                    
                        
        else : 
            init_time = None
            alert_sent = False
            
            
        time.sleep(0.20)

          


except KeyboardInterrupt:
    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
GPIO.cleanup()           # clean up GPIO on normal exit
