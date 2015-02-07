#!/usr/bin/env python2.7

with open('/home/pi/projects/gpioCounter/config/endpoint.config') as c:
    mySetupLine = c.read()
    mySetupList = mySetupLine.split();
    endpointAddress = mySetupList[0]
    print mySetupLine

