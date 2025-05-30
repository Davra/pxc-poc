# Establish connection with the Davra server
# Save the location of the Davra server to config.json for use by other programs
# Optionally: Create this device on the Davra server
#
import time, requests, os
from requests.auth import HTTPBasicAuth
import json 
from pprint import pprint
import sys
from datetime import datetime
import davra_lib as comDavra


configFilename = comDavra.agentConfigFile

currentDirectory = comDavra.runCommandWithTimeout('pwd', 10)[1]
print("Running setup of Davra Agent " + comDavra.davraAgentVersion)
print("Received arguments: ")
print(sys.argv)
print("Current directory: " + str(currentDirectory))


# Load configuration if it already exists
comDavra.loadConfiguration()


def configGetServer():
    if('server' not in comDavra.conf):
        userInput = os.environ.get("SERVER")
        # No server known yet. Was it passed as a command line param?
        for index, arg in enumerate(sys.argv):
            if arg in ['--server'] and len(sys.argv) > index + 1:
                userInput = sys.argv[index + 1]
                #comDavra.conf['server'] = sys.argv[index + 1]
                with open(configFilename, 'w') as outfile:
                    json.dump(comDavra.conf, outfile, indent=4)
                break
        # No configuration info exists so get it from user and save
        if(not userInput):
            print("Error: SERVER environment variable not set.")
            configGetServer()
            return
        if("http" not in userInput or "://" not in userInput):
            print("Ensure you specify http:// or https:// before the server name or IP")
            configGetServer()
            return
        comDavra.conf['server'] = userInput
        with open(configFilename, 'w') as outfile:
            json.dump(comDavra.conf, outfile, indent=4)
    # Confirm can reach server    
    print("Establishing connection to Davra server... ")
    # Confirm can reach the server
    headers = comDavra.getHeadersForRequests()
    cert = comDavra.getCertForRequests()
    r = requests.get(comDavra.conf['server'], headers=headers, cert=cert)
    if(r.status_code == 200):
        #print(r.content)
        print("Ok, can reach " + comDavra.conf['server'])
    else:
        print("Cannot reach server. " + comDavra.conf['server'] + ' Response: ' + str(r.status_code))
        # Repeat until server is reachable
        configGetServer()
        return

configGetServer()


def configGetUUIDOfDevice():
    # Confirm the details supplied can make authenticated API call to server
    # Find the UUID of this device
    print('Confirming device on server')
    headers = comDavra.getHeadersForRequests()
    cert = comDavra.getCertForRequests()
    r = requests.get(comDavra.conf['server'] + '/user', headers=headers, cert=cert)
    if(r.status_code == 200):
        print(r.content)
        responseContent = json.loads(r.content)
        if("UUID" in responseContent and "type" in responseContent and responseContent["type"] == "DEVICE"):
            comDavra.conf['UUID'] = json.loads(r.content)['UUID']
            print("Device confirmed on server")
            # Save device info to config file
            with open(configFilename, 'w') as outfile:
                json.dump(comDavra.conf, outfile, indent=4)
        else:
            print("ERROR: Issue with device UUID. It does not appear to be a valid certificate for a device.")
            configGetUUIDOfDevice()
            return
    else:
        print(r.content)
        print("Cannot reach server. Cannot retrieve device information. Please confirm then retry. " + str(r.status_code))
        sys.exit()

configGetUUIDOfDevice()


# heartbeatInterval is how many seconds between calling home
if('heartbeatInterval' not in comDavra.conf):
    comDavra.upsertConfigurationItem('heartbeatInterval', 600)


# scriptMaxTime is how many seconds between a script can run for before timing out
if('scriptMaxTime' not in comDavra.conf):
    comDavra.upsertConfigurationItem('scriptMaxTime', 600)


# agentRepository is where the artifacts for the agent are published
# should also have /build_version.txt to indicate the latest release version
if('agentRepository' not in comDavra.conf):
    comDavra.upsertConfigurationItem('agentRepository', 'TBD')


# What is the host of the MQTT Broker on Davra Server
if('mqttBrokerServerHost' not in comDavra.conf):
    # No configuration exists for mqtt
    # Make assumptions for the cloud based scenarios
    if ('davra.com' in comDavra.conf['server']):
        comDavra.upsertConfigurationItem('mqttBrokerServerHost', 'mqtt.davra.com')
    elif ('eemlive.com' in comDavra.conf['server']):
        comDavra.upsertConfigurationItem('mqttBrokerServerHost', 'mqtt.eemlive.com')
    else:
        # Assume the same IP as the Davra server but ignore http or port definition
        mqttBroker = comDavra.conf['server'].replace("http://", "").replace("https://", "").split(":")[0]
        print('Setting mqttBroker ' + str(mqttBroker))
        comDavra.upsertConfigurationItem('mqttBrokerServerHost', mqttBroker)


# What is the port of the MQTT Broker on Davra Server
if('mqttBrokerServerPort' not in comDavra.conf):
    comDavra.upsertConfigurationItem('mqttBrokerServerPort', 6883)


# Reload configuration inside library
print("comDavra.loadConfiguration()...")
comDavra.loadConfiguration()


# Create necessary metrics on server    
comDavra.createMetricOnServer('cpu', '%', 'CPU usage')
comDavra.createMetricOnServer('uptime', 's', 'Time since reboot')
comDavra.createMetricOnServer('ram', '%', 'RAM usage')


def getWanIpAddress():
    # Returns the current WAN IP address, as calls to internet server perceive it
    r = comDavra.httpGet('http://whatismyip.akamai.com/')
    if (r.status_code == 200):
        return r.content
    return ''


# Estimate GPS
def getLatLong():
    # Use IP address to guess location from geoIp
    wanIpAddress = getWanIpAddress()
    # Make call to GeoIP server to find out location from WAN IP
    comDavra.log('Getting Lat/Long estimate ')
    r = comDavra.httpGet('http://ip-api.com/json')
    if(r.status_code == 200):
        jsonContent = json.loads(r.content)
        latitude = jsonContent['lat']
        longitude = jsonContent['lon']
        return (latitude, longitude)
    else:
        comDavra.logWarning("Cannot reach GeoIp server. " + str(r.status_code))
        return (0,0)

(piLatitude, piLongitude) = getLatLong()
comDavra.log('Latitude/Longitude estimated as ' + str(piLatitude) + ", " + str(piLongitude))


# Confirm MQTT Broker on agent
if(comDavra.checkIsAgentMqttBrokerInstalled() == False):
    comDavra.logError('MQTT Broker not installed')
    comDavra.upsertConfigurationItem("mqttBrokerAgentHost", '')
else:
    comDavra.log('MQTT Broker installed and running')
    comDavra.upsertConfigurationItem("mqttBrokerAgentHost", '127.0.0.1')
    # To enable basic security which is only localhost connections to mqtt
    comDavra.upsertConfigurationItem("mqttRestrictions", 'localhost')
    

# Send an event to the server to inform it of the installation
dataToSend = { 
    "UUID": comDavra.conf['UUID'],
    "name": "davra.agent.installed",
    "value": {
        "deviceConfig": comDavra.conf
    },
    "msg_type": "event",
    "latitude": piLatitude,
    "longitude": piLongitude
}
# Inform user of the overall data being sent for a single metric
comDavra.log('Sending data to server: ' + comDavra.conf['server'])
comDavra.log(json.dumps(dataToSend, indent=4))
comDavra.sendDataToServer(dataToSend)


print("Finished setup.")
