# Multi-stage build for React frontend

# Build stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Accept build arguments
ARG VITE_API_BASE_URL=http://localhost:8001/api
ARG VITE_MEDIA_BASE_URL=http://localhost:8001

# Set as environment variables
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_MEDIA_BASE_URL=$VITE_MEDIA_BASE_URL

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including dev dependencies needed for build)
RUN npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start nginx (run as root to handle pid file and port binding)
CMD ["nginx", "-g", "daemon off;"]