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

# Install the inference engine from the standard PyPI manylinux wheel. This is
# a glibc-compatible wheel (matches the Debian/glibc base above) and llama.cpp
# performs RUNTIME CPU-feature detection, so it dispatches to the right kernels
# and does NOT execute AVX-512 on consumer CPUs that lack it (no "Illegal
# instruction" crash). No source compilation on CI, so the build is fast.
RUN pip install --no-cache-dir llama-cpp-python==0.3.2

# Application code
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/build /app/frontend/build

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/models /app/backend/rag_storage

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
