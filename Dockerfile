# Dockerfile for SNF-AI Windsurf
# This Dockerfile sets up both frontend and backend environments

# Use Node.js as the base image for frontend
FROM node:18 AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Use Python as the base image for backend
FROM python:3.9-slim AS backend-build
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# Final image combining frontend and backend
FROM python:3.9-slim
WORKDIR /app

# Install Node.js for running the frontend
RUN apt-get update && apt-get install -y nodejs npm

# Copy built frontend from frontend-build stage
COPY --from=frontend-build /app/frontend/build /app/frontend/build

# Copy backend files
COPY --from=backend-build /app/backend /app/backend

# Copy model download script and other necessary scripts
COPY scripts/download_models.py /app/scripts/
COPY start.sh /app/

# Install httpx for model downloading
RUN pip install httpx

# Download models (if necessary)
RUN python /app/scripts/download_models.py

# Expose ports for frontend and backend - Railway will map these
EXPOSE 3000 5001

# Set executable permissions on start script
RUN chmod +x /app/start.sh

# Run the start script
CMD ["/app/start.sh"]
