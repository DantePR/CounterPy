#!/usr/bin/env python3.5
import time
from datetime import datetime
import os.path
import os
import json
import uuid
import sys
import logging
import subprocess
import RPi.GPIO as GPIO
import glob
import ssl
from AWSIoTPythonSDK.core.greengrass.discovery.providers import DiscoveryInfoProvider
from AWSIoTPythonSDK.core.protocol.connection.cores import ProgressiveBackOffCore
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import DiscoveryInvalidRequestException
from adafruit_servokit import ServoKit
import redconfig
import boto3
#V1.0
#os.system('sudo chown pi /dev/hidraw0')



ENABLE_PIN = 22 #enable pin
DIR_PIN = 27 #change direction
STEP_PIN = 17
ACTUATOR_OUT_PIN = 19 # moves box out to deliver drink
ACTUATOR_IN_PIN = 13 # moves box In 
CUP_PIN = 26 # signals cup droper
LIGHTS_PIN = 12 
VALVE_PINS = 6
STEP_COUNT = 1000
TOTAL_CLICKS = 25
HAND_SERVO = 0

GPIO.setmode(GPIO.BCM)
GPIO.setup(VALVE_PINS, GPIO.OUT, initial=GPIO.HIGH)  #valve
GPIO.setup(LIGHTS_PIN, GPIO.OUT, initial=GPIO.HIGH) #Lights
GPIO.setup(CUP_PIN, GPIO.OUT, initial=GPIO.HIGH) #Cup Dropper
GPIO.setup(ENABLE_PIN,GPIO.OUT) # enable
GPIO.setup(DIR_PIN,GPIO.OUT) # direction
GPIO.setup(STEP_PIN,GPIO.OUT) # step
GPIO.setup(ACTUATOR_OUT_PIN,GPIO.OUT,initial=GPIO.HIGH) # box out
GPIO.setup(ACTUATOR_IN_PIN,GPIO.OUT,initial=GPIO.HIGH) # box in 
kit = ServoKit(channels=16)
#GPIO.setup(IR_SENSORS,GPIO.IN) #GPIO 14 -> IR sensor as input
#GPIO.setup(IR_SENSORS2,GPIO.IN) #GPIO 14 -> IR sensor as input

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb',region_name='us-west-2')
MODE = redconfig.config["MODE"]
SLEEP_SECONDS = redconfig.config["SLEEP_SECONDS"]
TEMP_TIME = redconfig.config["TEMP_TIME"]
host = redconfig.config["host"]
rootCAPath = redconfig.config["rootCAPath"]
certificatePath = redconfig.config["certificatePath"]
privateKeyPath = redconfig.config["privateKeyPath"]
clientId = redconfig.config["clientId"]
thingName = redconfig.config["thingName"]
topic = "store/"+ thingName +"/state"
topicStore = "store/"+ thingName +"/state"
totalToDispenseL = 0.3549

base_dir = redconfig.config["base_dir"]
device_folder = None
device_file = None


#This values must be reloaded from cloud 
MAX_DISCOVERY_RETRIES = redconfig.config["MAX_DISCOVERY_RETRIES"]
GROUP_CA_PATH = redconfig.config["GROUP_CA_PATH"]
BOXDEBUG = redconfig.config["BOXDEBUG"]
relevant_path = redconfig.config["relevant_path"]
Counters={}
Dispensed = 0
DispenseClicks = 200
NotifyEveryClicks = 25
NotifyClicks = 0
valveOpened = False
currentTemp = 0.00
lastTemp = 0.00
DOOR_TIME = 15
PLAY_TIME = 2
DELAY_TIME = 2
DELAY = 0.001
MAX_USED_TIMES = 3
currentRead = datetime.now()
currentReadPing = datetime.now()
lastRead = datetime.now()
lastReadPing = datetime.now()

def closeHand():
    global kit
    kit.servo[HAND_SERVO].angle = 180

def openHand():
    global kit
    kit.servo[HAND_SERVO].angle = 0

def my_callback(gpio_id):
    global Dispensed
    global NotifyClicks
    #global KeepAlaive
    Dispensed = Dispensed + 1
    NotifyClicks = NotifyClicks + 1
    my_logprint( "Notify Clicks : " + str(NotifyClicks)) 
    my_logprint( "Total Clicks : " + str(Dispensed)) 
    

def updateUsed(usedTimes,msgId):
    
    try:
        usedTimes = usedTimes + 1
        #table_node = dynamodb.Table('messages')
        now = datetime.now()
        dynamodb.put_item(
            TableName='messages',
           Item={
                    'msgId': {'S':msgId},
                    'ThingId': {'S':clientId},
                    'lastupdated': {'N': str(now.strftime('%s'))},
                    'usedTimes': {'S': str(usedTimes)}
                })
        
        tItem={
                    'msgId': {'S':msgId},
                    'ThingId': {'S':clientId},
                    'lastupdated': {'N': str(now.strftime('%s'))},
                    'usedTimes': {'S': str(usedTimes)}
                }
        myAWSIoTMQTTClient.publish(topicStore, json.dumps(tItem), 0)   

        
    
    except Exception as inst:
        print(inst)
    
def viasualConfirm():
    print(' start viasualConfirm')
    GPIO.output(12, GPIO.LOW)
    time.sleep(int(PLAY_TIME))
    GPIO.output(12, GPIO.HIGH)
    

    
    print(' end viasualConfirm')
    
def dropacup():
    global ppADDR
    global rlyCupDropper
    global CUP_PIN

    GPIO.output(CUP_PIN, GPIO.LOW) #Drop the cup
    my_logprint("Dropping Cup :")
    time.sleep(1)
    GPIO.output(CUP_PIN, GPIO.HIGH) 
    time.sleep(8)   

def on_message(client, userdata, msg):
    
    my_logprint("on message :" + msg.topic+" "+str(msg.payload))
    myDataObj = json.loads(str(msg.payload))
    if myDataObj['msgType'] == "HITMEUP":
        on_update_message(myDataObj,client)
    
    if myDataObj['msgType'] == "HBT":    
        on_hbt_message(myDataObj,client)
        
        
def dispenseliquid():
    global GPIO
    global NotifyClicks
    global Dispensed
    global valveOpened
    global detailChannel
    global totalToDispenseL
    
    if valveOpened == False : 
        totalDispL = 0
        flowr = 0.01
        amtDisp = 0.00
        flowZeroIndx = 0
        Dispensed = 0
        NotifyClicks = 0
        time_zero = time.time()
        last_time = time.time()
        my_logprint("Started Dispensing :")
        GPIO.output(6, GPIO.LOW) #open valve
        valveOpened = True
        while valveOpened :
            time.sleep(1)
            
            my_logprint("Valve still opened :")
            if NotifyClicks >= 1:
                flowZeroIndx = 0
                my_logprint("NotifyClicks >= 1 :")
                flowr = NotifyClicks / float(98) # f= (Q * 98) L/m
                my_logprint("NotifyClicks :" + str(NotifyClicks))
                my_logprint("flowr :" + str(flowr))
                apxflow = (NotifyClicks * 0.00225)  #second method estimating how much is each click
                my_logprint("apxflow :" + str(apxflow))
                NotifyClicks = 0
                now = time.time()
                tdiff = now - last_time
                last_time = time.time()
                amtDisp = tdiff * (flowr/float(60))  # the flowrate calculated in prv step is L/M have to divide by 60 to get fr per second * by timediff between cycles should aprox to sleep time on top 
                my_logprint("amtDisp :" + str(amtDisp))
                amtDisp = apxflow # for testing which method is best TODO REMOVE
                
                totalDispL = totalDispL + amtDisp
                
                my_logprint("totalDispL :" + str(totalDispL))
                #client.publish(detailChannel, '{"msgType":"DISP_OPEN","boxid":"'+ BOXID+ '","totalDispL":"'+ str(totalDispL)+ '","status":"Active","amtDisp":"'+ str(amtDisp)+ '","flowr":"'+ str(flowr)+ '","time_zero":"'+ str(time_zero)+ '","last_time":"'+ str(last_time)+ '"}') 
                if totalDispL >= totalToDispenseL:
                    valveOpened = False;
                    my_logprint("bye bye totalDispL :" + str(totalDispL))
            else:
                flowZeroIndx = flowZeroIndx + 1
                my_logprint("flowZeroIndx :" + str(flowZeroIndx))
                if flowZeroIndx > 20 :  #TODO twick this numbers to make for prod
                    valveOpened = False
                    #client.publish(detailChannel, '{"msgType":"VALVE_HANG","boxid":"'+ BOXID+ '","totalDispL":"'+ str(totalDispL)+ '","status":"Active","amtDisp":"'+ str(amtDisp)+ '","flowr":"'+ str(flowr)+ '","time_zero":"'+ str(time_zero)+ '","last_time":"'+ str(last_time)+ '"}') 
                if flowZeroIndx > 120:  #TODO twick this numbers to make for prod
                    valveOpened = False
                    #client.publish(detailChannel, '{"msgType":"VALVE_ERROR","boxid":"'+ BOXID+ '","totalDispL":"'+ str(totalDispL)+ '","status":"Active","amtDisp":"'+ str(amtDisp)+ '","flowr":"'+ str(flowr)+ '","time_zero":"'+ str(time_zero)+ '","last_time":"'+ str(last_time)+ '"}') 

                    
            if Dispensed >= 400: #need to define threashhold where we cutoff if something goes wrong so we dont go in eternal loop
                my_logprint("Reached Goal by Unhealthy way Closing:")
                valveOpened = False
                        
                    
                    
                    
        GPIO.output(6, GPIO.HIGH) # close valve
        GPIO.output(12, GPIO.HIGH) # turn the light off
        #client.publish(detailChannel, '{"msgType":"VALVE_STOP","boxid":"'+ BOXID+ '","totalDispL":"'+ str(totalDispL)+ '","status":"STOP","amtDisp":"'+ str(amtDisp)+ '","flowr":"'+ str(flowr)+ '","time_zero":"'+ str(time_zero)+ '","last_time":"'+ str(last_time)+ '"}') 
        updateShadow('Online','Green')
    else :
        #client.publish(detailChannel, '{"msgType":"VALVE_OPEN","boxid":"'+ BOXID+ '","totalDispL":"'+ str(totalDispL)+ '","status":"Active"}')  
        updateShadow('Online','Green')       
    #time.sleep(10)
    #GPIO.output(6, GPIO.HIGH)
    

def move_belt_back():
    
    move_belt(TOTAL_CLICKS * -1) #make negative so goes back 
            
def move_belt(position):

    global DIR_PIN
    global STEP_PIN
    global DELAY
    global STEP_COUNT
    my_logprint("Moving : " + str(position))
    index = 0
    if position > 0 :
        GPIO.output(DIR_PIN, GPIO.LOW) # go foward
    else :
        GPIO.output(DIR_PIN, GPIO.HIGH) # go backward
        position = position * -1
    while (index <= position) : 
        index = index + 1
        for x in range(STEP_COUNT):
            GPIO.output(STEP_PIN, GPIO.HIGH)
            time.sleep(DELAY)
            GPIO.output(STEP_PIN, GPIO.LOW)
            time.sleep(DELAY)
        
def move_beltEnd(currentposition):
    global IR_SENSORS2
    global TOTAL_CLICKS
    moveclicks = TOTAL_CLICKS - currentposition
    move_belt(moveclicks -1)
 
def pushboxout():
    global ACTUATOR_OUT_PIN
    GPIO.output(ACTUATOR_OUT_PIN, GPIO.LOW)
    time.sleep(int(DOOR_TIME))
    GPIO.output(ACTUATOR_OUT_PIN, GPIO.HIGH)

def pushboxin():
    global ACTUATOR_IN_PIN
    GPIO.output(ACTUATOR_IN_PIN, GPIO.LOW)
    time.sleep(int(DOOR_TIME))
    GPIO.output(ACTUATOR_IN_PIN, GPIO.HIGH)



    
        
def on_update_message(data,client):
    global GPIO
    global NotifyClicks
    global Dispensed
    global valveOpened
    global detailChannel
    global totalToDispenseL
    
    my_logprint("got payload : " + str(data))
    #client.publish(detailChannel, '{"msgType":"VALVE_OPEN","boxid":"'+ BOXID+ '","totalDispL":"0","status":"Active"}')
    #viasualConfirm()
    updateShadow('Dispensing','Red')
    GPIO.output(LIGHTS_PIN, GPIO.LOW) #turn light on
    time.sleep(2)

    flavorpos = int(data['flavorpos'])


    
    if valveOpened == False :
        GPIO.output(ENABLE_PIN, GPIO.LOW)
        #move_belt(-16)
        dropacup() #Drop the cup
        time.sleep(DELAY_TIME)
        closeHand() #hold cup
        time.sleep(DELAY_TIME)
        move_belt(flavorpos) #dispense selected tap
        time.sleep(DELAY_TIME)
        dispenseliquid()
        move_beltEnd(flavorpos)
        time.sleep(DELAY_TIME)
        openHand()
        time.sleep(DELAY_TIME)
        pushboxout()#pushboxout
        time.sleep(DELAY_TIME)
        pushboxin()#pullboxIn
        move_belt_back() #bring back home
        
    
    

    
    
def openRelay():
    #Visual Confirmation play sound 
    viasualConfirm()
    
    #
    GPIO.output(5, GPIO.LOW)
    time.sleep(int(DOOR_TIME))
    #viasualConfirm()
    GPIO.output(5, GPIO.HIGH)
    print(' end openRelay')    
    
def checkbarcodeValid(barcode):
    

    print("checkbarcodeValid : " + barcode)
    
    response = dynamodb.get_item(
         TableName='messages',
          Key={
              'msgId':{'S':barcode}
              }
         
         )
    print(response)
    
    if 'Item' in response :
        print('Item')
        i = response['Item']
        print(i)
        device = i['ThingId']
        print(device)
        if device['S'] == clientId :
            print('device')
            if 'usedTimes' in i:
                usedTimes = i['usedTimes']['S'] 
                intusedTimes = int(usedTimes)
                if intusedTimes <= MAX_USED_TIMES :
                    #open relay
                    print('openrelay')
                    openRelay()
                    updateUsed(intusedTimes,barcode)
            
            #Close circuit 
       
    
def updateShadow(state,color):
    global clientId
    global myAWSIoTMQTTClient
    #desired = {}
    #desired["state"] = "Online"
    #reported = {}
    #reported["state"] = state
    #reported["color"] = color
    
    message2 = {
    "state": {
        "desired": {
            "state": "Online",
            "color": "Green"
            
        },
        "reported": {
            "state": state,
            "color": color
        }
      }
    }
    #message2['desired'] = desired
    #message2['reported'] = reported
    
    myAWSIoTMQTTClient.publish('$aws/things/'+clientId +'/shadow/update', json.dumps(message2), 0)

def ping():
    global clientId
    global myAWSIoTMQTTClient
    global currentReadPing
    global currentTemp
    global lastTemp
    global lastReadPing
    global TEMP_TIME
    #global datetime
    #my_logprint("cheking ping :")
    currentReadPing = datetime.now()
    delta = currentReadPing - lastReadPing
    if delta.total_seconds() > int(600) :
        lastReadPing = currentReadPing
        message2 = {
            "device":  clientId
                
        }
        my_logprint("sending ping :")
        myAWSIoTMQTTClient.publish('my/things/'+clientId +'/ping', json.dumps(message2), 0)
        
def pingnow():
    global myAWSIoTMQTTClient
    global clientId
    message2 = {
            "device":  clientId
                
        }
    my_logprint("sending ping :")
    myAWSIoTMQTTClient.publish('my/things/'+clientId +'/ping', json.dumps(message2), 0)
    
    
    
def configureLastWill(): 
    global myAWSIoTMQTTClient
    message2 = {
    "state": {
        "desired": {
            "state": "Online",
            "color": "Green"
            
        },
        "reported": {
            "state": "Offline",
            "color": "Red"
        }
      }
    }
    myAWSIoTMQTTClient.configureLastWill("last/will/topic", json.dumps(message2), 1)
    
     

def customOnMessage(message):
    print('Received client ' )
    #print(client)
    #print('Received userdata ' )
    #print(userdata)
    print('Received message ' )
    print(message)
def customPongMessage(client, userdata, message):
    global s3
    print('Received client ' )
    #print(client)
    #print('Received userdata ' )
    #print(userdata)
    print('Received message ' )
    
    print(message.topic)
    print(message.payload)
    myJ = json.loads(message.payload)
    if myJ['Action'] == 'UPDATE':
        print('getting a code update')
        BUCKET_NAME = myJ['BUCKET_NAME']
        OBJECT_NAME = myJ['OBJECT_NAME']
        FILE_NAME = myJ['FILE_NAME']
        s3.download_file(BUCKET_NAME, OBJECT_NAME, FILE_NAME)
        print('Finished Updating Code restarting ...' )
        os.system('sudo reboot')
     
    if myJ['Action'] == "HITMEUP":
        print('Hitting Up ...' )
        on_update_message(myJ,client)   
    
    if myJ['Action'] == "PONG":
        print('PING Up ...' )
        pingnow() 

def my_logprint(message):
    if BOXDEBUG == 'True':
        print(message)    
        sys.stdout.flush()

def my_shadowUpdate(client,userdata,message):
    my_logprint(message)

        
    
    
    



        
        
#*********  START UP END ********************************     
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


# Discover GGCs
discoveryInfoProvider = DiscoveryInfoProvider()
discoveryInfoProvider.configureEndpoint(host)
discoveryInfoProvider.configureCredentials(rootCAPath, certificatePath, privateKeyPath)
discoveryInfoProvider.configureTimeout(10)  # 10 sec

retryCount = MAX_DISCOVERY_RETRIES
discovered = False
groupCA = None
coreInfo = None

while retryCount != 0:
    try:
        discoveryInfo = discoveryInfoProvider.discover(thingName)
        caList = discoveryInfo.getAllCas()
        coreList = discoveryInfo.getAllCores()

        # We only pick the first ca and core info
        groupId, ca = caList[0]
        coreInfo = coreList[0]
        print("Discovered GGC: %s from Group: %s" % (coreInfo.coreThingArn, groupId))

        print("Now we persist the connectivity/identity information...")
        groupCA = GROUP_CA_PATH + groupId + "_CA_" + str(uuid.uuid4()) + ".crt"
        if not os.path.exists(GROUP_CA_PATH):
            os.makedirs(GROUP_CA_PATH)
        groupCAFile = open(groupCA, "w")
        groupCAFile.write(ca)
        groupCAFile.close()

        discovered = True
        print("Now proceed to the connecting flow...")
        break
    except DiscoveryInvalidRequestException as e:
        print("Invalid discovery request detected!")
        print("Type: %s" % str(type(e)))
        print("Error message: %s" % e.message)
        print("Stopping...")
        break
    except BaseException as e:
        print("Error in discovery!")
        print("Type: %s" % str(type(e)))
        print("Error message: %s" % e.message)
        retryCount -= 1
        print("\n%d/%d retries left\n" % (retryCount, MAX_DISCOVERY_RETRIES))
        print("Backing off...\n")
        backOffCore.backOff()

if not discovered:
    print("Discovery failed after %d retries. Exiting...\n" % (MAX_DISCOVERY_RETRIES))
    sys.exit(-1)

# Iterate through all connection options for the core and use the first successful one
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureCredentials(groupCA, privateKeyPath, certificatePath)
myAWSIoTMQTTClient.onMessage = customOnMessage

connected = False
for connectivityInfo in coreInfo.connectivityInfoList:
    currentHost = connectivityInfo.host
    currentPort = connectivityInfo.port
    print("Trying to connect to core at %s:%d" % (currentHost, currentPort))
    myAWSIoTMQTTClient.configureEndpoint(currentHost, currentPort)
    configureLastWill()
    try:
        myAWSIoTMQTTClient.connect()
        connected = True
        break
    except BaseException as e:
        print("Error in connect!")
        
        print("Type: %s" % str(type(e)))
        print("Error message: %s" % str(e))

if not connected:
    print("Cannot connect to core %s. Exiting..." % coreInfo.coreThingArn)
    sys.exit(-2)
    
myAWSIoTMQTTClient.subscribe('my/things/'+clientId +'/pong', 0, customPongMessage)
myAWSIoTMQTTClient.subscribe('$aws/things/'+clientId +'/shadow/update/delta', 0, my_shadowUpdate)
time.sleep(2)
try:
    
    GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(5, GPIO.FALLING, callback=my_callback,bouncetime=50)
    updateShadow('Online','Green')
    while(True):
        try:
            time.sleep(int(SLEEP_SECONDS))
            
            #my_logprint("main loop :")
            #my_logprint(GPIO.input(IR_SENSORS))
            #checkbarcodeValid(barcode_reader())
            #ping()
            
        except Exception as inst:
            my_logprint("Exception in main loop ")
            my_logprint(inst)
            updateShadow('Online','Red')

       
          
    

except KeyboardInterrupt:
    updateShadow('Offline','Red')
    time.sleep(int(SLEEP_SECONDS))
    #client.loop_stop()
    #GPIO.cleanup()
    


