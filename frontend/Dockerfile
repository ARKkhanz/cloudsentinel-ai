# CloudSentinel AI — Frontend Multi-Stage Dockerfile
# Stage 1: Build static assets using Node.js 24 Alpine
FROM node:24-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Install exact dependencies reproducibly
RUN npm ci

# Copy frontend source and configuration files
COPY frontend/ ./

# Configure Vite production API base URL to empty string for same-origin proxying
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=""

# Compile TypeScript and bundle production assets with Vite
RUN npm run build

# Stage 2: Production runtime using lightweight Nginx Alpine
FROM nginx:1.27-alpine AS runner

# Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled production artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration (reverse proxy and SPA fallback)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port 80 (to be mapped to host port 3000 in Compose)
EXPOSE 80

# Run Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
