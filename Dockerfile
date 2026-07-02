# Twhyne AI - native CPU image for normal (x86_64) PCs
# Builds the React frontend, installs a prebuilt PORTABLE llama-cpp-python
# CPU wheel, and runs the Flask backend (port 5002) + static frontend (3000).

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

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl procps \
    && rm -rf /var/lib/apt/lists/*

# Base Python deps (SymPy included for exact math)
RUN pip install --no-cache-dir \
        flask==3.1.1 flask-cors==6.0.1 requests==2.32.4 \
        "numpy<2" Pillow==10.4.0 sympy==1.13.3

# Install a PREBUILT portable CPU wheel of the inference engine. These wheels
# are compiled for a baseline x86-64 CPU (AVX2, no AVX-512), so they run on
# any modern consumer laptop without the "Illegal instruction" crash, and the
# build is fast/reliable (no source compilation on CI).
RUN pip install --no-cache-dir llama-cpp-python==0.3.2 \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# Application code
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/build /app/frontend/build

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/models /app/backend/rag_storage

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
