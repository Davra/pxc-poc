# Phoenix Contact Davra Agent service

This is a Davra Agent service containing the Davra SDK ready to deploy as a Docker container.

## To build the image
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx build --platform linux/arm/v7 -t phoenix-contact-davra-agent:latest .