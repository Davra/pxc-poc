#!/bin/bash
set -e  # Stop script on any command failure

echo "Starting installation procedure for Davra Agent"
cd `dirname $0`

installationDir="/usr/bin/davra"
installOrUpgrade="install" # Is this an installation or upgrade

if [[ $(id -u) -ne 0 ]]; then
    echo "Please run as root" 
    exit 1 
fi

if [[ ! -d "${installationDir}" ]]; 
then
	echo "Creating installation directory at ${installationDir}"
	mkdir -p "${installationDir}"
    mkdir -p "${installationDir}/currentJob"
else 
    echo "This is an upgrade."
    installOrUpgrade="upgrade"
fi 

# echo "Setting file permissons ..."
cp -r . "${installationDir}"
chmod -R 755 "${installationDir}"
cd "${installationDir}"

logFile="/var/log/davra_agent.log"
echo "Logs going to ${logFile}"
touch "${logFile}"
chmod 777 "${logFile}"

# Confirm now in the installation directory
if [[ $(pwd) != "${installationDir}" ]]; then
    echo "Could not create and navigate to ${installationDir}" 
    exit 1 
fi

echo "Agent install location ${installationDir}"
