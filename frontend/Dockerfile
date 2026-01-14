# Multi-stage build for React frontend

# Build stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Accept build arguments
ARG VITE_API_BASE_URL
ARG VITE_MEDIA_BASE_URL
ARG VITE_DEBUG_VALIDATION=false
ARG VITE_AUTH_METHOD=otp
ARG VITE_OIDC_DOMAIN
ARG VITE_OIDC_AUTH_DOMAIN
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OAUTH_NAMESPACE

# Set as environment variables (Vite embeds these at build time)
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_MEDIA_BASE_URL=$VITE_MEDIA_BASE_URL
ENV VITE_DEBUG_VALIDATION=$VITE_DEBUG_VALIDATION
ENV VITE_AUTH_METHOD=$VITE_AUTH_METHOD
ENV VITE_OIDC_DOMAIN=$VITE_OIDC_DOMAIN
ENV VITE_OIDC_AUTH_DOMAIN=$VITE_OIDC_AUTH_DOMAIN
ENV VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID
ENV VITE_OAUTH_NAMESPACE=$VITE_OAUTH_NAMESPACE

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