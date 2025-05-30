const moment = require("moment-timezone");

const schedule = require("node-schedule");
const fs = require("fs");

moment.tz.setDefault("Europe/Dublin");

const axios = require("axios");
const token =
    process.env.NODE_ENV === "dev"
        ? process.env.DEV_TOKEN
        : fs.readFileSync("/etc/connecthing-api/token");
const baseURL =
    process.env.NODE_ENV === "dev"
        ? process.env.TENANT_URL
        : "http://api.connecthing/";
const platformRequest = axios.create({
    baseURL: baseURL,
    headers: {
        Authorization: "Bearer " + token,
    },
});

function getRandomFloat(min, max, decimals) {
    const str = (Math.random() * (max - min) + min).toFixed(decimals);

    return parseFloat(str);
}

let currentDailyMetrics = {};

let sites = [];
const pullSites = async () => {
    const { data } = await platformRequest
        .get("api/v1/twins?labels.project=celticore")
        .catch((err) => console.log(err));
    sites = data;
};
let trucks = [];
const pullTrucks = async () => {
    const {
        data: { records: devices },
    } = await platformRequest
        .get("api/v1/devices?labels.project=celticore&labels.deviceType=Truck")
        .catch((err) => console.log(err));
    trucks = devices;
};
let comps = [];
const pullComps = async () => {
    const {
        data: { records: devices },
    } = await platformRequest
        .get(
            "api/v1/devices?labels.project=celticore&labels.deviceType=AirCompressor"
        )
        .catch((err) => console.log(err));
    comps = devices;
};
let pumps = [];
const pullPumps = async () => {
    const {
        data: { records: devices },
    } = await platformRequest
        .get("api/v1/devices?labels.project=celticore&labels.deviceType=Pump")
        .catch((err) => console.log(err));
    pumps = devices;
};

const getRoute = async (siteName) => {
    console.log(siteName.toLowerCase());
    if (siteName.toLowerCase().indexOf("kenmare") > -1) {
        return JSON.parse(fs.readFileSync("kenmareRoute.json"));
    } else if (siteName.toLowerCase().indexOf("carrickmines") > -1) {
        return JSON.parse(fs.readFileSync("carrickminesRoute.json"));
    } else if (siteName.toLowerCase().indexOf("dunleer") > -1) {
        return JSON.parse(fs.readFileSync("dunleerRoute.json"));
    } else {
        return null;
    }
};

const pushTruckEngineData = async () => {
    await pullSites();
    await pullTrucks();

    sites.forEach(async (site) => {
        const truck = trucks.find((t) => t.labels.Site === site.UUID);

        if (!truck) return;

        const route = await getRoute(site.name);

        if (!route || !route.gpsCoords || !route.gpsCoords.length) return;

        const startDate = moment().subtract(1, "hours");

        const increment = (60 * 60) / route.gpsCoords.length;
        const distanceIncrement = Math.round(
            route.totalDistance / route.gpsCoords.length
        );
        const gasIncrement = 80 / route.gpsCoords.length;
        let odometerValue = 27000;
        let gasValue = 100;
        const payload = [];

        route.gpsCoords.forEach((value, index) => {
            payload.push(
                {
                    value: getRandomFloat(98, 100, 1),
                    name: "engine.temperature",
                    timestamp: startDate.valueOf(),
                    UUID: truck.UUID,
                    msg_type: "datum",
                },
                {
                    value: getRandomFloat(1, 1.5, 2),
                    name: "engine.vibration.velocity",
                    timestamp: startDate.valueOf(),
                    UUID: truck.UUID,
                    msg_type: "datum",
                },
                {
                    value: odometerValue,
                    name: "trip.odometer",
                    timestamp: startDate.valueOf(),
                    UUID: truck.UUID,
                    msg_type: "datum",
                    longitude: parseFloat(value.lon),
                    latitude: parseFloat(value.lat),
                },
                {
                    value: route.totalDistance,
                    name: "trip.speed",
                    timestamp: startDate.valueOf(),
                    UUID: truck.UUID,
                    msg_type: "datum",
                },
                {
                    value: gasValue,
                    name: "trip.gas",
                    timestamp: startDate.valueOf(),
                    UUID: truck.UUID,
                    msg_type: "datum",
                }
            );

            startDate.add(increment, "seconds");
            odometerValue += distanceIncrement;
            gasValue = gasValue - gasIncrement;
        });

        payload.push(
            {
                value: 60,
                name: "trip.duration",
                timestamp: startDate.valueOf(),
                UUID: truck.UUID,
                msg_type: "datum",
            },
            {
                value: 100,
                name: "trip.gas",
                timestamp: startDate.valueOf() + 1000 * 60,
                UUID: truck.UUID,
                msg_type: "datum",
            }
        );
        console.log("GAS STATION !");
        payload.push({
            value: {
                UUID: truck.UUID,
                config: {
                    name: "Stop at gas station",
                    description: "Gas tank refilled",
                    instructions: "Gas tank refilled",
                },
                message: "Gas tank refilled",
                severity: "INFO",
            },
            name: "davranetworks.alarm",
            timestamp: startDate.valueOf() + 1000 * 60 * 2,
            UUID: truck.UUID,
            msg_type: "event",
        });

        platformRequest
            .put("api/v1/iotdata", payload)
            .catch((err) => console.log(err));
    });
};

setInterval(() => {
    pumps.forEach((pump) => {
        const payload = [
            {
                value: getRandomFloat(58, 64, 1),
                name: "pump.temperature",
                timestamp: moment().valueOf(),
                UUID: pump.UUID,
                msg_type: "datum",
            },
            {
                value: getRandomFloat(32, 33, 2),
                name: "pump.specific.power",
                timestamp: moment().valueOf(),
                UUID: pump.UUID,
                msg_type: "datum",
            },
        ];

        platformRequest
            .put("api/v1/iotdata", payload)
            .catch((err) => console.log(err));
    });

    comps.forEach((comp) => {
        const payload = [
            {
                value: getRandomFloat(79, 81, 2),
                name: "compressor.flowrate",
                timestamp: moment().valueOf(),
                UUID: comp.UUID,
                msg_type: "datum",
            },
            {
                value: getRandomFloat(5.2, 5.9, 3),
                name: "compressor.specific.power",
                timestamp: moment().valueOf(),
                UUID: comp.UUID,
                msg_type: "datum",
            },
            {
                value: getRandomFloat(28, 32, 2),
                name: "compressor.dewpoint",
                timestamp: moment().valueOf(),
                UUID: comp.UUID,
                msg_type: "datum",
            },
        ];
        platformRequest
            .put("api/v1/iotdata", payload)
            .catch((err) => console.log(err));
    });
}, 10 * 1000);

console.log("Starting cron job");

schedule.scheduleJob("00 8 * * *", function () {
    pushTruckEngineData();
});
schedule.scheduleJob("00 12 * * *", function () {
    pushTruckEngineData();
});

// second trip
schedule.scheduleJob("00 14 * * *", function () {
    pushTruckEngineData();
});

// 3rd trip
schedule.scheduleJob("00 16 * * *", function () {
    pushTruckEngineData();
});

// every hour refresh asset cache
schedule.scheduleJob("00 59 * * * *", function () {
    pullTrucks();
    pullComps();
    pullPumps();
});

// init pull

const init = async () => {
    await pullTrucks();
    await pullComps();
    await pullPumps();
    //    pushTruckEngineData()
};

init();
