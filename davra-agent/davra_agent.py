# Davra Device Agent
# This runs on a device so it communicates with the Davra Server.
# It facilitates running Applications on Devices and running Jobs.
# It should run continuously (as a service) on a device.
#
#
import subprocess
import os, sys, string
import time, requests, os.path
from requests.auth import HTTPBasicAuth
import json 
from pprint import pprint
import datetime
import paho.mqtt.client as mqtt
import davra_lib as comDavra
from PyPlcnextRsc import Device
from PyPlcnextRsc.Arp.Device.Interface.Services import IDeviceInfoService, IDeviceStatusService
# If you add new libraries to the agent, update requirements.txt


# sys.dont_write_bytecode = True
# Confirm configuration available from within the config file
if('server' not in comDavra.conf or 'UUID' not in comDavra.conf):
    print("Configuration incomplete. Please run davra_setup.py first.")
    sys.exit(1)

comDavra.logInfo('Starting Davra Device Agent.')
comDavra.logInfo('Server: ' + comDavra.conf['server'] + ". Device: " + comDavra.conf['UUID'])

# The job details of currently running job for this device.
# Files are used to track the currently running Job, script and function.
# Each get a dirctory to themselves and a json for tracking.
# The directory "currentJob" etc may be removed when job is finished.
currentJobDir = comDavra.installationDir + '/currentJob'
currentJobJson = currentJobDir + '/job.json'
currentFunctionDir = comDavra.installationDir + "/currentFunction"
currentFunctionJson = currentFunctionDir + "/currentFunction.json"
# Some flags to cache in RAM whether a function/script/job is running 
# rather than checking the hard drive continuously
flagIsFunctionRunning = False
flagIsScriptRunning = False
flagIsJobRunning = False


def sendHeartbeatMetricsToServer():
    dataToSend = [{ 
        "UUID": comDavra.conf['UUID'],
        "name": "davra.agent.heartbeat",
        "value": {
            "davraAgentVersion": comDavra.davraAgentVersion,
            "heartbeatInterval": comDavra.conf['heartbeatInterval']
        },
        "msg_type": "event"
    }]
    comDavra.logInfo('Sending heartbeat data to: ' + comDavra.conf['server'] + ": " + comDavra.conf['UUID'])
    #print(json.dumps(dataToSend, indent=4))
    statusCode = comDavra.sendDataToServer(dataToSend).status_code
    comDavra.log('Response after sending heartbeat data: ' + str(statusCode))
    return


def secureInfoSupplier():
    return (os.environ["PLC_USER"], os.environ["PLC_PASS"])


def sendPLCSystemInfoToServer(device):
    try:
        device_info_service = IDeviceInfoService(device)
        info_items = [
            "General.ArticleName",
            "General.ArticleNumber",
            "General.SerialNumber",
            "General.Firmware.Version",
            "General.Hardware.Version",
            "Interfaces.Ethernet.1.0.Mac"
        ]
        for identifier, result in zip(info_items, device_info_service.GetItems(info_items)):
            print(identifier.rjust(40) + " : " + str(result.GetValue()))

        # Get individual device info items
        article_name = device_info_service.GetItems(["General.ArticleName"])[0].GetValue()
        article_number = device_info_service.GetItems(["General.ArticleNumber"])[0].GetValue()
        serial_number = device_info_service.GetItems(["General.SerialNumber"])[0].GetValue()
        firmware_version = device_info_service.GetItems(["General.Firmware.Version"])[0].GetValue()
        hardware_version = device_info_service.GetItems(["General.Hardware.Version"])[0].GetValue()
        mac_address = device_info_service.GetItems(["Interfaces.Ethernet.1.0.Mac"])[0].GetValue()

        # Update the device labels to reflect the PLC system info
        comDavra.updateDeviceAttributeOnServer("articleName", article_name)
        comDavra.updateDeviceAttributeOnServer("articleNumber", article_number)
        comDavra.updateDeviceAttributeOnServer("serialNumber", serial_number)
        comDavra.updateDeviceAttributeOnServer("firmwareVersion", firmware_version)
        comDavra.updateDeviceAttributeOnServer("hardwareVersion", hardware_version)
        comDavra.updateDeviceAttributeOnServer("macAddress", mac_address)

    except Exception as e:
        comDavra.logError(f"Failed to fetch PLC info: {str(e)}")
    
    return


def sendPLCMetricsToServer(device):
    try:
        device_status_service = IDeviceStatusService(device)
        status_items = [
            "Status.Cpu.0.Load.Percent",
            "Status.Memory.Usage.Percent",
            "Status.ProgramMemoryIEC.Usage.Percent",
            "Status.DataMemoryIEC.Usage.Percent",
            "Status.Board.Temperature.Centigrade",
            "Status.Board.Humidity"
        ]
        for identifier, result in zip(status_items, device_status_service.GetItems(status_items)):
            print(identifier.rjust(40) + " : " + str(result.GetValue()))

        # Get individual device info items
        cpu_load = device_status_service.GetItems(["Status.Cpu.0.Load.Percent"])[0].GetValue()
        memory_usage = device_status_service.GetItems(["Status.Memory.Usage.Percent"])[0].GetValue()
        program_memory_usage = device_status_service.GetItems(["Status.ProgramMemoryIEC.Usage.Percent"])[0].GetValue()
        data_memory_usage = device_status_service.GetItems(["Status.DataMemoryIEC.Usage.Percent"])[0].GetValue()
        board_temperature = device_status_service.GetItems(["Status.Board.Temperature.Centigrade"])[0].GetValue()
        board_humidity = device_status_service.GetItems(["Status.Board.Humidity"])[0].GetValue()

        dataToSend = [{ 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.cpu_load",
            "value": cpu_load,
            "msg_type": "datum",
        }, { 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.memory_usage",
            "value": memory_usage,
            "msg_type": "datum",
        }, { 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.program_memory_usage",
            "value": program_memory_usage,
            "msg_type": "datum",
        }, { 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.data_memory_usage",
            "value": data_memory_usage,
            "msg_type": "datum",
        }, { 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.board_temperature",
            "value": board_temperature,
            "msg_type": "datum",
        }, { 
            "UUID": comDavra.conf['UUID'],
            "name": "plcnext.board_humidity",
            "value": board_humidity,
            "msg_type": "datum",
        }]
        comDavra.logInfo('Sending PLCnext data to: ' + comDavra.conf['server'] + ": " + comDavra.conf['UUID'])
        statusCode = comDavra.sendDataToServer(dataToSend).status_code
        comDavra.log('Response after sending PLCnext data: ' + str(statusCode))
    
    except Exception as e:
        comDavra.logError(f"Failed to fetch PLC metrics: {str(e)}")

    return



###########################   JOBS

def checkForPendingJob():
    dataToSend = { 
        "deviceUUID": comDavra.conf['UUID'], 
        "deviceStatus": "pending",
        "jobStatus": "active",
        "oldest": True
    }
    r = comDavra.httpPut(comDavra.conf['server'] + '/api/v1/jobs', dataToSend)
    if (r.status_code == 200):
        pendingJobs = json.loads(r.content) if comDavra.isJson(r.content) else []
        if(pendingJobs != [] and len(pendingJobs) > 0):
            comDavra.log('Pending job to run: ' + str(pendingJobs[0]))  
            runDavraJob(pendingJobs[0])
        else:
            comDavra.log('No pending job to run.') 
        return
    else:
        comDavra.logError("Issue while checking for pending job. " + str(r.status_code))
        comDavra.logError(r.content)
        return(r.status_code)
    

# For any type of job, determine which type (eg script) and run it
def runDavraJob(jobObject):
    # Catch situation where a job is already running
    if(os.path.isfile(currentJobJson) == True):
        comDavra.logWarning('A job is already running. Will not start another job. ' + jobObject["UUID"])
        return
    comDavra.log('Start Run of job ' + jobObject["UUID"])
    try:
        flagIsJobRunning = True
        # Write this job to disk as the current job
        jobObject['devices'][0]['startTime'] = comDavra.getMilliSecondsSinceEpoch()
        jobObject['devices'][0]['status'] = 'running'
        comDavra.provideFreshDirectory(currentJobDir)
        with open(currentJobJson, 'w') as outfile:
            json.dump(jobObject, outfile, indent=4)
        if ('jobConfig' in jobObject and jobObject['jobConfig']['type'].lower() == 'runfunction'):
            comDavra.logInfo('Job Run: type is runFunction. ' + jobObject['jobConfig']['functionName'])
            runFunction(jobObject['jobConfig']['functionName'], jobObject['jobConfig']['functionParameterValues'])
            return
        # Reaching here means the job type was not recognised so that is a failed situation
        updateJobWithResult('failed', 'Unknown job type')
        checkCurrentJob()
        return
    except Exception as e:
        # Reaching here means the job type was not recognised so that is a failed situation
        comDavra.logError('Job Error ' + str(e))
        updateJobWithResult('failed', 'Unknown job type')
        checkCurrentJob()
        return

        

# Check if the current job is finished
def checkCurrentJob():        
    if(os.path.isfile(currentJobJson) == True):
        with open(currentJobJson) as data_file:
            jobObject = json.load(data_file)    
        if(jobObject['devices'][0]['status'] == 'completed' or jobObject['devices'][0]['status'] == 'failed'):
            reportJobStatus()
    return


def updateJobWithResult(status, responseText):
    # Update the currentJob file on disk with the result. That will be noticed upon next "checkCurrentJob".
    jobObject = None
    if(os.path.isfile(currentJobJson) == True):
        with open(currentJobJson) as data_file:
            jobObject = json.load(data_file)
        jobObject['devices'][0]['endTime'] = comDavra.getMilliSecondsSinceEpoch()
        jobObject['devices'][0]['status'] = status
        jobObject['devices'][0]['response'] = responseText
        with open(currentJobJson, 'w') as outfile:
            json.dump(jobObject, outfile, indent=4)
    # Finished writing the file to disk indicating job progress/completion
    return


# When a job has finished, send the result to the Davra server        
def reportJobStatus():            
    comDavra.log('Current job is finished so reporting it to server now')
    jobObject = None
    with open(currentJobJson) as data_file:
        jobObject = json.load(data_file) 
    deviceJobObject = jobObject['devices'][0]
    apiEndPoint = comDavra.conf['server'] + '/api/v1/jobs/' + jobObject['UUID'] + '/' + deviceJobObject['UUID']
    comDavra.logInfo('Reporting job update to server: ' + apiEndPoint + ' : ' + json.dumps(deviceJobObject))
    r = comDavra.httpPut(apiEndPoint, deviceJobObject)
    if (r.status_code == 200):
        comDavra.log("Updated server after running job.")
        # The job has completed and been reflected at the server so delete the currentJobJson file
        os.remove(currentJobJson)
    else:
        comDavra.log("Issue while updating server after running job. " + str(r.status_code))
        comDavra.log(r.content)
    # Report job event to server as an iotdata event
    eventToSend = {
        "UUID": deviceJobObject['UUID'],
        "name": "davra.job.finished",
        "msg_type": "event",
        "value": deviceJobObject,
        "tags": {
            "status": deviceJobObject["status"]
        }
    }
    apiEndPoint = comDavra.conf['server'] + '/api/v1/iotdata'
    r = comDavra.httpPut(apiEndPoint, eventToSend)
    if (r.status_code == 200):
        comDavra.log("Sent event to server after running job.")
    else:
        comDavra.logError("Issue while sending event to server after running job. " + str(r.status_code))
        comDavra.logError(r.content)
    comDavra.provideFreshDirectory(currentJobDir) # Remove the file and dir on disk 
    flagIsJobRunning = False
    return



# Report an event to the Davra server indicating the agent started
def reportAgentStarted():            
    eventToSend = {
        "UUID": comDavra.conf['UUID'],
        "name": "davra.agent.started",
        "msg_type": "event",
        "value": comDavra.conf
    }
    r = comDavra.sendDataToServer(eventToSend)
    if (r.status_code == 200):
        comDavra.logInfo("Sent event to server to indicate agent started")
    # Update the device labels to reflect this agent version
    comDavra.logInfo("Running davraAgentVersion:" + comDavra.davraAgentVersion)
    comDavra.updateDeviceLabelOnServer("davraAgentVersion", comDavra.davraAgentVersion)
    return




###########################   RUN FUNCTIONS

# Run a function which the agent knows what to do, or get the appropriate app to run it
# This function just kicks it off. Another function will check in later to see if it is finished
def runFunction(functionName, functionParameterValues):
    # Always assign a uuid to a function if not already
    if(("functionUuid" in functionParameterValues) == False):
        functionParameterValues["functionUuid"] = comDavra.generateUuid()
    # Put a file to indicate what is happening and start the function
    comDavra.provideFreshDirectory(currentFunctionDir)
    functionInfo = { 'functionName': functionName, \
        'functionParameterValues': functionParameterValues, \
        'status': 'running', \
        'startTime': comDavra.getMilliSecondsSinceEpoch() }
    with open(currentFunctionDir + '/currentFunction.json', 'w') as outfile:
        json.dump(functionInfo, outfile, indent=4)
    # Only run functions which are within capabilities
    if((functionName in comDavra.conf["capabilities"]) is False):
        comDavra.logError('Error: Attemping to to run a function which is not in capabilities: ' + functionName)
        comDavra.logError('Error: Capabilities: ' + str(comDavra.conf["capabilities"]))
        comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'failed')
        return
    #
    comDavra.log('Running a function:' + json.dumps(functionInfo))
    flagIsFunctionRunning = True
    #
    # Is this capability something the agent knows how to do
    if(functionName in agentCapabilityFunctions):
        comDavra.log('Will run this function within the agent')
        agentCapabilityFunctions[functionName](functionParameterValues)
    else:
        # Send it onwards to the apps who may be able to do it
        comDavra.log('Will run this function within an app rather than the agent')
        sendMessageFromAgentToApps(functionInfo)
    return


# Check if a function is finished running and if it was part of a job
def checkFunctionFinished():
    currentFunctionInfo = None
    if(os.path.isfile(currentFunctionJson) == True):
        with open(currentFunctionJson) as data_file:
            currentFunctionInfo = json.load(data_file)
        if("status" in currentFunctionInfo):
            if(currentFunctionInfo["status"] == 'completed' or currentFunctionInfo["status"] == 'failed'):
                # Function has finished, report back if part of a currently running job
                functionResponse = currentFunctionInfo["response"] if "response" in currentFunctionInfo else ""
                reportFunctionFinishedAsEventToServer(currentFunctionInfo)
                updateJobWithResult(currentFunctionInfo["status"], functionResponse)
                comDavra.provideFreshDirectory(currentFunctionDir) # Wipe the currently running function files
                flagIsFunctionRunning = False
                comDavra.log('Function finished ' + json.dumps(currentFunctionInfo))
            else:
                # Has the function been running for too long. If so, declare it as failed
                if(("startTime" in currentFunctionInfo) is True):
                    if(comDavra.getMilliSecondsSinceEpoch() - int(currentFunctionInfo["startTime"]) \
                    > int(comDavra.conf["scriptMaxTime"]) * 1000):
                        comDavra.logWarning('Function has been running for too long - declare it failed')
                        currentFunctionInfo["status"] = "failed"
                        currentFunctionInfo["endTime"] = comDavra.getMilliSecondsSinceEpoch()
                        with open(currentFunctionDir + '/currentFunction.json', 'w') as outfile:
                            json.dump(currentFunctionInfo, outfile, indent=4)
                        reportFunctionFinishedAsEventToServer(currentFunctionInfo)
                        flagIsFunctionRunning = False
                        comDavra.logWarning('Function finished due to timeout ' + json.dumps(currentFunctionInfo))
            # If a function has finished, it may have been part of a job. Check if that is finished
            checkCurrentJob()
            return
        else:
            comDavra.logError('Error situation. Function has no status. Should not occur.');
    return


# Report function-finished event to server as an iotdata event
def reportFunctionFinishedAsEventToServer(currentFunctionInfo):
    if(("functionParameterValues" in currentFunctionInfo) == False \
    or ("functionUuid" in currentFunctionInfo["functionParameterValues"]) == False):
        return
    eventToSend = {
        "UUID": comDavra.conf['UUID'],
        "name": "davra.function.finished",
        "msg_type": "event",
        "value": currentFunctionInfo,
        "tags": {
            "functionUuid": currentFunctionInfo["functionParameterValues"]["functionUuid"]
        }
    }
    #comDavra.log("Sending event to server to indicate function finished: " + str(eventToSend))
    r = comDavra.sendDataToServer(eventToSend)
    comDavra.log("Sent event to server to indicate function finished. Response " + str(r.status_code))
    

# When a function was enacted by a device app rather than the agent, it reports back the
# finished function information via mqtt. This receives that message and updates the
# agent's understanding of the function's progress
def updateFunctionStatusAsReportedByDeviceApp(functionInfo):
    comDavra.log('App reported it finished a function ' + str(functionInfo))
    comDavra.upsertJsonEntry(currentFunctionJson, 'response', functionInfo["response"])
    comDavra.upsertJsonEntry(currentFunctionJson, 'status', functionInfo["status"])
    checkFunctionFinished()
    return

# Function: Reboot this device        
def agentFunctionReboot(functionParameterValues):
    # Put a file to indicate what is happening and start the reboot process
    with open(currentFunctionDir + '/doingReboot.json', 'w') as outfile:
        json.dump({ 'doingRebootAsPartOfFunction': True }, outfile, indent=4)
    comDavra.logInfo('Function: Reboot Device, starting')
    comDavra.runCommandWithTimeout('sudo reboot -h now', comDavra.conf["scriptMaxTime"])


# Check if we are just back after a purposeful reboot as part of a job or function
def checkIfJustBackAfterRebootTask():
    currentFunctionInfo = None
    if(os.path.isfile(currentFunctionJson) == True):
        with open(currentFunctionJson) as data_file:
            currentFunctionInfo = json.load(data_file)
        if(currentFunctionInfo["functionName"] == 'agent-action-rebootDevice'):
            comDavra.log('checkIfJustBackAfterRebootTask: True. Function completed')
            comDavra.upsertJsonEntry(currentFunctionJson, 'response', str(comDavra.getUptime()))
            comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'completed')
            checkFunctionFinished()             


# Function: Push an Application which has an install.sh onto this device to run as a service
# functionParameterValues should have "Installation File" which should be a tar.gz containing the service file,
# an install.sh 
def agentFunctionPushAppWithInstaller(functionParameterValues):
    comDavra.logInfo('Function: Pushing Application onto device to run as a service ' + str(functionParameterValues))
    if(functionParameterValues["Installation File"]):
        installationFile = functionParameterValues["Installation File"]
        # Download the app tarball
        try:
            tmpPath = '/tmp/' + str(comDavra.getMilliSecondsSinceEpoch())
            comDavra.ensureDirectoryExists(tmpPath)
            comDavra.runCommandWithTimeout('cd ' + tmpPath + ' && /usr/bin/curl -LO ' + installationFile, 300)
            comDavra.runCommandWithTimeout('cd ' + tmpPath + ' && /bin/tar -xvf ./* ', 300)
            comDavra.runCommandWithTimeout('cd ' + tmpPath + ' && chmod 777 ./* ', 300)
            # Ensure the install.sh is unix format
            comDavra.runCommandWithTimeout("cd " + tmpPath + " &&  sed -i $'s/\r$//' install.sh ", 30)
            installedAppPath = comDavra.installationDir + '/apps/' + str(comDavra.getMilliSecondsSinceEpoch())
            comDavra.ensureDirectoryExists(installedAppPath)
            comDavra.runCommandWithTimeout('cd ' + tmpPath + ' && cp -r * ' + installedAppPath, 300)
            installResponse = comDavra.runCommandWithTimeout('cd ' + installedAppPath + ' && bash ./install.sh ', comDavra.conf["scriptMaxTime"])
            comDavra.log('Installation response: ' + str(installResponse[1]))
            scriptStatus = 'completed'  if (installResponse[0] == 0) else 'failed'
            comDavra.upsertJsonEntry(currentFunctionJson, 'response', str(installResponse[1]))
            comDavra.upsertJsonEntry(currentFunctionJson, 'status', scriptStatus)
        except Exception as e:
            comDavra.logError('Failed to download application:' + installationFile + " : Error: " + str(e))
            comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'failed')
            checkFunctionFinished() 
        comDavra.log('Finished agentFunctionPushAppWithInstaller')
        checkFunctionFinished()
    else:
        comDavra.logWarning('Action parameters missing, nothing to do')
    # TODO
    return


# Function: Push an Application onto this device to run as a snap
def agentFunctionPushAppSnap(functionParameterValues):
    comDavra.logInfo('Function: Pushing Application onto device to run as a snap ' +  str(functionParameterValues))
    if(functionParameterValues["Snap File From Repo"]):
        comDavra.log('URL is ' + functionParameterValues["File URL"]);
    # TODO
    return


# Function: Report the device configuration to the server
def agentFunctionReportAgentConfig(functionParameterValues):
    comDavra.logInfo('Function: Reporting the agent config to server')
    comDavra.reportDeviceConfigurationToServer()
    comDavra.upsertJsonEntry(currentFunctionJson, 'response', comDavra.conf)
    comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'completed')
    checkFunctionFinished()
    return


# Function: Report the device configuration to the server
def agentFunctionUpdateAgentConfig(functionParameterValues):
    comDavra.logInfo('Function: Updating the agent config to server ' + str(functionParameterValues))
    comDavra.upsertConfigurationItem(functionParameterValues["key"], functionParameterValues["value"])
    comDavra.reportDeviceConfigurationToServer()
    comDavra.upsertJsonEntry(currentFunctionJson, 'response', comDavra.conf)
    comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'completed')
    checkFunctionFinished()
    return


# Function: Run a bash script
# Take a set of lines and write them to a shell script then execute that script
def agentFunctionRunScriptBash(functionParameterValues):
    if "script" not in functionParameterValues:
        comDavra.upsertJsonEntry(currentFunctionJson, 'response', 'script missing')
        comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'failed')
        comDavra.logError('Could not run script as function because no script to run')
        checkFunctionFinished()
        return
    # Put the script into the function dir 
    scriptFile = open(currentFunctionDir + "/script.sh", "a")
    scriptFile.write(str(functionParameterValues["script"]))
    scriptFile.close()
    comDavra.logInfo('Running script ' + str(functionParameterValues["script"]))
    os.system("chmod 777 " + currentFunctionDir + "/script.sh")
    time.sleep(0.5) # Time for file flush to disk
    # Run the script with -x flag so it prints each command before ruuning it. 
    # This allows the UI to show it formatted better for user on jobs page
    scriptResponse = comDavra.runCommandWithTimeout('cd ' + currentFunctionDir + \
    ' && sudo bash -x ' + currentFunctionDir + "/script.sh", comDavra.conf["scriptMaxTime"])
    # scriptResponse is a tuple of (exitStatusCode, stdout) . For exitStatusCode: 0 = success, 1 = failed )
    comDavra.log("Script response: " + str(scriptResponse[1]))
    scriptStatus = 'completed'  if (scriptResponse[0] == 0) else 'failed'
    comDavra.upsertJsonEntry(currentFunctionJson, 'response', str(scriptResponse[1]))
    comDavra.upsertJsonEntry(currentFunctionJson, 'status', scriptStatus)
    checkFunctionFinished()


# Function: This will search for the Digital Twin associated to the device (labels: { "OPCProfile" : <UUID> }) and update the opc-profile.json file
def agentFunctionUpdateOPCProfile(functionParameterValues):
    comDavra.logInfo('Function: Updating the OPC Profile into the device')
    res = comDavra.updateOPCProfile()
    comDavra.upsertJsonEntry(currentFunctionJson, 'response', str(res))
    comDavra.upsertJsonEntry(currentFunctionJson, 'status', 'completed')
    checkFunctionFinished()
    return



###########################   REPORT KNOWN AGENT CAPABILITIES


# Set which actions this agent can do and inform the server of these capabilities
agentCapabilityFunctions = {} # Keep a pointer to the functions which enact each of capabilities
def registerAgentCapabilities(functionName, functionDetails, functionToCallToEnactCapability):
    global agentCapabilityFunctions
    agentCapabilityFunctions[functionName] = functionToCallToEnactCapability
    # Inform the server that this device has these capabilities
    comDavra.registerDeviceCapability(functionName, functionDetails)


# Register the functions defined above as those which the agent can do
# This will then be sent to the server informing the server of agent capabilities
# This makes its way into the value at /api/v1/devices/<deviceUuid> in "capabilities"
# Device Applications may also register their own capabilities separately
#
def registerAllAgentCapabilities():
    registerAgentCapabilities('agent-action-pushAppWithInstaller', { \
        "functionParameters": { "Installation File": "file" }, \
        "functionLabel": "Push Device App (with installer)", \
        "functionDescription": "To run a device Application alongside the Device Agent on a device. Supply a tar.gz file containing an install.sh script to install it." \
    }, agentFunctionPushAppWithInstaller)
    registerAgentCapabilities('agent-action-rebootDevice', { \
        "functionParameters": {}, \
        "functionLabel": "Reboot Device", \
        "functionDescription": "Reboot the device immediately" \
    }, agentFunctionReboot)
    registerAgentCapabilities('agent-action-reportAgentConfig', { \
        "functionParameters": {}, \
        "functionLabel": "Report Agent Config to Server", \
        "functionDescription": "Send the agent configuration from agent to server" \
    }, agentFunctionReportAgentConfig)
    registerAgentCapabilities('agent-action-updateAgentConfig', { \
        "functionParameters": { "key": "string", "value": "string" }, \
        "functionLabel": "Update Config on Device Agent", \
        "functionDescription": "Upsert a configuration item on the device" \
    }, agentFunctionUpdateAgentConfig)
    registerAgentCapabilities('agent-action-runScriptBash', { \
        "functionParameters": { "script": "textarea" }, \
        "functionLabel": "Run bash script on Device", \
        "functionDescription": "Run a bash script once on the device, launched by the Device Agent" \
    }, agentFunctionRunScriptBash)
    registerAgentCapabilities('agent-action-updateOPCProfile', { \
        "functionParameters": {}, \
        "functionLabel": "Update the OPC Profile on Device", \
        "functionDescription": "It will push the OPCProfile Digital Twin associated to the device" \
    }, agentFunctionUpdateOPCProfile)

###########################   MQTT Broker running on device

# The callback for when the client receives a CONNACK response from the broker on the device.
def mqttOnConnectDevice(client, userdata, flags, resultCode):
    comDavra.log('Mqtt Device Broker: Connected with result code ' + str(resultCode))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("/agent")
    return


# The callback for when a message is received from the mqtt broker on the device.
def mqttOnMessageDevice(client, userdata, msg):
    payload = str(msg.payload.decode('utf8').replace("'", '"'))
    if(comDavra.isJson(payload)):
        processMessageFromAppToAgent(json.loads(payload))
    else:
        comDavra.logError('ERROR: Mqtt Device Broker: Received NON json Mqtt message: ' + payload)
    return
    

# Setup the MQTT client talking to the broker on the device    
clientOfDevice = None
if("mqttBrokerAgentHost" in comDavra.conf and len(comDavra.conf["mqttBrokerAgentHost"]) > 3):
    clientOfDevice = mqtt.Client()
    clientOfDevice.on_connect = mqttOnConnectDevice
    clientOfDevice.on_message = mqttOnMessageDevice
    comDavra.logInfo('Starting to connect to MQTT broker running on device ' + comDavra.conf["mqttBrokerAgentHost"])
    try:
        clientOfDevice.connect(comDavra.conf["mqttBrokerAgentHost"])
        clientOfDevice.loop_start() # Starts another thread to monitor incoming messages
    except Exception as e:
        comDavra.logError('Experienced error connecting to mqtt at ' + comDavra.conf["mqttBrokerAgentHost"] + ":" + str(e))
else:
    comDavra.logError('No MQTT broker configured on device')




###########################   Process Messages from Device Application to Device Agent

# These messages may arrive by mqtt from app to agent or api calls or flat file comms
# msg should be a json object
def processMessageFromAppToAgent(msg):
    # Ignore any messages this agent published
    if("fromAgent" in msg):
        return
    comDavra.log('processMessageFromAppToAgent: incoming msg: ' + str(msg))
    if("registerCapability" in msg):
        capabilityName = msg["registerCapability"]
        capabilityDetails = msg["capabilityDetails"] if "capabilityDetails" in msg else {}
        comDavra.registerDeviceCapability(capabilityName, capabilityDetails)
    if("runFunctionOnAgent" in msg):
        functionName = msg["runFunctionOnAgent"]
        functionParameterValues = msg["functionParameterValues"] if "functionParameterValues" in msg else {}
        runFunction(functionName, functionParameterValues)
    if("connectToAgent" in msg):
        applicationName = msg["connectToAgent"]
        comDavra.log('From app to agent, app announcing it is running: ' + applicationName)
        time.sleep(0.1)
        sendHeartbeatToDeviceApps()
    if("retrieveConfigFromAgent" in msg):
        comDavra.log('From app to agent, app requesting config')
        sendMessageFromAgentToApps({"agentConfig": comDavra.conf})
    if("finishedFunctionOnApp" in msg):
        functionName = msg["finishedFunctionOnApp"]
        comDavra.log('From app to agent, app announcing it finished running a function: ' + functionName)
        updateFunctionStatusAsReportedByDeviceApp(msg)
    if("sendIotData" in msg):
        comDavra.log('From app to agent, app announcing it has iotData to send ' + str(msg))
        sendIotDataToServer(msg)


# Send a message onto the mqtt topic which the Device Apps are lstening to
# Usually topic /agent on localhost
# msg should be valid json
def sendMessageFromAgentToApps(msg):
    comDavra.log('sendMessageFromAgentToApps: sending msg: ' + str(msg))
    msg['fromAgent'] = comDavra.davraAgentVersion
    clientOfDevice.publish('/agent', json.dumps(msg)) 


# Send a regular message to apps to inform them the agent is still available
def sendHeartbeatToDeviceApps():
    sendMessageFromAgentToApps({"agentHeartbeat": comDavra.getMilliSecondsSinceEpoch()})


# Send metrics and events to the platform server
def sendIotDataToServer(msgFromMqtt):
    comDavra.log('Sending iotdata to server ')
    print(str(msgFromMqtt))
    dataFromAgent = json.loads(msgFromMqtt["sendIotData"])
    if (type (dataFromAgent) == type ({})):
        dataFromAgent = [dataFromAgent]
    dataForServer = []
    for metric in dataFromAgent:
        if (("UUID" in metric) == False):
            metric["UUID"] = comDavra.conf["UUID"]
        if ("timestamp" not in metric):
            metric["timestamp"] = comDavra.getMilliSecondsSinceEpoch()
        if ("name" in metric and "value" in metric and "msg_type" in metric):
            comDavra.log('Sending data now to server ')
            print(str(metric))
            dataForServer.append(metric)
        else:
            comDavra.logError('Not sending data to server as it appears incomplete: ' + str(metric))
    if dataForServer:
        comDavra.log('Sending data to Server: ' + str(dataForServer))
        statusCode = comDavra.sendDataToServer(dataForServer).status_code
        comDavra.log('Response after sending iotdata to server: ' + str(statusCode))
    
    
        
        


###########################   MQTT Broker running on the Davra server (probably mqtt.davra.com)

# A device can subscribe to a topic for itself on "devices/<deviceUuid>"
# the Davra server will communicate over this topic to speak to the agent and vice-versa
# Usually the agent makes regular API calls to /api/v1/jobs to determine if there is a job to run and 
# download the job. When a new job is created on the server, a "new-job-available" mesasge will be 
# sent over mqtt to indicate this

# The callback for when the client (this agent) receives a CONNACK response from the broker
def mqttOnConnectServer(client, userdata, flags, resultCode):
    comDavra.log("Mqtt Davra Server Broker: Connected with result code " + str(resultCode))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("devices/" + comDavra.conf["UUID"])
    return


# The callback for when a message is received from the broker on platform server.
def mqttOnMessageServer(client, userdata, msg):
    payload = str(msg.payload.decode('utf8').replace("'", '"'))
    comDavra.log('Mqtt Davra Server Broker: Received Mqtt message: ' + payload)
    jsonPayload =  json.loads(payload) if comDavra.isJson(payload) else { "stringMsg": payload }
    processMessageFromServerToAgent(jsonPayload)
    return

    
# Setup the MQTT client talking to the broker on the Davra server    
clientOfServer = None
def mqttConnectToServer():
    if("mqttBrokerServerHost" in comDavra.conf and len(comDavra.conf["mqttBrokerServerHost"]) > 3):
        clientOfServer = mqtt.Client()
        clientOfServer.on_connect = mqttOnConnectServer
        clientOfServer.on_message = mqttOnMessageServer
        comDavra.log('Starting to connect to MQTT broker running on Davra server ' + comDavra.conf["mqttBrokerServerHost"])
        certfile, keyfile = comDavra.getCertForRequests()
        clientOfServer.tls_set(certfile=certfile, keyfile=keyfile)
        try:
            clientOfServer.connect(comDavra.conf["mqttBrokerServerHost"], comDavra.conf["mqttBrokerServerPort"], 60)
            clientOfServer.loop_start() # Starts another thread to monitor incoming messages
        except Exception as e:
            comDavra.logError('Experienced error connecting to mqtt at ' + comDavra.conf["mqttBrokerServerHost"] + ":" + str(e))
    else:
        comDavra.logError('No MQTT broker configured for Davra server')



###########################   Process Messages from Davra Server to this Device Agent

# These messages may arrive by mqtt from server to agent 
# msg should be a json object
def processMessageFromServerToAgent(msg):
    comDavra.log('processMessageFromServerToAgent: incoming msg: ' + str(msg))     
    if("stringMsg" in msg and msg["stringMsg"] == "davra.announcement:check-for-jobs"):
        comDavra.log('From server to device, new jobs might be available')
        checkForPendingJob()
    if("davra-announcement" in msg and msg["davra-announcement"] == "check-for-jobs"):
        comDavra.log('From server to device, new jobs might be available')
        checkForPendingJob()
    if("davra-function" in msg):
        comDavra.log('From server to device, run a function: ' + str(msg["davra-function"]))
        funcParamsToRun = {}
        if("functionParameterValues" in msg):
            funcParamsToRun = msg["functionParameterValues"]
        runFunction(msg["davra-function"], funcParamsToRun)
        



###########################   MAIN LOOP

if __name__ == "__main__":
    mqttConnectToServer()
    reportAgentStarted()
    sendMessageFromAgentToApps({ "name": "agent-test", "value": "sample published message"}) # Demonstrate mqtt ok
    # Run the reboot-finished check any time the program is started
    checkIfJustBackAfterRebootTask()  
    registerAllAgentCapabilities()
    try:
        with Device('127.0.0.1', secureInfoSupplier=secureInfoSupplier) as device:
            comDavra.log("Connected to local PLC from Docker container.")
            # Send PLCnext system info to platform server
            sendPLCSystemInfoToServer(device)
            # Main loop to run forever. 
            # Send heartbeat signal to server ocassionally, check for jobs and run them
            countMainLoop = 0
            while True:
                try:
                    # Only every n seconds
                    if(countMainLoop % int(comDavra.conf['heartbeatInterval']) == 0):
                        # Emit a heartbeat for any apps listening on mqtt
                        sendHeartbeatToDeviceApps()
                        # Send a heartbeat to platform server
                        sendHeartbeatMetricsToServer()
                        # Send PLCnext metrics to platform server
                        sendPLCMetricsToServer(device)
                        # Check for any pending jobs
                        checkForPendingJob() 
                    # check if a currently running job or function is finished
                    # Only check if the flag indicates one is running but also every n iterations just in case
                    if(flagIsFunctionRunning is True or countMainLoop % 60 == 0):
                        checkFunctionFinished()
                    if(flagIsJobRunning is True or countMainLoop % 60 == 0):
                        checkCurrentJob()    
                    # Only occasionally, report all capabilities up to server just in case.
                    if(countMainLoop % (int(comDavra.conf['heartbeatInterval']) * 10) == 0):
                        comDavra.reportDeviceCapabilities()
                except KeyboardInterrupt:
                    print("Error: issue encountered")
                    comDavra.logError("Error: issue encountered")
                countMainLoop += 1
                time.sleep(1)
    except Exception as e:
        comDavra.logError(f"Failed to connect to PLC: {str(e)}")
# End Main loop