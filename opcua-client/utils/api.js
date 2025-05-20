const axios = require('axios');
const https = require('https');
const fs = require('fs');

// Load cert and key from disk
const cert = fs.readFileSync('./certs/device2.crt');
const key = fs.readFileSync('./certs/device2.key');

const platformRequest = axios.create({
    baseURL: process.env.SERVER,
    httpsAgent: new https.Agent({
        cert,
        key,
        rejectUnauthorized: true
      })
});


async function getTwinTypes (qs) {
    let querySearch = (typeof(qs) !== 'undefined' && qs !== null) ? `?${qs}` : ``;
    var twinTypes = await platformRequest.get(`api/v1/twintypes${querySearch}`)
        .then(({data}) => data)
        .catch((error) => console.log(error));
    return twinTypes;
}

async function createTwinType (twinType) {
    var data = await platformRequest.post(`api/v1/twintypes`, twinType)
        .then(({data}) => data)
        .catch((error) => console.log(error));
    return data;
}

async function createTwin (twin) {
    var data = await platformRequest.post(`api/v1/twins`, twin)
        .then(({data}) => data)
        .catch((error) => console.log(error));
    return data;
}

async function getUser () {
    var user = await platformRequest.get(`user`)
        .then(({data}) => data)
        .catch((error) => console.log(error));
    return user;
}

async function sendIoTData (payload) {
    await platformRequest.put(`api/v1/iotdata`, payload)
        .then(({ data }) => data)
        .catch((error) => console.log("Error sendig IoT Data.", error));
}

async function updateDevice (uuid, payload) {
    await platformRequest.put(`api/v1/devices/${uuid}`, payload)
        .then(({data}) => data)
        .catch((error) => console.log(error));
}

async function updateCustomAttributes (uuid, payload) {
    await platformRequest.patch(`api/v1/devices/${uuid}/attributes`, payload)
        .then(({data}) => data)
        .catch((error) => console.log(error));
}


module.exports = {
    getUser,
    updateDevice,
    updateCustomAttributes,
    getTwinTypes,
    createTwin,
    createTwinType,
    sendIoTData  
};