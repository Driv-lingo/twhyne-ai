# Twhyne AI - native CPU image for normal (x86_64) PCs
# Builds the React frontend, installs a PORTABLE llama-cpp-python build,
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

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake curl procps \
    && rm -rf /var/lib/apt/lists/*

# Base Python deps (SymPy included for exact math)
RUN pip install --no-cache-dir \
        flask==3.1.1 flask-cors==6.0.1 requests==2.32.4 \
        "numpy<2" Pillow==10.4.0 sympy==1.13.3

# Compile llama-cpp-python in PORTABLE mode. GGML_NATIVE=OFF stops the build
# from targeting the build server's CPU (which has AVX-512). We enable only
# AVX/AVX2/FMA/F16C, which every modern consumer CPU supports, so the binary
# does not crash with "Illegal instruction" on laptops without AVX-512.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_AVX512=OFF"
ENV FORCE_CMAKE=1
RUN pip install --no-cache-dir --force-reinstall --no-binary :all: llama-cpp-python

# Application code
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/build /app/frontend/build

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/models /app/backend/rag_storage

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
