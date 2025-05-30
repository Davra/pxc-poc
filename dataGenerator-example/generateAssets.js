
const axios = require('axios');
const fs = require('fs')


const token = process.env.NODE_ENV === 'dev' ? process.env.DEV_TOKEN : fs.readFileSync('/etc/connecthing-api/token')
const baseURL = process.env.NODE_ENV === 'dev' ? process.env.TENANT_URL : 'http://api.connecthing/'
const platformRequest = axios.create({
    baseURL: baseURL,
    headers: {
        Authorization: 'Bearer ' + token
    }
});
const projectName = 'celticore'


const twinTypes =
{
    "name": "Site",
    "description": "",
    labels: {
        project: projectName
    },
    "customAttributes": {}
}


const siteTwins = [
    {
        name: "Dunleer",
        labels: {
            project: projectName
        },
        customAttributes: {
            siteManager: "Kieran O'Brien",
        },
        gpsLastSeen: 1000000,
        latitude: 53.837003,
        longitude: -6.390232
    },
    {
        name: "Carrickmines",
        labels: {
            project: projectName
        },
        customAttributes: {
            siteManager: "Kieran O'Brien",
        },
        gpsLastSeen: 1000000,
        latitude: 53.252107,
        longitude: -6.181290,
    },
    {
        name: "Kenmare",
        labels: {
            project: projectName
        },
        customAttributes: {
            siteManager: "Kieran O'Brien",
        },
        gpsLastSeen: 1000000,
        latitude: 51.864279,
        longitude: -9.562166,
    },

]



const devicesType = [
    {
        name: "DUM-011",
        labels: {
            project: projectName
        },
        customAttributes: {
            AssignedDriver: "Jimmy O'Brien",
            make: 'Caterpillar',
            model: 'CAT 789',
            registration: '161-D-123456'
        },
        labels: {
            project: projectName,
            deviceType: 'Truck'
        },
    },
    {
        name: "PUM-11",
        serialNumber: "pum-VAA1F2LESBQQEHY",
        labels: {
            project: projectName,
            deviceType: 'Pump'
        },
        customAttributes: {
            make: 'Grundfos',
            model: 'NKG 100-65-200/183'
        }
    },
    {
        name: "COM-01",
        serialNumber: "com-AC75985546",
        labels: {
            project: projectName,
            deviceType: 'AirCompressor'

        },
        customAttributes: {
            make: 'Atlas Copco',
            model: 'GA 450-100 '

        }
    },

]

const metrics = [

    { name: "compressor.flowrate", label: "Flow Rate (Comp)", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "compressor.specific.power", label: "Specific Power", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "compressor.dewpoint", label: "Dew Point", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "pump.temperature", label: "Temperature", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "pump.flowrate", label: "Flow Rate (Pump)", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "engine.temperature", label: "Temperature", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "engine.vibration.velocity", label: "Vibration Velocity", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "trip.duration", label: "Trip Duration", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "trip.speed", label: "Speed", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "trip.odometer", label: "Speed", units: "", description: "", semantics: "metric", labels: { project: projectName } },
    { name: "trip.gas", label: "Gas", units: "", description: "", semantics: "metric", labels: { project: projectName } },

]


const createResources = async () => {
    let twintypeUUID = ''
    const { data } = await platformRequest.get('api/v1/twintypes?name=Site').catch(err => console.log(err))
    if (!data.length || !data[0].UUID) {
        const twintype = await platformRequest.post('api/v1/twintypes', twinTypes)
        twintypeUUID = twintype.data.UUID
    } else {
        twintypeUUID = data[0].UUID
    }

    //get project celticore
    const { data: existingTwins } = await platformRequest.get('api/v1/twins?labels.project=celticore').catch(err => console.log(err))
    let deviceCounter = 0
    siteTwins.forEach(async twin => {
        if (exsitingTwin = existingTwins.find(t => twin.name === t.name)) {
            devicesType.forEach(async device => {
                const newDevice = JSON.parse(JSON.stringify(device))
                newDevice.labels.Site = exsitingTwin.UUID
                newDevice.name += deviceCounter
                newDevice.serialNumber += deviceCounter
                await platformRequest.post('api/v1/devices', newDevice).catch(err => console.log(err))
            })
            deviceCounter++
            return
        }
        twin.digitalTwinType = twintypeUUID
        const { data: twinData } = await platformRequest.post('api/v1/twins', twin).catch(err => console.log(err))
        if (twinData.UUID) {
            devicesType.forEach(async device => {
                const newDevice = JSON.parse(JSON.stringify(device))
                newDevice.labels.Site = twinData.UUID
                newDevice.name += deviceCounter
                newDevice.serialNumber += deviceCounter
                deviceCounter++
                await platformRequest.post('api/v1/devices', newDevice).catch(err => console.log(err))
            })
        }
    })



    await platformRequest.post('api/v1/iotdata/meta-data', metrics).catch(err => console.log(err))
}


createResources()