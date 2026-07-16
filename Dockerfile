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
# Build identity: which commit this image was built from. Surfaced at
# /version and in the UI footer so "which build am I running" is a
# two-second check, not archaeology.
ARG TWHYNE_BUILD=dev
ENV TWHYNE_BUILD=${TWHYNE_BUILD}

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl procps build-essential \
    && rm -rf /var/lib/apt/lists/*

# Base Python deps (SymPy included for exact math; waitress is the
# production WSGI server). cmake/ninja are build tools for the engine
# compile below.
RUN pip install --no-cache-dir \
        flask==3.1.3 flask-cors==6.0.1 requests==2.33.0 \
        "numpy<2" Pillow==10.4.0 sympy==1.13.3 waitress==3.0.2 pypdf==5.1.0 \
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

# IP hardening: the shipped image must not contain readable application
# source. Compile the backend to bytecode (-b writes server.pyc next to
# server.py) and delete the .py files. Bytecode is not encryption - it
# raises the cost of inspection from "open the file" to "decompile and
# reconstruct"; the crown-jewel modules move to native compilation next.
RUN python -m compileall -b -q /app/backend \
    && find /app/backend -name "*.py" -delete \
    && (find /app/backend -name "__pycache__" -type d -exec rm -rf {} + || true)

# Strip build tooling from the final image (remove source, strip build
# tools). The compiled llama engine needs only the runtime libraries.
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libgomp1 \
    && apt-get purge -y build-essential && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip uninstall -y cmake ninja

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/models /app/backend/rag_storage

EXPOSE 3000 5002
ENTRYPOINT ["/app/docker-entrypoint.sh"]
