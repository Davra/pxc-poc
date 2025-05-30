# Stage 1: Build the Angular app
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build  -- --base-href /microservices/angular-demo-app/ --output-path=dist --configuration=production

# Stage 2: Serve the app with Nginx
FROM nginx:alpine

# Copy built app to Nginx html directory
COPY --from=build /app/dist/browser /usr/share/nginx/html

# Copy custom nginx config (optional, for Angular routing)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]