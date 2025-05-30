FROM node:18-slim

# Set the working directory inside the container
WORKDIR /app

# Copy application files
COPY . /app/

# Install required libraries
RUN npm install

# Default command to run the client
CMD ["node", "index.js"]
