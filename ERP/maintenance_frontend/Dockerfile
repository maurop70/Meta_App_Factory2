# Build Stage
FROM node:20-alpine as build
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Build the Vite application
COPY . .
RUN npm run build

# Production Serving Stage
FROM nginx:alpine

# Copy the custom Nginx reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the static build output from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
