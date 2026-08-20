# ============================================
# PolicySummarizer Docker image
# Multi-stage build: ABC solver, Quacky, and the web application
# ============================================

# --- Stage 1: Build ABC and dependencies from source ---
FROM ubuntu:22.04@sha256:2edbbc5dc405e9612ba3584ce95480277e3eb374407b5505fe26f17df77c7dbc AS abc-builder

ENV DEBIAN_FRONTEND=noninteractive

ARG GLOG_COMMIT=53d58e4531c7c90f71ddab503d915e027432447a
ARG ABC_COMMIT=04d191b793ae4d57df5ba0b9b9b37f95456e23c2
ARG MONA_COMMIT=e10403bf9d193a0e490ce735bb5514263a00165b

# System deps for building ABC, Glog, and Mona
RUN apt-get update && apt-get install -y \
    git g++ cmake make \
    build-essential autoconf automake libtool intltool \
    flex bison python3 \
    && rm -rf /var/lib/apt/lists/*

# Build Glog at the pinned revision
RUN git clone https://github.com/google/glog.git /tmp/glog \
    && cd /tmp/glog \
    && git checkout "$GLOG_COMMIT" \
    && cmake -S . -B build -G "Unix Makefiles" \
    && cmake --build build \
    && cmake --build build --target install \
    && ldconfig

# Build Mona (with the matching ABC patch)
RUN git clone https://github.com/vlab-cs-ucsb/ABC.git /opt/ABC \
    && cd /opt/ABC \
    && git checkout "$ABC_COMMIT" \
    && git submodule update --init --recursive
RUN git clone https://github.com/cs-au-dk/MONA.git /tmp/MONA \
    && cd /tmp/MONA \
    && git checkout "$MONA_COMMIT" \
    && git apply /opt/ABC/external/mona/mona_abc.patch \
    && libtoolize && aclocal && automake --gnu --add-missing && autoreconf -ivf \
    && ./configure && make all && make install && ldconfig

# Build ABC
RUN cd /opt/ABC \
    && ./autogen.sh \
    && ./configure \
    && make all \
    && make install \
    && ldconfig

# --- Stage 2: Runtime image ---
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install minimal runtime libs needed by ABC
RUN apt-get update && apt-get install -y \
    libstdc++6 libgcc-s1 \
    && rm -rf /var/lib/apt/lists/*

# Copy ABC binary and all shared libraries from builder
COPY --from=abc-builder /usr/local/bin/abc /usr/local/bin/abc
COPY --from=abc-builder /usr/local/lib/libabc.so* /usr/local/lib/
COPY --from=abc-builder /usr/local/lib/libglog.so* /usr/local/lib/
COPY --from=abc-builder /usr/local/lib/libmonadfa.so* /usr/local/lib/
COPY --from=abc-builder /usr/local/lib/libmonabdd.so* /usr/local/lib/
COPY --from=abc-builder /usr/local/lib/libmonamem.so* /usr/local/lib/
RUN ldconfig

# Set up working directory
WORKDIR /app

# Install the pinned Python runtime dependencies.
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

# Copy application code
COPY quacky/ ./quacky/
COPY web/ ./web/
COPY samples/ ./samples/
COPY *.py ./

# Expose port
EXPOSE 8000

# Provide the Anthropic API key at runtime:
#   docker run -e ANTHROPIC_API_KEY=sk-... -p 8000:8000 quacky
# Or via an env file:
#   docker run --env-file .env -p 8000:8000 quacky

CMD ["python", "web/app.py"]
