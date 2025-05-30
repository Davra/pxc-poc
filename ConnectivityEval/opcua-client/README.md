# Phoenix Contact OPC UA client

This is a OPC UA client ready to deploy as a Docker container.

## To build the image
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx build --platform linux/arm/v7 -t phoenix-contact-opcua-client:latest .