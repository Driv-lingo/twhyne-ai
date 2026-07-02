# Twhyne AI - native CPU image for normal (x86_64) PCs
# Builds the React frontend, compiles the llama.cpp engine for a PORTABLE
# x86-64 baseline (AVX2, no AVX-512), and runs the Flask backend (port 5002)
# + static frontend (3000).

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
        curl procps build-essential \
    && rm -rf /var/lib/apt/lists/*

# Base Python deps (SymPy included for exact math). cmake/ninja are build
# tools for the engine compile below.
RUN pip install --no-cache-dir \
        flask==3.1.1 flask-cors==6.0.1 requests==2.32.4 \
        "numpy<2" Pillow==10.4.0 sympy==1.13.3 \
        cmake ninja

# Compile the inference engine for a PORTABLE x86-64 baseline. PyPI ships
# this package as source, and without these flags it optimizes for the CI
# runner's CPU (GGML_NATIVE defaults ON) - binaries built on AVX-512 runners
# then crash consumer laptops with "Illegal instruction". AVX2+FMA+F16C is
# supported by effectively every x86 CPU since 2013; AVX-512 stays OFF.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_AVX512=OFF"
ENV FORCE_CMAKE=1
RUN pip install --no-cache-dir llama-cpp-python==0.3.2

# Application code
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/build /app/frontend/build

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/models /app/backend/rag_storage

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
