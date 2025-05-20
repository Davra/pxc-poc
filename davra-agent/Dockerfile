FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy application files
COPY davra_agent.py davra_lib.py davra_sdk.py davra_setup.py requirements.txt install.sh entrypoint.sh /app/
RUN chmod +x ./install.sh ./entrypoint.sh

# Install required system packages
RUN apt-get update && apt-get install -y \
    bash \
    sudo \
    curl \
    mosquitto \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir -r ./requirements.txt

# Set the script to run as entry point
ENTRYPOINT ["./entrypoint.sh"]
