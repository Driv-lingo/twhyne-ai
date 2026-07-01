# Twhyne AI - native CPU image for normal (x86_64) PCs
# Builds the React frontend, installs the llama-cpp-python inference engine,
# and runs the Flask backend (port 5002) + static frontend (port 3000).

# ---- Stage 1: build the React frontend ----
FROM node:18-bullseye AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: python runtime with the AI engine ----
FROM python:3.11-bullseye
WORKDIR /app

# Flush stdout/stderr immediately so logs are visible in real time
ENV PYTHONUNBUFFERED=1

# Build tools needed to compile llama-cpp-python, plus curl for the license check
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake curl procps \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (CPU build of the inference engine + SymPy for exact math)
RUN pip install --no-cache-dir \
        flask==3.1.1 flask-cors==6.0.1 requests==2.32.4 \
        "numpy<2" Pillow==10.4.0 sympy==1.13.3 \
    && pip install --no-cache-dir llama-cpp-python

# Application code
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/build /app/frontend/build

# Entrypoint (license check + start services)
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Models are mounted at runtime from the host at /app/models
RUN mkdir -p /app/models

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
