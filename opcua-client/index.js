const moment = require('moment');
const fs = require('fs');
const path = require('path');
const api = require('./utils/api');

const {
  OPCUAClient,
  MessageSecurityMode,
  SecurityPolicy,
  AttributeIds,
  TimestampsToReturn,
  UserTokenType,
  BrowseDirection
} = require("node-opcua");

// OPC UA connection details
const endpointUrl = "opc.tcp://" + process.env.PLC_IP + ":4840";
const userIdentity = {
  type: UserTokenType.UserName,
  userName: process.env.PLC_USER,
  password: process.env.PLC_PASS,
};

// Config file path
const CONFIG_PATH = path.join(__dirname, './data/config.json');

// Variables to monitor and track changes
let OPCUA_VARS_TO_MONITOR = [];
let CURRENT_VARS_STRINGIFIED = '';

// Globals to track session/subscription/twin types/device
let DEVICE;
let TWIN_TYPE_OPC_PROFILE = null;
let TWIN_TYPE_OPC_VARIABLES = null;
let AVAILABLE_NODE_IDS = [];
let session;
let subscription;

// Create OPC UA client
const client = OPCUAClient.create({
  applicationName: "PLCnextBrowser",
  securityMode: MessageSecurityMode.Sign,
  securityPolicy: SecurityPolicy.Basic256,
  endpointMustExist: false,
});

/**
 * Load configuration from ./data/config.json if it exists.
 */
function loadConfig() {
  if (fs.existsSync(CONFIG_PATH)) {
    console.log("[CONFIG] Loading configuration from file...");
    const rawData = fs.readFileSync(CONFIG_PATH);
    const parsed = JSON.parse(rawData);
    OPCUA_VARS_TO_MONITOR = parsed.opcVarsToMonitor || [];
    console.log(`[CONFIG] Loaded ${OPCUA_VARS_TO_MONITOR.length} variable(s) to monitor.`);
  } else {
    console.warn("[CONFIG] config.json not found. Skipping variable monitoring.");
    OPCUA_VARS_TO_MONITOR = [];
  }
}

/**
 * Recursively browse all nodes starting from RootFolder
 */
async function browseRecursively(session, nodeId = "RootFolder", indent = "") {
  const browseResult = await session.browse({
    nodeId,
    referenceTypeId: "HierarchicalReferences",
    browseDirection: BrowseDirection.Forward,
    includeSubtypes: true,
    nodeClassMask: 0,
    resultMask: 63,
  });

  for (const reference of browseResult.references) {
    const childNodeId = reference.nodeId.toString();
    const displayName = reference.displayName.text;

    if (reference.nodeClass === 2) {
      AVAILABLE_NODE_IDS.push({
        name: displayName,
        nodeId: childNodeId,
      });
    }

    await browseRecursively(session, childNodeId, indent + "  ");
  }
}

/**
 * Create or update a subscription to monitor configured variables.
 */
async function subscribeToVariables() {
  if (subscription) {
    console.log("[SUBSCRIBE] Terminating previous subscription...");
    await subscription.terminate();
  }

  if (OPCUA_VARS_TO_MONITOR.length === 0) {
    console.log("[SUBSCRIBE] No variables configured to monitor. Subscription skipped.");
    return;
  }

  console.log("[SUBSCRIBE] Creating new subscription...");
  subscription = await session.createSubscription2({
    requestedPublishingInterval: 1000,
    requestedLifetimeCount: 100,
    requestedMaxKeepAliveCount: 10,
    maxNotificationsPerPublish: 10,
    publishingEnabled: true,
    priority: 10,
  });

  for (const { name: varName, type: varType } of OPCUA_VARS_TO_MONITOR) {
    const nodeEntry = AVAILABLE_NODE_IDS.find(entry => entry.name === varName);
    if (!nodeEntry) {
      console.warn(`[SUBSCRIBE] Variable '${varName}' not found in server. Skipping.`);
      continue;
    }

    console.log(`[SUBSCRIBE] Monitoring variable '${varName}' of type '${varType}'...`);

    const monitoredItem = await subscription.monitor(
      {
        nodeId: nodeEntry.nodeId,
        attributeId: AttributeIds.Value,
      },
      {
        samplingInterval: 100,
        discardOldest: true,
        queueSize: 10,
      },
      TimestampsToReturn.Both
    );

    monitoredItem.on("changed", (dataValue) => {
      let value = dataValue.value.value;
      console.log(`[DATA] '${varName}' changed:`, value);

      if (varType === "customattribute") {
        console.log(`[DATA] Updating custom attribute: opcua.${varName}`);
        api.updateCustomAttributes(DEVICE.UUID, {
          [`opcua.${varName}`]: value
        });
      } else {
        if (varType === "datum") {
          const parsed = parseFloat(value);
          if (isNaN(parsed)) {
            console.warn(`[DATA] Skipping '${varName}' - invalid number:`, value);
            return;
          }
          value = parsed;
        }

        console.log(`[DATA] Sending IoT data: opcua.${varName}`);
        api.sendIoTData({
          name: `opcua.${varName}`,
          value: value,
          timestamp: moment().valueOf(),
          UUID: DEVICE.UUID,
          msg_type: varType
        });
      }
    });
  }

  CURRENT_VARS_STRINGIFIED = JSON.stringify(OPCUA_VARS_TO_MONITOR);
  console.log("[SUBSCRIBE] Subscribed to configured variables.");
}

/**
 * Monitor for config.json changes and resubscribe if necessary.
 */
async function monitorConfigFileChanges() {
  setInterval(async () => {
    if (!fs.existsSync(CONFIG_PATH)) return;

    const rawData = fs.readFileSync(CONFIG_PATH);
    const updatedVars = JSON.parse(rawData).opcVarsToMonitor || [];
    const newVarsStringified = JSON.stringify(updatedVars);

    if (newVarsStringified !== CURRENT_VARS_STRINGIFIED) {
      console.log("[CONFIG WATCHER] Configuration changed. Resubscribing...");
      OPCUA_VARS_TO_MONITOR = updatedVars;
      await subscribeToVariables();
    }
  }, 2 * 60 * 1000); // Every 2 minutes
}

/**
 * Main async function to initialize everything
 */
async function main() {
  try {
    loadConfig();

    console.log("[INIT] Fetching Twin Types...");
    const twinTypes = await api.getTwinTypes();
    for (const twinType of twinTypes) {
      if (twinType.name === "OPCProfile") TWIN_TYPE_OPC_PROFILE = twinType;
      if (twinType.name === "OPCVariables") TWIN_TYPE_OPC_VARIABLES = twinType;
    }

    if (!TWIN_TYPE_OPC_PROFILE)
      TWIN_TYPE_OPC_PROFILE = await api.createTwinType({ name: "OPCProfile" });
    if (!TWIN_TYPE_OPC_VARIABLES)
      TWIN_TYPE_OPC_VARIABLES = await api.createTwinType({ name: "OPCVariables" });

    console.log("[INIT] Getting device info...");
    const user = await api.getUser();
    if (user.UUID && user.type === "DEVICE") {
      DEVICE = user;
    } else {
      throw new Error("Invalid certificate for device.");
    }

    console.log(`[OPC UA] Connecting to: ${endpointUrl}`);
    await client.connect(endpointUrl);
    console.log("[OPC UA] Connected.");

    console.log("[OPC UA] Creating session...");
    session = await client.createSession(userIdentity);
    console.log("[OPC UA] Session created.");

    console.log("[OPC UA] Browsing server...");
    await browseRecursively(session);
    console.log(`[OPC UA] Found ${AVAILABLE_NODE_IDS.length} nodes.`);

    console.log("[DAVRA] Creating OPCVariables twin...");
    const opcVariablesTwin = await api.createTwin({
      name: "OPCVariables",
      digitalTwinType: TWIN_TYPE_OPC_VARIABLES.UUID,
      customAttributes: {
        availableNodeIds: AVAILABLE_NODE_IDS,
      }
    });

    const mergedLabels = { ...DEVICE.labels, OPCVariables: opcVariablesTwin.UUID };
    await api.updateDevice(DEVICE.UUID, { labels: mergedLabels });

    await subscribeToVariables();
    monitorConfigFileChanges();

  } catch (err) {
    console.error("[ERROR]", err);
  }
}

main();
